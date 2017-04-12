import logging

from mozci import query_jobs
from mozci.mozci import trigger_all_talos_jobs
from mozci.ci_manager import BuildAPIManager
from mozci.sources import buildjson
from thclient import TreeherderClient

LOG = logging.getLogger(__name__.split('.')[-1])


def ignored(data):
    '''Ite determines if the job will be processed or not.'''
    # We do not handle 'cancel_all' action right now, so skip it.
    if data['action'] == "cancel_all":
        return True
    else:
        return False


def on_event(data, message, dry_run, treeherder_server_url, **kwargs):
    if ignored(data):
        return 0  # SUCCESS

    # Cleaning mozci caches
    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}
    repo_name = data["project"]
    action = data["action"]
    times = data["times"]
    # Pulse gives us resultset_id, we need to get revision from it.
    resultset_id = data["resultset_id"]

    treeherder_client = TreeherderClient(server_url=treeherder_server_url)

    LOG.info("%s action requested by %s on repo_name %s with resultset_id: %s" % (
        data['action'],
        data["requester"],
        data["project"],
        data["resultset_id"])
    )
    revision = treeherder_client.get_resultsets(repo_name, id=resultset_id)[0]["revision"]

    if action == "trigger_missing_jobs":
        mgr = BuildAPIManager()
        mgr.trigger_missing_jobs_for_revision(repo_name, revision, dry_run=dry_run)

    elif action == "trigger_all_talos_jobs":
        trigger_all_talos_jobs(
            repo_name=repo_name,
            revision=revision,
            times=times,
            priority=-1,
            dry_run=dry_run
        )
    else:
        raise Exception(
            'We were not aware of the "{}" action. Please address the code.'.format(action)
        )

    return 0  # SUCCESS
