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

from mozci.mozci import disable_validations
from mozci.utils import transfer
from replay import create_consumer, replay_messages

# This changes the behaviour of mozci in transfer.py
transfer.MEMORY_SAVING_MODE = False
transfer.SHOW_PROGRESS_BAR = False

DRY_RUN = True
LOG = None
TREEHERDER_HOST = 'treeherder.mozilla.org'


def main():
    global DRY_RUN, LOG, TREEHERDER_HOST
    options = parse_args()

    if options.debug:
        LOG = setup_logging(logging.DEBUG)
    else:
        LOG = setup_logging(logging.INFO)

    if options.memory_saving:
        transfer.MEMORY_SAVING_MODE = True

    DRY_RUN = options.dry_run
    if options.config_file:
        # Load information only relevant to pulse_actions
        with open(options.config_file, 'r') as file:
            pulse_actions_config = json.load(file).get('pulse_actions')

            if pulse_actions_config:
                # Inside of some of our handlers we set the Treeherder client
                # We would not want to try to test with a stage config yet
                # we query production instead of stage
                TREEHERDER_HOST = pulse_actions_config['treeherder_host']
            else:
                TREEHERDER_HOST = options.treeherder_host

    # Disable mozci's validations
    disable_validations()
    if options.replay_file:
        replay_messages(
            filepath=options.replay_file,
            process_message=message_handler,
            dry_run=True
        )
    else:
        # Normal execution path
        run_listener(
            config_file=options.config_file,
            dry_run=options.dry_run
        )


# Pulse consumer's callback passes only data and message arguments
# to the function, we need to pass dry-run to route
def message_handler(data, message, *args, **kwargs):
    ''' Handle pulse message, log to file, upload and report to Treeherder

    * Each request is logged into a unique file
    XXX: Upload each logging file into S3
    XXX: Report the job to Treeherder as running and then as complete
    '''
    file_path = start_logging()
    LOG.info('#### New request ####.')
    start_time = default_timer()
    try:
        route(data, message, DRY_RUN, TREEHERDER_HOST)
    except Exception as e:
        LOG.exception(e)

    if not DRY_RUN:
        message.ack()

    LOG.info('Message {}, took {} seconds to execute'.format(
        str(data)[0:150],
        str(int(int(default_timer() - start_time)))))
    end_logging(file_path)
    # XXX: Upload to S3
    # XXX: Report to Treeherder


def route(data, message, dry_run, treeherder_host):
    ''' We need to map every exchange/topic to a specific handler.

    We return if the request was processed succesfully or not
    '''
    # XXX: This is not ideal; we should define in the config which exchange uses which handler
    # XXX: Specify here which treeherder host
    if 'job_id' in data:
        exit_code = treeherder_job_event.on_event(data, message, dry_run, treeherder_host)
    elif 'buildernames' in data:
        exit_code = treeherder_runnable.on_runnable_job_event(data, message, dry_run,
                                                              treeherder_host)
    elif 'resultset_id' in data:
        exit_code = treeherder_resultset.on_resultset_action_event(data, message, dry_run,
                                                                   treeherder_host)
    elif data['_meta']['exchange'] == 'exchange/build/normalized':
        exit_code = talos.on_event(data, message, dry_run)
    else:
        LOG.error("Exchange not supported by router (%s)." % data)

    return exit_code


def run_listener(config_file, dry_run=True):
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
    parser.add_argument('--config-file', dest="config_file", type=str)

    parser.add_argument('--debug', action="store_true", dest="debug",
                        help="Record debug messages.")

    parser.add_argument('--dry-run', action="store_true", dest="dry_run",
                        help="Test without actual making changes.")

    parser.add_argument('--replay-file', dest="replay_file", type=str,
                        help='You can specify a file with saved pulse_messages to process')

    parser.add_argument('--memory-saving', action='store_true', dest="memory_saving",
                        help='Enable memory saving. It is good for Heroku')

    parser.add_argument('--treeherder-host', dest="treeherder_host", type=str,
                        default='treeherder.mozilla.org',
                        help='You can specify a file with saved pulse_messages to process')

    options = parser.parse_args(argv)
    return options


if __name__ == '__main__':
    main()
