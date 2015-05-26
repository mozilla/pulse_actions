import json
import logging
import os
import requests

from mozillapulse.config import PulseConfiguration
from mozillapulse.consumers import GenericConsumer
from mozci.sources.buildapi import make_retrigger_request, make_cancel_request

logging.basicConfig(format='%(asctime)s %(levelname)s:\t %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S')
LOG = logging.getLogger()
LOG.setLevel(logging.INFO)
# requests is too noisy
logging.getLogger("requests").setLevel(logging.WARNING)

TH_ARTIFACT_URL = 'https://treeherder.mozilla.org/api/project/{}/artifact/'


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


def _get_request_id_from_job_id(repo_name, job_id):
    """Get buildapi's request_id from Treeherder's artifact API."""
    artifact_url = TH_ARTIFACT_URL.format(repo_name)
    query_params = {'job_id': job_id,
                    'name': 'buildapi'}
    artifact_content = requests.get(artifact_url, params=query_params).json()
    return artifact_content[0]["blob"]["request_id"]


def run_pulse(repo_name=None, dry_run=True):
    """
    Listen to Treeherder's job actions on pulse in a infinite loop.

    When a repo_name is given, listen to only that branch, when it's
    not listen to everything (on buildbot).
    """
    label = 'mozci'

    if repo_name is None:
        topic = 'buildbot.#.#'
    else:
        topic = 'buildbot.{}.#'.format(repo_name)

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
        # Pulse gives us a job_id and a job_guid, we need request_id.
        repo_name = data['project']
        job_id = data['job_id']
        request_id = _get_request_id_from_job_id(repo_name, job_id)

        # Retrigger action
        if data['action'] == 'retrigger':
            make_retrigger_request(repo_name, request_id, dry_run)

        # Cancel action
        elif data['action'] == 'cancel':
            make_cancel_request(repo_name, request_id, dry_run)

    pulse = TreeherderJobActionsConsumer(callback=on_build_event, **pulse_args)
    LOG.info('Listening on exchange/treeherder/v1/job-actions')
    while True:
        pulse.listen()


run_pulse(repo_name=None, dry_run=True)
