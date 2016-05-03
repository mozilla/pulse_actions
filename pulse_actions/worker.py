import logging
import os
import sys
import traceback

from argparse import ArgumentParser
from timeit import default_timer

import pulse_actions.handlers.treeherder_buildbot as treeherder_buildbot
import pulse_actions.handlers.treeherder_resultset as treeherder_resultset
import pulse_actions.handlers.treeherder_runnable as treeherder_runnable

from pulse_actions.utils.log_util import setup_logging

from mozci.mozci import disable_validations
from mozci.utils import transfer
from replay import create_consumer, replay_messages

# This changes the behaviour of mozci in transfer.py
transfer.MEMORY_SAVING_MODE = True
transfer.SHOW_PROGRESS_BAR = False

LOG = None


def main():
    global LOG
    options = parse_args()

    if options.debug:
        LOG = setup_logging(logging.DEBUG)
    else:
        LOG = setup_logging(logging.INFO)

    # Disable mozci's validations
    disable_validations()
    if not options.replay_file:
        run_listener(options.config_file, options.dry_run)
    else:
        replay_messages(options.replay_file, route, dry_run=True)


def route(data, message, dry_run):
    if 'job_id' in data:
        treeherder_buildbot.on_buildbot_event(data, message, dry_run)
    elif 'buildernames' in data:
        treeherder_runnable.on_runnable_job_prod_event(data, message, dry_run)
    elif 'resultset_id' in data:
        treeherder_resultset.on_resultset_action_event(data, message, dry_run)
    else:
        LOG.error("Exchange not supported by router (%s)." % data)


def run_listener(config_file, dry_run=True):
    # Pulse consumer's callback passes only data and message arguments
    # to the function, we need to pass dry-run
    def handler_with_dry_run(data, message):
        start_time = default_timer()
        route(data, message, dry_run)
        elapsed_time = default_timer() - start_time
        LOG.info('Message {}, took {} seconds to execute'.format(data, str(elapsed_time)))

    consumer = create_consumer(
        user=os.environ['PULSE_USER'],
        password=os.environ['PULSE_PW'],
        config_file_path=config_file,
        handle_message=handler_with_dry_run,
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
    parser.add_argument('--replay-file', dest="replay_file", type=str,
                        help='You can specify a file with saved pulse_messages to process')

    parser.add_argument("--dry-run",
                        action="store_true",
                        dest="dry_run",
                        help="flag to test without actual push.")

    parser.add_argument("--debug",
                        action="store_true",
                        dest="debug",
                        help="set debug for logging.")

    options = parser.parse_args(argv)
    return options


if __name__ == '__main__':
    main()
