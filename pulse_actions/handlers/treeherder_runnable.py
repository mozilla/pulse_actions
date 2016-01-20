import logging

from mozci import query_jobs
from mozci.ci_manager import TaskClusterBuildbotManager
from mozci.mozci import trigger_job, valid_builder
from mozci.sources import buildjson, buildbot_bridge
from pulse_actions.publisher import MessageHandler
from thclient import TreeherderClient

LOG = logging.getLogger('th_runnable')
MEMORY_SAVING_MODE = True
TREEHERDER = 'https://treeherder.mozilla.org/#/jobs?repo=%(repo)s&revision=%(revision)s'


def on_runnable_job_stage_event(data, message, dry_run):
    return on_runnable_job_event(data, message, dry_run, stage=True)


def on_runnable_job_prod_event(data, message, dry_run):
    return on_runnable_job_event(data, message, dry_run, stage=False)


def _whitelisted_users(requester):
    return requester in ('philringnalda@gmail.com', 'nigelbabu@gmail.com')


def on_runnable_job_event(data, message, dry_run, stage):
    # Cleaning mozci caches
    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}

    if stage:
        treeherder_client = TreeherderClient(host='treeherder.allizom.org')
    else:
        treeherder_client = TreeherderClient()

    # Grabbing data received over pulse
    repo_name = data["project"]
    requester = data["requester"]
    resultset_id = data["resultset_id"]
    buildernames = data["buildernames"]

    resultset = treeherder_client.get_resultsets(repo_name, id=resultset_id)[0]
    revision = resultset["revision"]
    author = resultset["author"]
    status = None

    treeherder_link = TREEHERDER % {'repo': repo_name, 'revision': resultset['revision']}

    LOG.info("New jobs requested by %s for %s" % (requester, treeherder_link))
    LOG.info("List of builders: %s" % str(buildernames))

    message_sender = MessageHandler()
    # Everyone can press the button, but only authorized users can trigger jobs
    # TODO: remove this when proper LDAP identication is set up on TH
    if not (requester.endswith('@mozilla.com') or author == requester or
            _whitelisted_users(requester)):
        # Remove message from pulse queue
        message.ack()

        # We publish a message saying we will not trigger the job
        pulse_message = {
            'resultset_id': resultset_id,
            'requester': requester,
            'status': "Could not determine if the user is authorized, nothing was triggered."}
        routing_key = '{}.{}'.format(repo_name, 'runnable')
        try:
            message_sender.publish_message(pulse_message, routing_key)
        except:
            LOG.error("Failed to publish message over pulse stream.")

        LOG.error("Requester %s is not allowed to trigger jobs." % requester)
        return  # Raising an exception adds too much noise

    # Discard invalid builders
    # Until https://github.com/mozilla/mozilla_ci_tools/issues/423 is fixed
    invalid_builders = []
    for b in buildernames:
        if not valid_builder(b):
            invalid_builders.append(b)
            buildernames.remove(b)

    if invalid_builders:
        LOG.info('Invalid builders: %s' % str(invalid_builders))

    builders_graph, other_builders_to_schedule = buildbot_bridge.buildbot_graph_builder(
        builders=buildernames,
        revision=revision,
        complete=False  # XXX: This can be removed when BBB is in use
    )

    if builders_graph != {}:
        mgr = TaskClusterBuildbotManager()
        mgr.schedule_graph(
            repo_name=repo_name,
            revision=revision,
            metadata={
                'name': 'pulse_actions_graph',
                'description':
                    'Adding new jobs to push via pulse_actions/treeherder for %s.' % requester,
                'owner': requester,
                'source': treeherder_link,
            },
            builders_graph=builders_graph,
            dry_run=dry_run)
    else:
        LOG.info("We don't have anything to schedule through TaskCluster")

    if other_builders_to_schedule:
        # XXX: We should be able to replace this once all Buildbot jobs run through BBB
        # XXX: There might be a work around with
        #      https://github.com/mozilla/mozilla_ci_tools/issues/424
        LOG.info("We're going to schedule these builders via Buildapi: %s" %
                 str(other_builders_to_schedule))
        # This is used for test jobs which need an existing Buildbot job to be scheduled
        for buildername in other_builders_to_schedule:
            trigger_job(revision, buildername)
    else:
        LOG.info("We don't have anything to schedule through Buildapi")

    # Send a pulse message showing what we did
    message_sender = MessageHandler()
    pulse_message = {
        'resultset_id': resultset_id,
        'graph': builders_graph,
        'requester': requester,
        'status': status}
    routing_key = '{}.{}'.format(repo_name, 'runnable')
    try:
        message_sender.publish_message(pulse_message, routing_key)
    except:
        LOG.error("Failed to publish message over pulse stream.")

    # We need to ack the message to remove it from our queue
    message.ack()
