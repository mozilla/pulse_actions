"""
This module is currently an experiment in publishing messages to pulse.

It might become a real pulse publisher one day.
"""
import os

from mozillapulse.publishers import GenericPublisher
from mozillapulse.config import PulseConfiguration
from mozillapulse.messages.base import GenericMessage


class ExperimentalPublisher(GenericPublisher):
    def __init__(self, **kwargs):
        super(ExperimentalPublisher, self).__init__(
            PulseConfiguration(**kwargs),
            'exchange/adusca/experiment',
            **kwargs)


def publish_message():
    """Publish a message to exchange/adusca/experiment."""
    user = os.environ.get('PULSE_USER')
    password = os.environ.get('PULSE_PW')
    msg = GenericMessage()
    msg.routing_parts = ['routing_part']
    msg.set_data('something', 'thing')
    publisher = ExperimentalPublisher(user=user, password=password)
    publisher.publish(msg)

publish_message()
