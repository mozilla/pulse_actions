import pulse_actions.handlers.treeherder_buildbot as treeherder_buildbot
import pulse_actions.handlers.treeherder_resultset as treeherder_resultset
import pulse_actions.handlers.backfilling as backfilling


HANDLERS_BY_EXCHANGE = {
    "exchange/treeherder/v1/job-actions": {
        "buildbot": treeherder_buildbot.on_buildbot_event
    },
    "exchange/treeherder/v1/resultset-actions": {
        "resultset_actions": treeherder_resultset.on_resultset_action_event
    },
    "exchange/build/normalized": {
        "backfilling": backfilling.on_event
    }
}
