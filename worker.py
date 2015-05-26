import json
import logging
import os

from treeherderactions import on_buildbot_event

from mozillapulse.config import PulseConfiguration
from mozillapulse.consumers import GenericConsumer


logging.basicConfig(format='%(asctime)s %(levelname)s:\t %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S')
LOG = logging.getLogger()

CREDENTIALS_PATH = os.path.expanduser('~/.mozilla/mozci/pulse_credentials.json')
with open(CREDENTIALS_PATH, 'r') as f:
    CREDENTIALS = json.load(f)


class PulseConsumer(GenericConsumer):
    """
    Consumer for pulse exchanges.

    Documentation for the exchanges:
    https://wiki.mozilla.org/Auto-tools/Projects/Pulse/Exchanges
    """

    def __init__(self, **kwargs):
        super(PulseConsumer, self).__init__(
            PulseConfiguration(**kwargs), **kwargs)


def run_pulse(exchange, event_handler, topic, dry_run=True):
    """Listen to a pulse exchange in a infinite loop."""

    label = 'pulse_actions'
    user = CREDENTIALS['pulse']['user']
    password = CREDENTIALS['pulse']['password']
    pulse_args = {
        'applabel': label,
        'topic': topic,
        'durable': False,
        'user': user,
        'password': password
    }

    # Pulse consumer's callback passes only data and message arguments
    # to the function, we need to pass dry-run
    def handler_with_dry_run(data, message):
        return event_handler(data, message, dry_run)

    pulse = PulseConsumer(exchange=exchange, callback=handler_with_dry_run, **pulse_args)
    LOG.info('Listening on %s, with topic %s' % (exchange, topic))

    while True:
        pulse.listen()


if __name__ == '__main__':
    LOG.setLevel(logging.INFO)
    # requests is too noisy
    logging.getLogger("requests").setLevel(logging.WARNING)
    run_pulse('exchange/treeherder/v1/job-actions', on_buildbot_event, 'buildbot.#.#', dry_run=True)
