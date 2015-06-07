import pulse_actions.handlers.treeherder_buildbot as treeherder_buildbot

HANDLERS_BY_EXCHANGE = {
    "exchange/treeherder/v1/job-actions": {
        "topic": {
            "buildbot": treeherder_buildbot.on_buildbot_event
        }
    }
}
