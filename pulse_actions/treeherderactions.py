"""
This module provides functions to deal with exchange/treeherder/v1/job-actions.

Exchange documentation:
 https://wiki.mozilla.org/Auto-tools/Projects/Pulse/Exchanges#Treeherder:_Job_Actions
"""
import requests

from mozci.sources.buildapi import make_retrigger_request, make_cancel_request

TH_ARTIFACT_URL = 'https://treeherder.mozilla.org/api/project/{}/artifact/'


def get_request_id_from_job_id(repo_name, job_id):
    """Get buildapi's request_id from Treeherder's artifact API."""
    artifact_url = TH_ARTIFACT_URL.format(repo_name)
    query_params = {'job_id': job_id,
                    'name': 'buildapi'}
    artifact_content = requests.get(artifact_url, params=query_params).json()
    return artifact_content[0]["blob"]["request_id"]


def on_buildbot_event(data, message, dry_run):
    """Act upon buildbot events."""
    # Pulse gives us a job_id and a job_guid, we need request_id.
    repo_name = data['project']
    job_id = data['job_id']
    request_id = get_request_id_from_job_id(repo_name, job_id)

    # Retrigger action
    if data['action'] == 'retrigger':
        make_retrigger_request(repo_name, request_id, dry_run)

    # Cancel action
    elif data['action'] == 'cancel':
        make_cancel_request(repo_name, request_id, dry_run)


def on_taskcluster_event(data, message, dry_run):
    """Act upon taskcluster events."""
    # Not implemented yet, see https://bugzilla.mozilla.org/show_bug.cgi?id=1168148#c7
    pass
