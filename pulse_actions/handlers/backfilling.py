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


from mozci.sources.pushlog import query_revision_info, query_pushid_range
from mozci.mozci import trigger_range, trigger_job, find_backfill_revlist, \
    query_repo_url_from_buildername
from mozci.query_jobs import FAILURE, WARNING
from mozci.sources import buildjson
from mozci import query_jobs
from mozci.utils import transfer

LOG = logging.getLogger()

MAX_REVISIONS = 5
# Use memory-saving mode
transfer.MEMORY_SAVING_MODE = True


def on_event(data, message, dry_run):
    """Automatically backfill failed jobs."""
    # Cleaning mozci caches
    buildjson.BUILDS_CACHE = {}
    query_jobs.JOBS_CACHE = {}
    payload = data["payload"]
    status = payload["status"]
    buildername = payload["buildername"]

    # Backfill a failed job
    if status == FAILURE:
        revision = payload["revision"]
        LOG.info("Failed job found at revision %s. Buildername: %s", revision, buildername)
        revlist = find_backfill_revlist(revision, MAX_REVISIONS, buildername)
        trigger_range(
                buildername=buildername,
                revisions=revlist,
                times=TIMES,
                dry_run=dry_run,
        )
    else:
        LOG.info("%s with status %i. Nothing to be done", buildername, status)

    # We need to ack the message to remove it from our queue
    message.ack()
