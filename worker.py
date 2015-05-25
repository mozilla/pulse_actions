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

SELF_SERVE_URL = 'https://secure.pub.build.mozilla.org/buildapi/self-serve'


class TreeherderJobActionsConsumer(GenericConsumer):
    """
    Consumer for exchange/treeherder/v1/job-actions.

    Documentation for the exchange:
    https://wiki.mozilla.org/Auto-tools/Projects/Pulse/Exchanges#Treeherder:_Job_Actions
    """

    def __init__(self, **kwargs):
        super(TreeherderJobActionsConsumer, self).__init__(
            PulseConfiguration(**kwargs), 'exchange/treeherder/v1/job-actions', **kwargs)


CREDENTIALS_PATH = os.path.expanduser('~/.mozilla/mozci/pulse_credentials.json')
with open(CREDENTIALS_PATH, 'r') as f:
    CREDENTIALS = json.load(f)
    CREDENTIALS['LDAP'] = tuple(CREDENTIALS['LDAP'])


def _get_request_id_from_job_id(job_id):
    """Get job_id from buildapi."""
    url = '{}/jobs/{}'.format(SELF_SERVE_URL, job_id)
    req = requests.get(url, auth=CREDENTIALS['LDAP'])
    content = json.loads(req.content)
    return content["request_id"]


def run_pulse(repo_name=None, dry_run=True):
    """
    Listen to Treeherder's job actions on pulse in a infinite loop.


    When a repo_name is given, listen to only that branch, when it's
    not listen to everything.
    """
    label = 'mozci'

    if repo_name is None:
        topic = '#'
    else:
        topic = '#.{}.#'.format(repo_name)

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
        # Pulse gives us job_id and job_guid, buildapi self-serve needs 'request_id'
        job_id = data['job_id']
        request_id = _get_request_id_from_job_id(job_id)

        repo_name = data['project']

        # Retrigger action
        if data['action'] == 'retrigger':
            LOG.info('Retrigger request received for job %s' % job_id)
            make_retrigger_request(repo_name, request_id, dry_run)

        # Cancel action
        elif data['action'] == 'cancel':
            LOG.info('Cancel request received for job %s' % job_id)
            make_cancel_request(repo_name, request_id, dry_run)

    pulse = TreeherderJobActionsConsumer(callback=on_build_event, **pulse_args)
    LOG.info('Listening on exchange/treeherder/v1/job-actions')
    while True:
        pulse.listen()


def make_retrigger_request(repo_name, request_id, dry_run=True, count=1):
    """
    Retrigger a request using buildapi self-serve. Returns a request.

    Builapi documentation:
    POST  /self-serve/{branch}/request
    Rebuild `request_id`, which must be passed in as a POST parameter.
    `priority` and `count` are also accepted as optional
    parameters. `count` defaults to 1, and represents the number
    of times this build  will be rebuilt.
    """
    # For now we should not call this function with dry_run=False
    # Added this assertion to avoid accidents
    assert dry_run
    url = '{}/{}/request'.format(SELF_SERVE_URL, repo_name)
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
    return req

def make_cancel_request(repo_name, request_id, dry_run=True):
    """
    Cancel a request using buildapi self-serve. Returns a request.

    Builapi documentation:
    DELETE /self-serve/{branch}/request/{request_id} Cancel the given request
    """
    # For now we should not call this function with dry_run=False
    # Added this assertion to avoid accidents
    assert dry_run

    url = '{}/{}/request/{}'.format(SELF_SERVE_URL, repo_name, request_id)
    if dry_run:
        LOG.info('We would make a DELETE request to %s.' % url)
        return None

    req = requests.delete(url, auth=CREDENTIALS['LDAP'])
    return req

run_pulse(repo_name=None, dry_run=True)
