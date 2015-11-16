import logging

from mozci.ci_manager import TaskClusterBuildbotManager
from mozci.sources import buildjson, buildbot_bridge
from mozci import query_jobs
from thclient import TreeherderClient
from pulse_actions.publisher import MessageHandler

logging.basicConfig(format='%(levelname)s:\t %(message)s')
LOG = logging.getLogger()
MEMORY_SAVING_MODE = True


def on_runnable_job_stage_event(data, message, dry_run):
    return on_runnable_job_event(data, message, dry_run, stage=True)


def on_runnable_job_prod_event(data, message, dry_run):
    return on_runnable_job_event(data, message, dry_run, stage=False)


def on_runnable_job_event(data, message, dry_run, stage):
    # Cleaning mozci caches
    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}
    repo_name = data["project"]
    requester = data["requester"]
    resultset_id = data["resultset_id"]
    buildernames = data["buildernames"]

    if stage:
        treeherder_client = TreeherderClient(host='treeherder.allizom.org')
    else:
        treeherder_client = TreeherderClient()

    mgr = TaskClusterBuildbotManager()

    LOG.info("New jobs requested by %s on repo_name %s with resultset_id: %s" %
             (data["requester"], data["project"], data["resultset_id"]))
    resultset = treeherder_client.get_resultsets(repo_name, id=resultset_id)[0]
    revision = resultset["revision"]
    author = resultset["author"]
    status = None

    message_sender = MessageHandler()
    # Everyone can press the button, but only authorized users can trigger jobs
    # TODO: remove this when proper LDAP identication is set up on TH
    if author != requester and not requester.endswith('@mozilla.com'):
        message.ack()

        # We publish a message saying we will not trigger the job
        pulse_message = {
            'resultset_id': resultset_id,
            'requester': requester,
            'status': "Could not determine if the user is authorized, nothing was triggered."}
        routing_key = '{}.{}'.format(repo_name, 'runnable')
        message_sender.publish_message(pulse_message, routing_key)

        raise Exception("Requester %s is not allowed to trigger jobs." %
                        requester)

    builders_graph = buildbot_bridge.buildbot_graph_builder(buildernames, revision)
    mgr.schedule_graph(
        repo_name=repo_name,
        revision=revision,
        builders_graph=builders_graph,
        dry_run=dry_run)

    # Send a pulse message showing what we did
    message_sender = MessageHandler()
    pulse_message = {
        'resultset_id': resultset_id,
        'graph': builders_graph,
        'requester': requester,
        'status': status}
    routing_key = '{}.{}'.format(repo_name, 'runnable')
    message_sender.publish_message(pulse_message, routing_key)

    # We need to ack the message to remove it from our queue
    message.ack()
