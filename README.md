# Pulse Actions

The goal of this project is to create a pulse listener that listens to Treeherder's job cancellation and retrigger actions and acts upon them.

### Current status:

worker.py listens to exchange/treeherder/v1/job-actions in an infinite loop. It calls make_retrigger_request when it sees a retrigger action and make_cancel_request when it sees a cancel action. Currently everything is run with dry_run=True, so instead of doing requests the script just logs the requests it would have made.

See [bug 1168148](https://bugzilla.mozilla.org/show_bug.cgi?id=1168148) for more details.
