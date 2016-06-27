import json
import logging
import os
import sys
import traceback

from argparse import ArgumentParser
from timeit import default_timer

import pulse_actions.handlers.treeherder_job_event as treeherder_job_event
import pulse_actions.handlers.treeherder_resultset as treeherder_resultset
import pulse_actions.handlers.treeherder_runnable as treeherder_runnable
import pulse_actions.handlers.talos as talos

from pulse_actions.utils.log_util import (
    end_logging,
    setup_logging,
    start_logging,
)

# Third party modules
from mozci.mozci import disable_validations
from mozci.query_jobs import TreeherderApi
from mozci.utils import transfer
from replay import create_consumer, replay_messages
from thsubmitter import (
    TreeherderSubmitter,
    TreeherderJobFactory
)

# This changes the behaviour of mozci in transfer.py
transfer.MEMORY_SAVING_MODE = False
transfer.SHOW_PROGRESS_BAR = False

# These constants are used inside of message_handler
ACKNOWLEDGE = True
DRY_RUN = False
JOB_FACTORY = None
LOG = None
PULSE_ACTIONS_JOB_TEMPLATE = {
    'desc': 'This job was scheduled by pulse_actions.',
    'job_name': 'pulse_actions',
    'job_symbol': 'Sch',
    # Even if 'opt' does not apply to us
    'option_collection': 'opt',
    # Used if add_platform_info is set to True
    'platform_info': ('linux', 'other', 'x86_64'),
}
REQUIRED_ENV_VARIABLES = [
    'LDAP_USER',  # To post jobs to BuildApi
    'LDAP_PW',
    'TASKCLUSTER_CLIENT_ID',  # To schedule jobs through TaskCluster
    'TASKCLUSTER_ACCESS_TOKEN',
    'TREEHERDER_CLIENT_ID',  # To submit Treeherder test jobs
    'TREEHERDER_SECRET',
    'PULSE_USER',  # To create Pulse queues and consume from them
    'PULSE_PW',
]
SUBMIT_TO_TREEHERDER = False  # XXX: Change when ready
TREEHERDER_HOST = None


def main():
    global DRY_RUN, JOB_FACTORY, LOG, TREEHERDER_HOST, SUBMIT_TO_TREEHERDER

    # 0) Parse the command line arguments
    options = parse_args()

    # 1) Set up logging
    if options.debug:
        LOG = setup_logging(logging.DEBUG)
    else:
        LOG = setup_logging(logging.INFO)

    # 2) Check required environment variables
    fail_check = False
    for env in REQUIRED_ENV_VARIABLES:
        if env not in os.environ:
            LOG.info('- {}'.format(env))
            fail_check = True

    if fail_check:
        if not options.dry_run:
            LOG.error('Please set all the missing environment variables above.')
            sys.exit(1)

    # 3) Enable memory saving (useful for Heroku)
    if options.memory_saving:
        transfer.MEMORY_SAVING_MODE = True

    # 4) Set the treeherder host
    if options.treeherder_host:
        TREEHERDER_HOST = options.treeherder_host

    elif options.config_file:
        with open(options.config_file, 'r') as file:
            # Load information only relevant to pulse_actions
            pulse_actions_config = json.load(file).get('pulse_actions')

            if pulse_actions_config:
                # Inside of some of our handlers we set the Treeherder client
                # We would not want to try to test with a stage config yet
                # we query production instead of stage
                TREEHERDER_HOST = pulse_actions_config['treeherder_host']
    else:
        LOG.error('Set --treeherder-host if you\'re not using a config file')
        sys.exit(1)

    assert TREEHERDER_HOST is not None

    # 5) Set few constants which are used by message_handler
    DRY_RUN = options.dry_run or options.replay_file is not None

    if options.submit_to_treeherder:
        SUBMIT_TO_TREEHERDER = True
    elif options.dry_run:
        SUBMIT_TO_TREEHERDER = False

    if options.acknowledge:
        ACKNOWLEDGE = True
    elif options.dry_run:
        ACKNOWLEDGE = False

    # 6) Set up the treeherder submitter
    if SUBMIT_TO_TREEHERDER:
        JOB_FACTORY = initialize_treeherder_submission(
            # XXX: For now we will post only to staging
            host='treeherder.allizom.org',
            protocol='http' if TREEHERDER_HOST.startswith('local') else 'https',
            client=os.environ['TREEHERDER_CLIENT_ID'],
            secret=os.environ['TREEHERDER_SECRET'],
            # XXX: Temporarily
            dry_run=False,
        )

    # 7) XXX: Disable mozci's validations (this might not be needed anymore)
    disable_validations()

    # 8) Determine if normal run is requested or replaying of saved messages
    if options.replay_file:
        replay_messages(
            filepath=options.replay_file,
            process_message=message_handler,
            dry_run=True,
        )
    else:
        # Normal execution path
        run_listener(config_file=options.config_file)


def initialize_treeherder_submission(host, protocol, client, secret, dry_run):
    # 1) Object to submit jobs
    th = TreeherderSubmitter(
        host=host,
        protocol=protocol,
        treeherder_client_id=client,
        treeherder_secret=secret,
        dry_run=dry_run,
    )
    return TreeherderJobFactory(submitter=th)


def _determine_repo_revision(data):
    ''' Return repo_name and revision based on Pulse message data.'''
    query = TreeherderApi()

    if 'project' in data:
        repo_name = data['project']
        if 'job_id' in data:
            revision = query.query_revision_for_job(
                repo_name=repo_name,
                job_id=data['job_id']
            )
        elif 'resultset_id' in data:
            revision = query.query_revision_for_resultset(
                repo_name=repo_name,
                resultset_id=data['resultset_id']
            )
        else:
            LOG.error('We should have been able to determine the repo and revision')
            sys.exit(1)
    elif data['_meta']['exchange'] == 'exchange/build/normalized':
        repo_name = data['payload']['tree']
        revision = data['payload']['revision']

    return repo_name, revision


