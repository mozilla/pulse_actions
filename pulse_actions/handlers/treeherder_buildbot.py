"""
This module deals with exchange/treeherder/v1/job-actions on buildbot.#.#.

Exchange documentation:
 https://wiki.mozilla.org/Auto-tools/Projects/Pulse/Exchanges#Treeherder:_Job_Actions
"""
from mozci.sources.buildapi import make_retrigger_request, make_cancel_request
from pulse_actions.utils.treeherder import get_request_id_from_job_id

from pulse_actions.publisher import MessageHandler


def on_buildbot_event(data, message, dry_run):
    """Act upon buildbot events."""
    # Pulse gives us a job_id and a job_guid, we need request_id.
    repo_name = data['project']
    job_id = data['job_id']
    request_id = get_request_id_from_job_id(repo_name, job_id)
    action = data['action']
    status = None

    # Re-trigger action
    if action == 'retrigger':
        make_retrigger_request(repo_name, request_id, dry_run=dry_run)
        if not dry_run:
            status = 'Retrigger request sent'
        else:
            status = 'Dry-mode, nothing was retriggered'
    # Cancel action
    elif action == 'cancel':
        make_cancel_request(repo_name, request_id, dry_run=dry_run)
        if not dry_run:
            status = 'Cancel request sent'
        else:
            status = 'Dry-run mode, nothing was cancelled'
    # Send a pulse message showing what we did
    message_sender = MessageHandler()
    pulse_message = {
        'job_id': job_id,
        'request_id': request_id,
        'action': action,
        'requester': data['requester'],
        'status': status}
    routing_key = '{}.{}'.format(repo_name, action)
    message_sender.publish_message(pulse_message, routing_key)
    # We need to ack the message to remove it from our queue
    message.ack()
