import json
import logging
import os
import sys
import traceback

from argparse import ArgumentParser
from timeit import default_timer

import pulse_actions.handlers.treeherder_job_action as treeherder_job_action
import pulse_actions.handlers.treeherder_push_action as treeherder_push_action
import pulse_actions.handlers.treeherder_add_new_jobs as treeherder_add_new_jobs
import pulse_actions.handlers.talos_pgo_jobs as talos_pgo_jobs

from pulse_actions.utils.log_util import (
    end_logging,
    setup_logging,
    start_logging,
)

# Third party modules
from kombu.exceptions import MessageStateError
from mozci.mozci import disable_validations
from mozci.query_jobs import TreeherderApi
from mozci.utils import transfer
from replay import create_consumer, replay_messages
from thsubmitter import (
    JobEndResult,
    TreeherderSubmitter,
    TreeherderJobFactory
)
from tc_s3_uploader import TC_S3_Uploader

# This changes the behaviour of mozci in transfer.py
transfer.MEMORY_SAVING_MODE = False
transfer.SHOW_PROGRESS_BAR = False

# Constants
JOB_SUCCESS = 0
JOB_FAILURE = -1
EXIT_CODE_JOB_RESULT_MAP = {
    JOB_SUCCESS: JobEndResult.SUCCESS,
    JOB_FAILURE: JobEndResult.FAIL
}
FILE_BUG = "https://bugzilla.mozilla.org/enter_bug.cgi?assigned_to=nobody%40mozilla.org&cc=armenzg%40mozilla.com&comment=Provide%20link.&component=General&form_name=enter_bug&product=Testing&short_desc=pulse_actions%20-%20Brief%20description%20of%20failure"  # flake8: noqa
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
# Global variables
LOG = None
TH_SCH_JOB = "Treeherder 'Sch' job"  # This guarantees using a proper filter for Papertrail
# These values are used inside of message_handler
CONFIG = {
    'acknowledge': True,
    'dry_run': 'DRY_RUN' in os.environ,
    'pulse_actions_job_template': {
        'desc': 'This job was scheduled by pulse_actions.',
        'job_name': 'pulse_actions',
        'job_symbol': 'Sch',
        # Even if 'opt' does not apply to us
        'option_collection': 'opt',
        # Used if add_platform_info is set to True
        'platform_info': ('linux', 'other', 'x86_64'),
    },
    'route': True,
    'submit_to_treeherder': False,
    'treeherder_server_url': 'https://treeherder.mozilla.org',
}


