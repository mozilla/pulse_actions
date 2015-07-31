"""
This module deals with exchange/treeherder/v1/job-actions on buildbot.#.#.

Exchange documentation:
 https://wiki.mozilla.org/Auto-tools/Projects/Pulse/Exchanges#Treeherder:_Job_Actions
"""
import logging
from mozci.mozci import manual_backfill
from pulse_actions.utils.treeherder import get_request_id_from_job_id
from thclient import TreeherderClient

from pulse_actions.publisher import MessageHandler

logging.basicConfig(format='%(levelname)s:\t %(message)s')
LOG = logging.getLogger()


def on_buildbot_event(data, message, dry_run):
    """Act upon buildbot events."""
    # Pulse gives us a job_id and a job_guid, we need request_id.
    treeherder_client = TreeherderClient()
    repo_name = data['project']
    job_id = data['job_id']
    result = treeherder_client.get_jobs(repo_name, id=job_id)
    # If result not found, ignore
    if not result:
        LOG.info("We could not find any result for repo_name: %s and job_id: %s" % (repo_name, job_id))
        message.ack()
        return

    result = result[0]
    buildername = result["ref_data_name"]
    resultset_id = result["result_set_id"]
    revision = treeherder_client.get_resultsets(repo_name, id=resultset_id)[0]["revision"]
    action = data['action']
    status = None

    # Backfill action
    if action == "backfill":
        LOG.info("Backfill requested by %s" % data["requester"])
        manual_backfill(revision, buildername, max_revisions=5, dry_run=dry_run)
        if not dry_run:
            status = 'Backfill request sent'
        else:
            status = 'Dry-run mode, nothing was backfilled'
    # Send a pulse message showing what we did
    message_sender = MessageHandler()
    pulse_message = {
        'job_id': job_id,
        'action': action,
        'requester': data['requester'],
        'status': status}
    routing_key = '{}.{}'.format(repo_name, action)
    message_sender.publish_message(pulse_message, routing_key)
    # We need to ack the message to remove it from our queue
    message.ack()
