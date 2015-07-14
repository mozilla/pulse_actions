=============
Pulse Actions
=============

This project is a Pulse_ listener that listens to Treeherder's job cancellation and retrigger actions in ``exchange/treeherder/v1/job-actions`` and acts upon them.

What it does
============

* ``worker.py`` listens to ``exchange/treeherder/v1/job-actions`` in an infinite loop.

* When it sees a retrigger actions it makes a retrigger request in buildapi self-serve using ``make_retrigger_request`` from mozci.

* When it sees a cancel action it makes a cancel request in buildapi self-serve using ``make_cancel_request`` from mozci.

* Currently everything is run with ``dry_run=True``, so instead of doing requests the script just logs the requests it would have made.


Current status
==============

* ``worker.py`` reads exchange and topic from ``run_time_config.json``. It then uses ``HANDLERS_BY_EXCHANGE``, a dictionary defined in ``config.py`` to decide what function it will use to handle incoming messages.

* Only buildbot topics (e.g. ``buildbot.#.#`` or ``buildbot.try.retrigger``) in ``exchange/treeherder/v1/job-actions`` are supported for now.

* The functions to deal with Treeherder's job-actions are defined in the module ``treeherderactions.py``


Installing
==========

From GitHub::

    git clone https://github.com/adusca/pulse_actions.git
    cd pulse_actions
    python setup.py develop

From Pypi::

    pip install pulse-actions

Running
=======

First you'll have to create a pulse user in https://pulse.mozilla.org . After that, you should set the PULSE_USER and PULSE_PW environment variables accordingly.

If you installed with Pypi:
---------------------------

If you installed inside a virtualenv (called venv in this example)::

    venv/bin/run-pulse-actions

If you installed globally (not recommended)::

    run-pulse-actions

If you cloned the repo:
-----------------------
::

   python worker.py

Adding more functionality
=========================

The main goal of this project is to act upon messages from  ``exchange/treeherder/v1/job-actions``, but it can be expanded to add more functionality. Here_ is a step-by-step guide for creating a "Hello World" client with pulse_actions.


Requirements
------------

* mozci
* mozillapulse

See bug 1168148_ for more details.

.. _Pulse: https://wiki.mozilla.org/Auto-tools/Projects/Pulse
.. _1168148: https://bugzilla.mozilla.org/show_bug.cgi?id=1168148
.. _Here: https://github.com/adusca/pulse_actions/blob/master/hello_world.md
