import logging

from mozci import query_jobs
from mozci.mozci import trigger_all_talos_jobs
from mozci.ci_manager import BuildAPIManager
from mozci.sources import buildjson
from thclient import TreeherderClient
from pulse_actions.publisher import MessageHandler

LOG = logging.getLogger('th_resultset')


def on_resultset_action_prod_event(data, message, dry_run):
    return on_resultset_action_event(data, message, dry_run, stage=False)


def on_resultset_action_stage_event(data, message, dry_run):
    return on_resultset_action_event(data, message, dry_run, stage=True)


def on_resultset_action_event(data, message, dry_run, stage=False):
    # Cleaning mozci caches
    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}
    repo_name = data["project"]
    action = data["action"]
    times = data["times"]
    # Pulse gives us resultset_id, we need to get revision from it.
    resultset_id = data["resultset_id"]

    if stage:
        treeherder_client = TreeherderClient(host='treeherder.allizom.org')
    else:
        treeherder_client = TreeherderClient()

    # We do not handle 'cancel_all' action right now, so skip it.
    if action == "cancel_all":
        message.ack()
        return
    LOG.info("%s action requested by %s on repo_name %s with resultset_id: %s" % (
        data['action'],
        data["requester"],
        data["project"],
        data["resultset_id"])
    )
    revision = treeherder_client.get_resultsets(repo_name, id=resultset_id)[0]["revision"]
    status = None

    if action == "trigger_missing_jobs":
        mgr = BuildAPIManager()
        mgr.trigger_missing_jobs_for_revision(repo_name, revision, dry_run=dry_run)
        if not dry_run:
            status = 'trigger_missing_jobs request sent'
        else:
            status = 'Dry-mode, no request sent'
    elif action == "trigger_all_talos_jobs":
        trigger_all_talos_jobs(
            repo_name=repo_name,
            revision=revision,
            times=times,
            priority=-1,
            dry_run=dry_run
        )
        if not dry_run:
            status = 'trigger_all_talos_jobs: {0} times request sent with priority'\
                     'lower then normal'.format(times)
        else:
            status = 'Dry-mode, no request sent'

    # Send a pulse message showing what we did
    message_sender = MessageHandler()
    pulse_message = {
        'resultset_id': resultset_id,
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
