import logging

from mozci.mozci import trigger_job
from mozci.sources import buildjson
from mozci import query_jobs
from thclient import TreeherderClient
from pulse_actions.publisher import MessageHandler

logging.basicConfig(format='%(levelname)s:\t %(message)s')
LOG = logging.getLogger()
MEMORY_SAVING_MODE = True


def on_runnable_job_event(data, message, dry_run):
    # Cleaning mozci caches
    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}
    repo_name = data["project"]
    requester = data["requester"]
    resultset_id = data["resultset_id"]
    buildernames = data["buildernames"]

    treeherder_client = TreeherderClient()

    LOG.info("New jobs requested by %s on repo_name %s with resultset_id: %s" %
             (data["requester"], data["project"], data["resultset_id"]))
    resultset = treeherder_client.get_resultsets(repo_name, id=resultset_id)[0]
    revision = resultset["revision"]
    author = resultset["author"]
    status = None

    # Everyone can press the button, but only authorized users can trigger jobs
    # TODO: remove this when proper LDAP identication is set up on TH
    if author != requester and not requester.endswith('@mozilla.com'):
        message.ack()
        raise Exception("Requester %s is not allowed to trigger jobs." %
                        requester)

    for buildername in buildernames:
        trigger_job(revision, buildername, dry_run=dry_run)

        if not dry_run:
            status = 'Request to trigger new jobs sent.'
        else:
            status = 'Dry-mode, no request sent'

    # Send a pulse message showing what we did
    message_sender = MessageHandler()
    pulse_message = {
        'resultset_id': resultset_id,
        'buildernames': buildernames,
        'requester': requester,
        'status': status}
    routing_key = '{}.{}'.format(repo_name, 'runnable')
    message_sender.publish_message(pulse_message, routing_key)

    # We need to ack the message to remove it from our queue
    message.ack()
