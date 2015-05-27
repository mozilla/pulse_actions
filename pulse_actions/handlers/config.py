import treeherderactions

HANDLERS_BY_EXCHANGE = {
    "exchange/treeherder/v1/job-actions" : {
        "topic": {
            "buildbot": treeherderactions.on_buildbot_event
        }
    }
}
