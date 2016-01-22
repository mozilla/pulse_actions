"""
This module deals with Treeherder's job-actions exchanges.

- exchange/treeherder/v1/job-actions on buildbot.#.#.
- exchange/treeherder-stage/v1/job-actions on buildbot.#.#.
Exchange documentation:
 https://wiki.mozilla.org/Auto-tools/Projects/Pulse/Exchanges#Treeherder:_Job_Actions
"""
import logging

from pulse_actions.publisher import MessageHandler

from mozci import query_jobs
from mozci.mozci import manual_backfill
from mozci.sources import buildjson
from thclient import TreeherderClient

LOG = logging.getLogger('th_buildbot')
# XXX: This has to be the same as SETA's skip level
MAX_REVISIONS = 7


def on_buildbot_prod_event(data, message, dry_run):
    """Act upon events on the production exchange"""
    return on_buildbot_event(data, message, dry_run, stage=False)


def on_buildbot_stage_event(data, message, dry_run):
    """Act upon events on the stage exchange"""
    return on_buildbot_event(data, message, dry_run, stage=True)


def on_buildbot_event(data, message, dry_run, stage=False):
    """Act upon buildbot events."""
    # Pulse gives us a job_id and a job_guid, we need request_id.
    LOG.info("%s action requested by %s on repo_name %s with job_id: %s" % (
        data['action'],
        data["requester"],
        data["project"],
        data["job_id"])
    )
    # Cleaning mozci caches
    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}

    if stage:
        treeherder_client = TreeherderClient(host='treeherder.allizom.org')
    else:
        treeherder_client = TreeherderClient()
    repo_name = data['project']
    job_id = data['job_id']
    result = treeherder_client.get_jobs(repo_name, id=job_id)
    # If result not found, ignore
    if not result:
        LOG.info("We could not find any result for repo_name: %s and "
                 "job_id: %s" % (repo_name, job_id))
        message.ack()
        return

    result = result[0]
    buildername = result["ref_data_name"]
    resultset_id = result["result_set_id"]
    result_sets = treeherder_client.get_resultsets(repo_name, id=resultset_id)
    revision = result_sets[0]["revision"]
    action = data['action']
    status = None

    # Backfill action
    if action == "backfill":
        manual_backfill(
            revision,
            buildername,
            max_revisions=MAX_REVISIONS,
            dry_run=dry_run
        )
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
    try:
        message_sender.publish_message(pulse_message, routing_key)
    except:
        LOG.warning("Failed to publish message over pulse stream.")
    # We need to ack the message to remove it from our queue
    message.ack()
