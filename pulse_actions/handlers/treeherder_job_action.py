"""
This module deals with Treeherder's job actions.

Exchange documentation:
 https://wiki.mozilla.org/Auto-tools/Projects/Pulse/Exchanges#Treeherder:_Job_Actions

- exchange/treeherder/v1/job-actions on buildbot.#.#.
- exchange/treeherder-stage/v1/job-actions on buildbot.#.#.


Sample data from Pulse:

{u'action': u'backfill',
 u'build_system_type': u'buildbot',
 u'job_guid': u'cb4c4cf5fdb50bc6b03ec18f50dc19bdf4ce6811',
 u'job_id': 30210861,
 u'project': u'mozilla-inbound',
 u'requester': u'armenzg@mozilla.com',
 u'version': 1}

Sample job from Treeherder:

[{u'build_architecture': u'x86_64',
  u'build_os': u'mac',
  u'build_platform': u'osx-10-10',
  u'build_platform_id': 69,
  u'build_system_type': u'buildbot',
  u'end_timestamp': 1466065682,
  u'failure_classification_id': 4,
  u'id': 30210861,
  u'job_coalesced_to_guid': None,
  u'job_group_description': u'fill me',
  u'job_group_id': 9,
  u'job_group_name': u'Mochitest e10s',
  u'job_group_symbol': u'M-e10s',
  u'job_guid': u'cb4c4cf5fdb50bc6b03ec18f50dc19bdf4ce6811',
  u'job_type_description': u'',
  u'job_type_id': 178,
  u'job_type_name': u'Mochitest e10s Browser Chrome',
  u'job_type_symbol': u'bc2',
  u'last_modified': u'2016-06-16T08:40:39',
  u'machine_name': u't-yosemite-r7-0204',
  u'machine_platform_architecture': u'x86_64',
  u'machine_platform_os': u'mac',
  u'option_collection_hash': u'102210fe594ee9b33d82058545b1ed14f4c8206e',
  u'platform': u'osx-10-10',
  u'platform_option': u'opt',
  u'reason': u'scheduler',
  u'ref_data_name':
      u'Rev7 MacOSX Yosemite 10.10.5 mozilla-inbound opt test mochitest-e10s-browser-chrome-2',
  u'result': u'testfailed',
  u'result_set_id': 33460,
  u'running_eta': 588,
  u'signature': u'931d973dbadb4c8e065d10905fc0b83f0eecb7f8',
  u'start_timestamp': 1466065035,
  u'state': u'completed',
  u'submit_timestamp': 1466065032,
  u'tier': 1,
  u'who': u'tests-mozilla-inbound-yosemite_r7-opt-unittest'}]
"""
import logging

from pulse_actions.utils.misc import filter_invalid_builders

from mozci import query_jobs
from mozci.mozci import manual_backfill
from mozci.sources import buildjson
from thclient import TreeherderClient

LOG = logging.getLogger(__name__.split('.')[-1])


def ignored(data):
    '''It determines if the job will be processed or not.'''
    if data['action'].capitalize() == "Backfill":
        return False
    else:
        return True


def on_event(data, message, dry_run, treeherder_server_url, acknowledge, **kwargs):
    """Act upon Treeherder job events.

    Return if the outcome was successful or not
    """
    exit_code = 0  # SUCCESS

    if ignored(data):
        if acknowledge:
            # We need to ack the message to remove it from our queue
            message.ack()
        return exit_code

    # Cleaning mozci caches
    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}

    treeherder_client = TreeherderClient(server_url=treeherder_server_url)

    action = data['action'].capitalize()
    job_id = data['job_id']
    repo_name = data['project']
    status = None

    # We want to know the status of the job we're processing
    try:
        job_info = treeherder_client.get_jobs(repo_name, id=job_id)[0]
    except IndexError:
        LOG.info("We could not find any job_info for repo_name: %s and "
                 "job_id: %s" % (repo_name, job_id))
        return exit_code

    buildername = job_info["ref_data_name"]

    # We want to know the revision associated for this job
    result_sets = treeherder_client.get_resultsets(repo_name, id=job_info["result_set_id"])
    revision = result_sets[0]["revision"]

    link_to_job = '{}/#/jobs?repo={}&revision={}&selectedJob={}'.format(
        treeherder_server_url,
        repo_name,
        revision,
        job_id
    )

    LOG.info("{} action requested by {} for '{}'".format(
        action,
        data['requester'],
        buildername,
    ))
    LOG.info('Request for {}'.format(link_to_job))

    buildername = filter_invalid_builders(buildername)

    if buildername is None:
        LOG.info('Treeherder can send us invalid builder names.')
        LOG.info('See https://bugzilla.mozilla.org/show_bug.cgi?id=1242038.')
        LOG.warning('Requested job name "%s" is invalid.' % job_info['ref_data_name'])
        exit_code = -1  # FAILURE

    # There are various actions that can be taken on a job, however, we currently
    # only process the backfill one
    elif action == "Backfill":
        exit_code = manual_backfill(
            revision=revision,
            buildername=buildername,
            dry_run=dry_run,
        )
        if not dry_run:
            status = 'Backfill request sent'
        else:
            status = 'Dry-run mode, nothing was backfilled.'
        LOG.debug(status)

    else:
        LOG.error(
            'We were not aware of the "{}" action. Please file an issue'.format(action)
        )
        exit_code = -1  # FAILURE

    if acknowledge:
        # We need to ack the message to remove it from our queue
        message.ack()

    return exit_code
