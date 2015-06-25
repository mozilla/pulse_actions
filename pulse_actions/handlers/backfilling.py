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

from mozci.mozci import backfill_revlist, trigger_range, query_repo_url_from_buildername
from mozci.sources.buildapi import FAILURE
from mozci.sources.pushlog import query_revision_info, query_pushid_range

LOG = logging.getLogger()

MAX_REVISIONS = 20
TIMES = 4


def find_backfill_revlist(rev, max_revisions, buildername):
    """Determine which revisions we need to trigger in order to backfill."""
    repo_url = query_repo_url_from_buildername(buildername)
    push_info = query_revision_info(repo_url, rev)
    # A known bad revision
    end_id = int(push_info["pushid"])  # newest revision
    # The furthest we will go to find the last good job
    # We might find a good job before that
    start_id = end_id - max_revisions + 1
    revlist = query_pushid_range(repo_url=repo_url,
                                 start_id=start_id,
                                 end_id=end_id)

    return backfill_revlist(buildername, revlist)


def on_event(data, message, dry_run):
    """Automatically backfill failed jobs."""
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
