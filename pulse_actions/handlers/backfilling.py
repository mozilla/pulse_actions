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

from mozci import query_jobs
from mozci.mozci import (
    disable_validations,
    find_backfill_revlist,
    trigger_range,
)
from mozci.query_jobs import FAILURE, WARNING
from mozci.sources import buildjson
from mozci.utils import transfer

LOG = logging.getLogger()

# Current SETA skip level defined in here:
# http://mxr.mozilla.org/build/source/buildbot-configs/mozilla-tests/config_seta.py#9
# XXX: Fix hardcoding in https://github.com/mozilla/pulse_actions/issues/29
MAX_REVISIONS = 7
# This changes the behaviour of mozci in transfer.py
transfer.MEMORY_SAVING_MODE = True


def on_event(data, message, dry_run):
    """Automatically backfill failed jobs."""
    # We need to ack the message to remove it from our queue
    message.ack()

    # Disable mozci's validations
    # XXX: We only to call this once but for now we will put it here
    disable_validations()

    # Cleaning mozci caches
    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}
    payload = data["payload"]
    status = payload["status"]
    buildername = payload["buildername"]

    # Backfill a failed job
    if status in [FAILURE, WARNING]:
        revision = payload["revision"]
        LOG.info("**")  # visual separator
        LOG.info("Failed job found at revision %s. Buildername: %s",
                 revision, buildername)

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
    else:
        LOG.debug("'%s' with status %i. Nothing to be done.",
                  buildername, status)
