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


class MessageHandler:

    def __init__(self, **kwargs):
        """Create Publisher."""
        user, password = get_user_and_password()
        exchange = kwargs.get('exchange', 'exchange/%s/pulse_actions' % user)
        try:
            self.publisher = GenericPublisher(
                config=PulseConfiguration(user=user, password=password),
                exchange=exchange
            )

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
