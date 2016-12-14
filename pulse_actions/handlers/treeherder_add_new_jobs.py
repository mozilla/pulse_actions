import logging

from pulse_actions.utils.misc import (
    filter_invalid_builders,
    whitelisted_users,
    TREEHERDER
)

from mozci import TaskClusterBuildbotManager, query_jobs
from mozci.mozci import trigger_job
from mozci.sources import buildjson, buildbot_bridge
from mozci.taskcluster import TaskClusterManager, is_taskcluster_label
from thclient import TreeherderClient

LOG = logging.getLogger(__name__.split('.')[-1])
MEMORY_SAVING_MODE = True


def ignored(data):
    '''It determines if the job will be processed or not.'''
    return False


def on_event(data, message, dry_run, treeherder_server_url, acknowledge, **kwargs):
    LOG.info('Acknowledge value: {}'.format(acknowledge))

    if ignored(data):
        if acknowledge:
            # We need to ack the message to remove it from our queue
            LOG.info('Message acknowledged')
            message.ack()
        return 0  # SUCCESS

    # Grabbing data received over pulse
    repo_name = data["project"]
    requester = data["requester"]
    resultset_id = data["resultset_id"]

    if "requested_jobs" in data:
        requested_jobs = data["requested_jobs"]
    else:
        LOG.error("Appropriate job requests not found in the pulse message.")
        return -1

    treeherder_client = TreeherderClient(server_url=treeherder_server_url)
    resultset = treeherder_client.get_resultsets(repo_name, id=resultset_id)[0]
    revision = resultset["revision"]
    author = resultset["author"]

    treeherder_link = TREEHERDER % {
        'treeherder_server_url': treeherder_server_url,
        'repo': repo_name,
        'revision': resultset['revision']
    }
    metadata = {
        'name': 'pulse_actions_graph',
        'description': 'Adding new jobs to push via pulse_actions/treeherder for %s.' % requester,
        'owner': requester,
        'source': treeherder_link,
    }

    if not (requester.endswith('@mozilla.com') or author == requester or
            whitelisted_users(requester)):
        # We want to see this in the alerts
        LOG.warning("Notice that we're letting {} schedule jobs for {}.".format(
            requester, treeherder_link)
        )

    LOG.info("New jobs requested by %s for %s" % (requester, treeherder_link))
    LOG.info("List of requested jobs:")
    for job in requested_jobs:
        LOG.info("- {}".format(job))

    # This is empty strings in non-try pulse messages
    # Remove support for `decisionTaskID` once bug 1286897 fixed.
    decision_task_id = data.get('decision_task_id', data.get('decisionTaskID'))

    # Separate Buildbot buildernames from TaskCluster task labels
    if decision_task_id:
        task_labels = [x for x in requested_jobs if is_taskcluster_label(x, decision_task_id)]
    else:
        task_labels = []

    # Treeherder can send us invalid builder names
    # https://bugzilla.mozilla.org/show_bug.cgi?id=1242038
    buildernames = filter_invalid_builders(list(set(requested_jobs) - set(task_labels)))

    # XXX: In the future handle return codes
    add_taskcluster_jobs(task_labels, decision_task_id, repo_name, dry_run)
    add_buildbot_jobs(repo_name, revision, buildernames, metadata, dry_run)

    if acknowledge:
        # We need to ack the message to remove it from our queue
        LOG.info('Message acknowledged')
        message.ack()

    return 0  # SUCCESS


def add_taskcluster_jobs(task_labels, decision_task_id, repo_name, dry_run):
    if not decision_task_id:
        LOG.warning("The pulse message did not contain the decision task ID."
                    "We can't schedule TaskCluster jobs.")
        # We don't raise an exception because we hope that the Buildbot jobs (if any)
        # will get scheduled.
        return -1

    # Scheduling TaskCluster jobs
    # Make sure that decision task id is not null and task_labels are there to schedule
    if task_labels and len(decision_task_id):
        # We want to prevent API requests to schedule non-Try jobs until we've done
        # a proper security review
        if repo_name != 'try':
            LOG.warning("We don't allow scheduling TaskCluster jobs for non Try repos until "
                        "bug 1286894 is resolved")
            return -1
        else:
            try:
                mgr = TaskClusterManager(dry_run=dry_run)
                mgr.schedule_action_task(decision_id=decision_task_id,
                                         action='action-task',
                                         action_args={'decision_id': decision_task_id,
                                                      'task_labels': ','.join(task_labels)})
            except Exception as e:
                # XXX: Read the following article and determine if we need to improve this
                # https://www.loggly.com/blog/exceptional-logging-of-exceptions-in-python
                LOG.warning(str(e))
                # We don't raise the exception since we hope that at least the Buildbot
                # jobs can be schedule
                return -1

    return 0  # No issues were found


def add_buildbot_jobs(repo_name, revision, buildernames, metadata, dry_run):
    # Cleaning mozci caches
    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}

    if not buildernames:
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
            metadata=metadata,
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
