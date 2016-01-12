.. image:: https://travis-ci.org/mozilla/pulse_actions.svg?branch=master
    :target: https://travis-ci.org/mozilla/pulse_actions
    :alt: Travis-CI Build Status
.. image:: https://requires.io/github/mozilla/pulse_actions/requirements.svg?branch=master
     :target: https://requires.io/github/mozilla/pulse_actions/requirements/?branch=master
     :alt: Requirements Status

=============
Pulse Actions
=============

This project is a Pulse_ listener that connects different parts of Mozilla with Mozilla CI Tools. See the wiki_ for more details.


How it works
============

* ``worker.py`` reads exchange and topic from ``run_time_config.json``. It then uses ``HANDLERS_BY_EXCHANGE``, a dictionary defined in ``config.py`` to decide what function it will use to handle incoming messages.

* The functions to deal with every case are defined in the ``handlers`` module.

* When multiple topics are passed, we use the ``route_functions.py`` to decide which function to call

Existing modes
==============

* manual_backfill: listens to ``exchange/treeherder/v1/job-actions`` with topic ``buildbot.#.backfill``. It calls mozci's ``manual_backfill`` with the appropriate input.

* backfilling: listens to ``exchange/build/normalized`` with topic ``unittest.mozilla-inbound.#``. It automatically backfills failed jobs. Progress in being tracked on bug 1180732_

* resulset_actions: listens to ``exchange/treeherder/v1/resultset-actions``. It calls mozci's ``trigger_missing_jobs`` or ``trigger_all_talos_jobs`` depending on the message.


Installing
==========

From GitHub::

    git clone https://github.com/mozilla/pulse_actions.git
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
From the base folder of repository, run:
::

   python pulse_actions/worker.py --topic-base MODE

Where MODE is a comma-separated list of the modes you in which you wish to run.

Adding more functionality
=========================

Pulse Actions can be expanded to add more functionality. Here_ is a step-by-step guide for creating a "Hello World" client with pulse_actions.


Requirements
------------

* mozci
* mozillapulse


.. _Pulse: https://wiki.mozilla.org/Auto-tools/Projects/Pulse
.. _1180732: https://bugzilla.mozilla.org/show_bug.cgi?id=1180732
.. _wiki: https://wiki.mozilla.org/Auto-tools/Projects/Pulse_actions
.. _Here: https://github.com/adusca/pulse_actions/blob/master/hello_world.md
