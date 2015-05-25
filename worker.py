import json
import logging
import os
import requests

from mozillapulse.config import PulseConfiguration
from mozillapulse.consumers import GenericConsumer


logging.basicConfig(format='%(asctime)s %(levelname)s:\t %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S')
LOG = logging.getLogger()
LOG.setLevel(logging.INFO)

SELF_SERVE_URL = 'https://secure.pub.build.mozilla.org/buildapi/self-serve/'


class TreeherderJobActionsConsumer(GenericConsumer):

    def __init__(self, **kwargs):
        super(TreeherderJobActionsConsumer, self).__init__(
            PulseConfiguration(**kwargs), 'exchange/treeherder/v1/job-actions', **kwargs)


CREDENTIALS_PATH = os.path.expanduser('~/.mozilla/mozci/pulse_credentials.json')
with open(CREDENTIALS_PATH, 'r') as f:
    CREDENTIALS = json.load(f)


def get_request_id_from_job_id(job_id, job_guid):
    """Pulse gives us job_id and job_guid, buildapi self-serve needs 'request_id'."""
    # Not implemented yet, returning a mock value for testing
    return 'xxxxxx'


def run_pulse():
    """Listen to pulse in a infinite loop."""
    label = 'mozci'
    topic = '#'
    user = CREDENTIALS['pulse']['user']
    password = CREDENTIALS['pulse']['password']
    pulse_args = {
        'applabel': label,
        'topic': topic,
        'durable': False,
        'user': user,
        'password': password
    }

    def on_build_event(data, message):
        """Retrigger a job on retrigger actions, cancel a job on cancel actions."""
        job_id = data['job_id']
        job_guid = data['job_guid']
        request_id = get_request_id_from_job_id(job_id, job_guid)
        repo_name = data['project']

        # Retrigger action
        if data['action'] == 'retrigger':
            make_retrigger_request(repo_name, request_id)

        # Cancel action
        elif data['action'] == 'cancel':
            make_cancel_request(repo_name, request_id)

    pulse = TreeherderJobActionsConsumer(callback=on_build_event, **pulse_args)
    LOG.info('Listening on exchange/treeherder/v1/job-actions')
    while True:
        pulse.listen()


def make_retrigger_request(repo_name, request_id, count=1, dry_run=True):
    """
    Retrigger a request using buildapi self-serve.

    Builapi documentation:
    POST  /self-serve/{branch}/request
    Rebuild `request_id`, which must be passed in as a POST parameter.
    `priority` and `count` are also accepted as optional
    parameters. `count` defaults to 1, and represents the number
    of times this build  will be rebuilt.
    """
    # For now we should not call this function with dry_run=False
    # Added this assertion to avoid acidents
    assert dry_run
    url = '{}{}/request'.format(SELF_SERVE_URL, repo_name)
    payload = {'request_id': request_id,
               'count': count}
    if dry_run:
        LOG.info('We would make a POST request to %s with this payload:' % url)
        LOG.info(payload)
        return None

    req = requests.post(
        url,
        headers={'Accept': 'application/json'},
        data=payload,
        auth=CREDENTIALS['LDAP']
    )


def make_cancel_request(repo_name, request_id, dry_run=True):
    """
    Cancel a request using buildapi self-serve.

    Builapi documentation:
    DELETE /self-serve/{branch}/request/{request_id} Cancel the given request
    """
    # For now we should not call this function with dry_run=False
    # Added this assertion to avoid accidents
    assert dry_run

    url = '{}{}/request/{}'.format(SELF_SERVE_URL, repo_name, request_id)
    if dry_run:
        LOG.info('We would make a DELETE request to %s.' % url)
        return None

    req = requests.delete(url)


run_pulse()
