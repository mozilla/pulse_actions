import logging

from pulse_actions.utils.misc import (
    filter_invalid_builders,
    whitelisted_users,
    TREEHERDER
)

from mozci import TaskClusterBuildbotManager, query_jobs
from mozci.mozci import trigger_job
from mozci.sources import buildjson, buildbot_bridge
from thclient import TreeherderClient

LOG = logging.getLogger(__name__)
MEMORY_SAVING_MODE = True


def ignored(data):
    '''It determines if the job will be processed or not.'''
    return False


def on_event(data, message, dry_run, treeherder_host, acknowledge, **kwargs):
    if ignored(data):
        if acknowledge:
            # We need to ack the message to remove it from our queue
            message.ack()
        return 0  # SUCCESS

    # Cleaning mozci caches
    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}

    treeherder_client = TreeherderClient(host=treeherder_host)

    # Grabbing data received over pulse
    repo_name = data["project"]
    requester = data["requester"]
    resultset_id = data["resultset_id"]
    buildernames = data["buildernames"]

    resultset = treeherder_client.get_resultsets(repo_name, id=resultset_id)[0]
    revision = resultset["revision"]
    author = resultset["author"]

    treeherder_link = TREEHERDER % {
        'host': treeherder_host,
        'repo': repo_name,
        'revision': resultset['revision']
    }

    if not (requester.endswith('@mozilla.com') or author == requester or
            whitelisted_users(requester)):
        # We want to see this in the alerts
        LOG.error("Notice that we're letting %s schedule jobs for %s." % (requester,
                                                                          treeherder_link))

    LOG.info("New jobs requested by %s for %s" % (requester, treeherder_link))
    LOG.info("List of builders:")
    for b in buildernames:
        LOG.info("- %s" % b)

    buildernames = filter_invalid_builders(buildernames)

    # Treeherder can send us invalid builder names
    # https://bugzilla.mozilla.org/show_bug.cgi?id=1242038
    if buildernames is None:
        if acknowledge:
            # We need to ack the message to remove it from our queue
            message.ack()
        return -1  # FAILURE

    builders_graph, other_builders_to_schedule = buildbot_bridge.buildbot_graph_builder(
        builders=buildernames,
        revision=revision,
        complete=False  # XXX: This can be removed when BBB is in use
    )

    if builders_graph != {}:
        mgr = TaskClusterBuildbotManager(dry_run=dry_run)
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
        LOG.info("We're going to schedule these builders via Buildapi.")
        # This is used for test jobs which need an existing Buildbot job to be scheduled
        for buildername in other_builders_to_schedule:
            trigger_job(revision, buildername, dry_run=dry_run)
    else:
        LOG.info("We don't have anything to schedule through Buildapi")

    if acknowledge:
        # We need to ack the message to remove it from our queue
        message.ack()

    return 0  # SUCCESS
