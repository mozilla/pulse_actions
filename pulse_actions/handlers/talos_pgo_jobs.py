"""
This module is for the following use case:

 - Talos jobs:

    * Trigger talos jobs twice if they are from PGO build.
"""
import logging

from mozci import query_jobs
from mozci.errors import MissingBuilderError
from mozci.mozci import trigger_talos_jobs_for_build
from mozci.platforms import get_buildername_metadata
from mozci.sources import buildjson

from pulse_actions.utils.misc import filter_invalid_builders

LOG = logging.getLogger(__name__.split('.')[-1])


def ignored(data):
    '''It determines if the request will be processed or not.'''
    try:
        info = get_buildername_metadata(data['payload']['buildername'])
        if info['build_type'] == "pgo" and \
           info['repo_name'] in ('mozilla-inbound', 'fx-team', 'autoland') and \
           info['platform_name'] != 'win64':
            return False
        else:
            return True
    except MissingBuilderError, e:
        LOG.warning(str(e))

        return True


def on_event(data, message, dry_run, acknowledge, **kwargs):
    """
    Whenever PGO builds are completed in mozilla-inbound or fx-team,
    we trigger the corresponding talos jobs twice.
    """
    if ignored(data):
        if acknowledge:
            # We need to ack the message to remove it from our queue
            message.ack()
        LOG.debug("'%s' with status %i. Nothing to be done.",
                  data['payload']['buildername'], data['payload']['status'])
        return 0  # SUCCESS

    # Cleaning mozci caches
    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}
    payload = data["payload"]
    buildername = payload["buildername"]
    revision = payload["revision"]

    # Treeherder can send us invalid builder names
    # https://bugzilla.mozilla.org/show_bug.cgi?id=1242038
    buildername = filter_invalid_builders(buildername)

    if buildername is None:
        if acknowledge:
            # We need to ack the message to remove it from our queue
            message.ack()
        return -1  # FAILURE

    try:

        trigger_talos_jobs_for_build(
            buildername=buildername,
            revision=revision,
            times=2,
            priority=0,
            dry_run=dry_run
        )

        if acknowledge:
            # We need to ack the message to remove it from our queue
            message.ack()

        LOG.info('We triggered talos jobs for the build.')
        return 0  # SUCCESS

    except Exception, e:
        LOG.warning("The message has not been acknowledged so we can retry it.")
        LOG.warning(str(e))
        raise
