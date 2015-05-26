import json
import logging
import os

import config

from argparse import ArgumentParser
from mozillapulse.config import PulseConfiguration
from mozillapulse.consumers import GenericConsumer


logging.basicConfig(format='%(asctime)s %(levelname)s:\t %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S')
LOG = logging.getLogger()

CREDENTIALS_PATH = os.path.expanduser('~/.mozilla/mozci/pulse_credentials.json')
with open(CREDENTIALS_PATH, 'r') as f:
    CREDENTIALS = json.load(f)


def parse_args(argv=None):
    """Parse command line options."""
    parser = ArgumentParser()

    parser.add_argument("exchange")
    parser.add_argument("topic")

    options = parser.parse_args(argv)
    return options

    
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
    """Listen to a pulse exchange in a infinite loop. Call event_handler on every message."""

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
    options = parse_args()
    
    LOG.setLevel(logging.INFO)
    # requests is too noisy
    logging.getLogger("requests").setLevel(logging.WARNING)

    # Finding the right event handler for the given exchange and topic
    topic_base = options.topic.split('.')[0]
    try:
        handler_function = config.HANDLERS_BY_EXCHANGE[options.exchange][topic_base]
    except KeyError:
        LOG.error("We don't have an event handler for %s with topic %s." % (options.exchange, options.topic)
        exit(1)

    run_pulse(options.exchange, handler_function, options.topic, dry_run=True)
