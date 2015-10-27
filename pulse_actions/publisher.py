"""
This module is currently an experiment in publishing messages to pulse.

It might become a real pulse publisher one day.
"""
import sys

from pulse_actions.authentication import (
    get_user_and_password,
    AuthenticationError,
)

from mozillapulse.publishers import GenericPublisher
from mozillapulse.config import PulseConfiguration
from mozillapulse.messages.base import GenericMessage


class ExperimentalPublisher(GenericPublisher):
    def __init__(self, user, **kwargs):
        super(ExperimentalPublisher, self).__init__(
            PulseConfiguration(**kwargs),
            'exchange/%s/pulse_actions' % pulse_user,
            **kwargs)


class MessageHandler:

    def __init__(self):
        """Create Publisher."""
        try:
            user, password = get_user_and_password()
            self.publisher = ExperimentalPublisher(
                user=user, password=password)
        except AuthenticationError as e:
            print(e.message)
            sys.exit(1)
        except Exception as e:
            # We continue without posting to pulse
            print('ERROR: We failed to post a pulse message with what we did')
            print(e.message)

    def publish_message(self, data, routing_key):
        """Publish a message to exchange/${pulse_user}/pulse_actions."""
        msg = GenericMessage()
        msg.routing_parts = routing_key.split('.')
        for key, value in data.iteritems():
            msg.set_data(key, value)
        self.publisher.publish(msg)