# Pulse consumer's callback passes only data and message arguments
# to the function, we need to pass dry-run to route
def message_handler(data, message, *args, **kwargs):
    ''' Handle pulse message, log to file, upload and report to Treeherder

    * Each request is logged into a unique file
    XXX: Upload each logging file into S3
    * Report the request to Treeherder first as running and then as complete
    '''
    # 1) Start logging and timing
    file_path = start_logging()
    start_time = default_timer()

    # 2) Report as running to Treeherder
    repo_name, revision = _determine_repo_revision(data)

    if SUBMIT_TO_TREEHERDER:
        job = JOB_FACTORY.create_job(
            repository=repo_name,
            revision=revision,
            add_platform_info=True,
            dry_run=DRY_RUN,
            **PULSE_ACTIONS_JOB_TEMPLATE
        )
        JOB_FACTORY.submit_running(job)

    LOG.info('#### New request ####.')
    # 3) process the message
    try:
        route(data, message, DRY_RUN, TREEHERDER_HOST, ACKNOWLEDGE)
    except Exception as e:
        LOG.exception(e)

    # 4) We're done - let's stop the logging
    LOG.info('Message {}, took {} seconds to execute'.format(
        str(data),
        str(int(int(default_timer() - start_time)))))

    LOG.info('#### End of request ####.')
    end_logging(file_path)

    # XXX: 5) Upload logs to S3

    # 6) Submit results to Treeherder
    if SUBMIT_TO_TREEHERDER:
        bugzilla_link = "https://bugzilla.mozilla.org/enter_bug.cgi?assigned_to=nobody%40mozilla.org&cc=armenzg%40mozilla.com&comment=Provide%20link.&component=General&form_name=enter_bug&product=Testing&short_desc=pulse_actions%20-%20Brief%20description%20of%20failure"  # flake8: noqa

        JOB_FACTORY.submit_completed(
            job=job,
            result='success',  # XXX: This should be a constant
            job_info_details_panel=[
                {
                    "url": bugzilla_link,
                    "value": "bug template",
                    "content_type": "link",
                    "title": "File bug"
                },
            ],
            log_references=[
                {
                    "url": "http://people.mozilla.org/~armenzg/foo.txt",
                    # Irrelevant name since we're not providing a custom log viewer parser
                    # and we're setting the status to 'parsed'
                    "name": "foo",
                    "parse_status": "parsed"
                }
            ],
        )


def route(data, message, dry_run, treeherder_host, acknowledge):
    ''' We need to map every exchange/topic to a specific handler.

    We return if the request was processed succesfully or not
    '''
    # XXX: This is not ideal; we should define in the config which exchange uses which handler
    # XXX: Specify here which treeherder host
    if 'job_id' in data:
        exit_code = treeherder_job_event.on_event(data, message, dry_run, treeherder_host,
                                                  acknowledge)
    elif 'buildernames' in data:
        exit_code = treeherder_runnable.on_runnable_job_event(data, message, dry_run,
                                                              treeherder_host, acknowledge)
    elif 'resultset_id' in data:
        exit_code = treeherder_resultset.on_resultset_action_event(data, message, dry_run,
                                                                   treeherder_host, acknowledge)
    elif data['_meta']['exchange'] == 'exchange/build/normalized':
        exit_code = talos.on_event(data, message, dry_run, acknowledge)
    else:
        LOG.error("Exchange not supported by router (%s)." % data)

    return exit_code


def run_listener(config_file):
    if 'PULSE_USER' not in os.environ or \
       'PULSE_PW' not in os.environ:

        LOG.error('You always need PULSE_{USER,PW} in your environment even '
                  'if running on dry run mode.')
        sys.exit(1)

    consumer = create_consumer(
        user=os.environ['PULSE_USER'],
        password=os.environ['PULSE_PW'],
        config_file_path=config_file,
        process_message=message_handler,
    )

    while True:
        try:
            consumer.listen()
        except KeyboardInterrupt:
            sys.exit(1)
        except:
            traceback.print_exc()


def parse_args(argv=None):
    parser = ArgumentParser()
    parser.add_argument('--acknowledge', action="store_true", dest="acknowledge",
                        help="Acknowledge even if running on dry run mode.")

    parser.add_argument('--config-file', dest="config_file", type=str)

    parser.add_argument('--debug', action="store_true", dest="debug",
                        help="Record debug messages.")

    parser.add_argument('--dry-run', action="store_true", dest="dry_run",
                        help="Test without actual making changes.")

    parser.add_argument('--memory-saving', action='store_true', dest="memory_saving",
                        help='Enable memory saving. It is good for Heroku')

    parser.add_argument('--replay-file', dest="replay_file", type=str,
                        help='You can specify a file with saved pulse_messages to process')

    parser.add_argument('--submit-to-treeherder', action="store_true", dest="submit_to_treeherder",
                        help="Submit to treeherder even if running on dry run mode.")

    parser.add_argument('--treeherder-host', dest="treeherder_host", type=str,
                        help='You can specify a treeherder host to use instead of reading the '
                             'value from a config file.')

    options = parser.parse_args(argv)

    if options.config_file and options.treeherder_host:
        # treeherder_host can be mistakenly set to two different values if we allow for this
        raise Exception('Do not use --treeherder-host with --config-file')

    return options


if __name__ == '__main__':
    main()
