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


class MessageHandler:

    def __init__(self):
        """Create Publisher"""
        self.user = os.environ.get('PULSE_USER')
        self.password = os.environ.get('PULSE_PW')
        self.publisher = ExperimentalPublisher(user=self.user, password=self.password)

    def publish_message(self, data, routing_key):
        """Publish a message to exchange/adusca/experiment."""
        msg = GenericMessage()
        msg.routing_parts = routing_key.split('.')
        for key, value in data.iteritems():
            msg.set_data(key, value)
        self.publisher.publish(msg)