def main():
    global CONFIG, LOG, JOB_FACTORY

    # 0) Parse the command line arguments
    options = parse_args()

    # 1) Set up logging
    if options.debug or os.environ.get('LOGGING_LEVEL') == 'debug':
        LOG = setup_logging(logging.DEBUG)
    else:
        LOG = setup_logging(logging.INFO)

    # 2) Check required environment variables
    if options.load_env_variables:
        with open('env_variables.json') as file:
            env_variables = json.load(file)

            for env, value in env_variables.iteritems():
                os.environ[env] = value
                # Do not print the value as it could be a secret
                LOG.info('Set {}'.format(env))

    if not options.dry_run:
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
    if options.config_file and options.treeherder_server_url:
        # treeherder_server_url can be mistakenly set to two different values if we allow for this
        raw_input('Press Ctrl + C if you did not intent to use --treeherder-server-url with --config-file')

    if options.treeherder_server_url:
        CONFIG['treeherder_server_url'] = options.treeherder_server_url

    elif options.config_file:
        with open(options.config_file, 'r') as file:
            # Load information only relevant to pulse_actions
            pulse_actions_config = json.load(file).get('pulse_actions')

            if pulse_actions_config:
                # Inside of some of our handlers we set the Treeherder client
                # We would not want to try to test with a stage config yet
                # we query production instead of stage
                CONFIG['treeherder_server_url'] = pulse_actions_config['treeherder_server_url']

    elif options.dry_run:
        pass

    else:
        LOG.error("Set --treeherder-url if you're not using a config file")
        sys.exit(1)

    # 5) Set few constants which are used by message_handler
    CONFIG['dry_run'] = options.dry_run or options.replay_file is not None

    if options.submit_to_treeherder:
        CONFIG['submit_to_treeherder'] = True
    elif options.dry_run:
        CONFIG['submit_to_treeherder'] = False
    elif os.environ.get('SUBMIT_TO_TREEHERDER'):
        CONFIG['submit_to_treeherder'] = True

    if options.acknowledge:
        CONFIG['acknowledge'] = True
    elif options.dry_run:
        CONFIG['acknowledge'] = False

    if options.do_not_route:
        CONFIG['route'] = False

    # 6) Set up the treeherder submitter
    if CONFIG['submit_to_treeherder']:
        JOB_FACTORY = initialize_treeherder_submission(
            server_url=CONFIG['treeherder_server_url'],
            client=os.environ['TREEHERDER_CLIENT_ID'],
            secret=os.environ['TREEHERDER_SECRET'],
            dry_run=CONFIG['dry_run'],
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


def initialize_treeherder_submission(server_url, client, secret, dry_run):
    # 1) Object to submit jobs
    th = TreeherderSubmitter(
        server_url=server_url,
        treeherder_client_id=client,
        treeherder_secret=secret,
        dry_run=dry_run,
    )
    return TreeherderJobFactory(submitter=th)


def _determine_repo_revision(data, treeherder_server_url):
    ''' Return repo_name and revision based on Pulse message data.'''
    query = TreeherderApi(server_url=treeherder_server_url)

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
    '''
    if CONFIG['route']:
        try:
            route(data=data, message=message, dry_run=CONFIG['dry_run'],
                  treeherder_server_url=CONFIG['treeherder_server_url'],
                  acknowledge=CONFIG['acknowledge'])
        except:
            LOG.exception('Failed to fulfill request.')
    else:
        LOG.info("We're not routing messages")


def start_request(repo_name, revision):
    results = {
        # Set the level to INFO to ensure that no debug messages could leak anything
        # to the public
        'log_path': start_logging(log_level=logging.INFO),
        'start_time': default_timer(),
        'treeherder_job': None
    }

    # 1) Report as running to Treeherder
    if CONFIG['submit_to_treeherder']:
        treeherder_job = JOB_FACTORY.create_job(
            repository=repo_name,
            revision=revision,
            add_platform_info=True,
            dry_run=CONFIG['dry_run'],
            **CONFIG['pulse_actions_job_template']
        )
        try:
            JOB_FACTORY.submit_running(treeherder_job)
            results['treeherder_job'] = treeherder_job
        except:
            LOG.exception("We will skip scheduling a {}".format(TH_SCH_JOB))
            # Even though the default value is None by being explicit we won't regress by mistake
            results['treeherder_job'] = None

    return results


def end_request(exit_code, data, log_path, treeherder_job, start_time):
    '''End logging, upload to S3 and submit to Treeherder'''
    # 1) Let's stop the logging
    LOG.info('Message {}, took {} seconds to execute'.format(
        str(data),
        str(int(int(default_timer() - start_time)))))

    if CONFIG['submit_to_treeherder']:
        if treeherder_job is None:
            LOG.warning("As mentioned above we did not schedule a {}.".format(TH_SCH_JOB))
        else:
            try:
                # XXX: We will add multiple logs in the future
                s3_uploader = TC_S3_Uploader(bucket_prefix='ateam/pulse-action-dev/')
                url = s3_uploader.upload(log_path)
                LOG.info('Log uploaded to {}'.format(url))
            except Exception as e:
                LOG.error(str(e))
                LOG.error("We have failed to upload to S3; Let's not fail to complete the job")
                url = 'http://people.mozilla.org/~armenzg/failure.html'

            JOB_FACTORY.submit_completed(
                job=treeherder_job,
                result=EXIT_CODE_JOB_RESULT_MAP[exit_code],
                job_info_details_panel=[
                    {
                        "url": FILE_BUG,
                        "value": "bug template",
                        "content_type": "link",
                        "title": "File bug"
                    },
                ],
                log_references=[
                    {
                        "url": url,
                        # Irrelevant name since we're not providing a custom log viewer parser
                        # and we're setting the status to 'parsed'
                        "name": "buildbot_text",
                        "parse_status": "parsed"
                    }
                ],
            )
            LOG.info("Created {}.".format(TH_SCH_JOB))

    end_logging(log_path)


def route(data, message, **kwargs):
    ''' We need to map every exchange/topic to a specific handler.'''
    post_to_treeherder = True
    acknowledge = kwargs.get('acknowledge', False)

    # XXX: This is not ideal; we should define in the config which exchange uses which handler
    # XXX: Specify here which treeherder host
    if 'job_id' in data:
        ignored = treeherder_job_action.ignored
        handler = treeherder_job_action.on_event

    elif 'buildernames' in data or 'requested_jobs' in data:
        ignored = treeherder_add_new_jobs.ignored
        handler = treeherder_add_new_jobs.on_event

    elif 'resultset_id' in data:
        ignored = treeherder_push_action.ignored
        handler = treeherder_push_action.on_event

    elif data['_meta']['exchange'] == 'exchange/build/normalized':
        # XXX: Maybe this information could be configured per handler
        post_to_treeherder = False
        ignored = talos_pgo_jobs.ignored
        handler = talos_pgo_jobs.on_event

    else:
        LOG.error("Exchange not supported by router (%s)." % data)


    if ignored(data):
        LOG.info('Message {}'.format(str(data)[:120]))
        if acknowledge:
            message.ack()
    elif not post_to_treeherder:
        try:
            LOG.info('#### New automatic request ####.')
            handler(data=data, message=message, **kwargs)
            LOG.info('Message {}'.format(str(data)))
            LOG.info('#### End of automatic request ####.')
        except MessageStateError as e:
            # I'm trying to fix the improper use of requeue in a previous patch
            LOG.warning(str(e))
        except:
            LOG.exception('Failed automatic action.')

    else:
        # * Each request is logged into a unique file
        # * Upload each log file to S3
        # * Report the request to Treeherder first as running and then as complete
        LOG.info('#### New user request ####.')
        # 1) Log request
        repo_name, revision = _determine_repo_revision(data, CONFIG['treeherder_server_url'])
        end_request_kwargs = start_request(repo_name=repo_name, revision=revision)

        # 2) Process request
        try:
            exit_code = handler(data=data, message=message, repo_name=repo_name,
                                revision=revision, **kwargs)
        except MessageStateError as e:
            # I'm trying to fix the improper use of requeue in a previous patch
            LOG.warning(str(e))
            exit_code = JOB_FAILURE
        except:
            LOG.exception('The handler failed to do is job. We will mark the job as failed')
            exit_code = JOB_FAILURE

        # XXX: Until handlers can guarantee an exit_code
        if not exit_code:
            LOG.warning('The handler did not give us an exit_code')
            exit_code = JOB_SUCCESS

        # 3) Submit results to Treeherder
        end_request(exit_code=exit_code, data=data, **end_request_kwargs)
        LOG.info('#### End of user request ####.')


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

    parser.add_argument('--do-not-route', action="store_true", dest="do_not_route",
                        help='This is useful if you do not care about processing Pulse '
                             'messages but want to test the overall system.')

    parser.add_argument('--load-env-variables', action="store_true", dest="load_env_variables",
                        help='It can be painful having to load all env variables. '
                             'This option will load them from env_variables.txt')

    parser.add_argument('--memory-saving', action='store_true', dest="memory_saving",
                        help='Enable memory saving. It is good for Heroku')

    parser.add_argument('--replay-file', dest="replay_file", type=str,
                        help='You can specify a file with saved pulse_messages to process')

    parser.add_argument('--submit-to-treeherder', action="store_true", dest="submit_to_treeherder",
                        help="Submit to treeherder even if running on dry run mode.")

    parser.add_argument('--treeherder-server-url', dest="treeherder_server_url", type=str,
                        help='You can specify a treeherder server url to use instead of reading the '
                             'value from a config file.')

    options = parser.parse_args(argv)

    return options


if __name__ == '__main__':
    main()
