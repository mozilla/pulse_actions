import json
import ijson.backends.yajl2 as ijson
import logging
import os

from pulse_actions.handlers import config
from argparse import ArgumentParser

from mozillapulse.config import PulseConfiguration
from mozillapulse.consumers import GenericConsumer

logging.basicConfig(format='%(levelname)s:\t %(message)s')
LOG = logging.getLogger()


class PulseConsumer(GenericConsumer):
    """
    Creates a consumer object for the given exchange.

    Documentation for the exchanges:
    https://wiki.mozilla.org/Auto-tools/Projects/Pulse/Exchanges
    """

    def __init__(self, exchange, **kwargs):
        super(PulseConsumer, self).__init__(
            PulseConfiguration(**kwargs), exchange, **kwargs)


def run_pulse(exchange, topic, event_handler, topic_base, dry_run=True):
    """
    Listen to a pulse exchange in a infinite loop.

    Call event_handler on every message.
    """

    label = topic_base
    user = os.environ.get('PULSE_USER')
    password = os.environ.get('PULSE_PW')
    pulse_args = {
        'applabel': label,
        'topic': topic,
        'durable': True,
        'user': user,
        'password': password
    }

    # Pulse consumer's callback passes only data and message arguments
    # to the function, we need to pass dry-run
    def handler_with_dry_run(data, message):
        return event_handler(data, message, dry_run)

    pulse = PulseConsumer(exchange,
                          callback=handler_with_dry_run,
                          **pulse_args)
    LOG.info('Listening on %s, with topic %s', exchange, topic)

    while True:
        pulse.listen()


def load_config():
    LOG.setLevel(logging.INFO)
    # requests is too noisy
    logging.getLogger("requests").setLevel(logging.WARNING)

    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, 'run_time_config.json')
    with open(config_path, 'r') as config_file:
        options = json.load(config_file)

    return options


def run_exchange_topic(topic_base):
    options = load_config()
    # Finding the right event handler for the given exchange and topic
    try:
        handler_data = config.HANDLERS_BY_EXCHANGE[options[topic_base]['exchange']]
        handler_function = handler_data[topic_base]
    except KeyError:
        LOG.error("We don't have an event handler for %s with topic %s.",
                  options[topic_base]['exchange'], options[topic_base]['topic'])
        exit(1)

    run_pulse(
        exchange=options[topic_base]['exchange'],
        topic=options[topic_base]['topic'],
        event_handler=handler_function,
        topic_base=topic_base,
        dry_run=True)


def parse_args(argv=None):
    parser = ArgumentParser()
    parser.add_argument("--topic-base",
                        required=True,
                        dest="topic_base",
                        type=str,
                        help="Identifier for exchange and topic to be listened to.")
    options = parser.parse_args(argv)
    return options


def main():
    options = parse_args()
    run_exchange_topic(options.topic_base)


if __name__ == '__main__':
    main()
