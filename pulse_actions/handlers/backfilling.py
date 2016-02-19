"""
This module is for the following use case:

 - Automatic backfilling:

    * If we use pulse_actions to listen to mozilla-inbound finished
      *test* jobs, we should be able to re-trigger a job a couple of
      times (similar to what trigger bot does on try) and backfill
      back to the last known good

    * Notice that trigger bot has conditions on when to stop
      re-triggering more than needed
"""
import logging

from pulse_actions.utils.misc import filter_invalid_builders

from mozci import query_jobs
from mozci.errors import PushlogError
from mozci.mozci import (
    find_backfill_revlist,
    trigger_range,
)
from mozci.query_jobs import FAILURE, WARNING
from mozci.sources import buildjson
from requests.exceptions import ConnectionError

LOG = logging.getLogger()

# Current SETA skip level defined in here:
# http://mxr.mozilla.org/build/source/buildbot-configs/mozilla-tests/config_seta.py#9
# XXX: Fix hardcoding in https://github.com/mozilla/pulse_actions/issues/29
MAX_REVISIONS = 7


def on_event(data, message, dry_run):
    """Automatically backfill failed jobs."""
    # Cleaning mozci caches
    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}
    payload = data["payload"]
    status = payload["status"]
    buildername = payload["buildername"]

    # Backfill a failed job
    if status in [FAILURE, WARNING]:
        buildername = filter_invalid_builders(buildername)

        # Treeherder can send us invalid builder names
        # https://bugzilla.mozilla.org/show_bug.cgi?id=1242038
        if buildername is None:
            if not dry_run:
                # We need to ack the message to remove it from our queue
                message.ack()
            return

        revision = payload["revision"]
        LOG.info("**")  # visual separator
        LOG.info("Failed job found at revision %s. Buildername: %s",
                 revision, buildername)

        try:
            # We want to ensure 1 appearance of the job on every revision
            revlist = find_backfill_revlist(
                revision=revision,
                max_revisions=MAX_REVISIONS,
                buildername=buildername)

            trigger_range(
                buildername=buildername,
                revisions=revlist[1:],
                times=1,
                dry_run=dry_run,
                trigger_build_if_missing=False
            )

            if not dry_run:
                # We need to ack the message to remove it from our queue
                message.ack()

        except ConnectionError:
            # The message has not been acked so we will try again
            LOG.warning("Connection error. Trying again")

        except PushlogError, e:
            # Unable to retrieve pushlog data. Please check repo_url and revision specified.
            LOG.warning(str(e))

        except Exception, e:
            # The message has not been acked so we will try again
            LOG.warning(str(e))
            raise
    else:
        if not dry_run:
            # We need to ack the message to remove it from our queue
            message.ack()

        LOG.debug("'%s' with status %i. Nothing to be done.",
                  buildername, status)
