"""
This module deals with exchange/treeherder/v1/job-actions on buildbot.#.#.

Exchange documentation:
 https://wiki.mozilla.org/Auto-tools/Projects/Pulse/Exchanges#Treeherder:_Job_Actions
"""
from mozci.sources.buildapi import make_retrigger_request, make_cancel_request
from pulse_actions.utils.treeherder import get_request_id_from_job_id


def on_buildbot_event(data, message, dry_run):
    """Act upon buildbot events."""
    # Pulse gives us a job_id and a job_guid, we need request_id.
    repo_name = data['project']
    job_id = data['job_id']
    request_id = get_request_id_from_job_id(repo_name, job_id)

    # Re-trigger action
    if data['action'] == 'retrigger':
        make_retrigger_request(repo_name, request_id, dry_run=dry_run)

    # Cancel action
    elif data['action'] == 'cancel':
        make_cancel_request(repo_name, request_id, dry_run=dry_run)

    # We need to ack the message to remove it from our queue
    message.ack()
