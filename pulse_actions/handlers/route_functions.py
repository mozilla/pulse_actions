import pulse_actions.handlers.treeherder_buildbot as treeherder_buildbot
import pulse_actions.handlers.treeherder_resultset as treeherder_resultset
import pulse_actions.handlers.treeherder_runnable as treeherder_runnable


import logging

LOG = logging.getLogger()


def route(data, message, dry_run):
    if 'job_id' in data:
        treeherder_buildbot.on_buildbot_event(data, message, dry_run)
    elif 'buildernames' in data:
        treeherder_runnable.on_runnable_job_event(data, message, dry_run)
    elif 'resultset_id' in data:
        treeherder_resultset.on_resultset_action_event(data, message, dry_run)
    else:
        LOG.error("Exchange not supported by router (%s)." % data)
