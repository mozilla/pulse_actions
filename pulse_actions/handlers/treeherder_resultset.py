from mozci.mozci import trigger_missing_jobs_for_revision
from thclient import TreeherderClient
from pulse_actions.publisher import MessageHandler
MEMORY_SAVING_MODE = True

def on_resultset_action_event(data, message, dry_run):
    repo_name = data["project"]
    action = data["action"]
    # Pulse gives us resultset_id, we need to get revision from it.
    resultset_id = data["resultset_id"]
    treeherder_client = TreeherderClient()
    revision = treeherder_client.get_resultsets(repo_name, id=resultset_id)[0]["revision"]
    status = None

    if action == "trigger_missing_jobs":
        trigger_missing_jobs_for_revision(repo_name, revision, dry_run=dry_run)
        if not dry_run:
            status = 'trigger_missing_jobs request sent'
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
    message_sender.publish_message(pulse_message, routing_key)
    # We need to ack the message to remove it from our queue
    message.ack()
