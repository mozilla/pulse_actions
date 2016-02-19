"""
This module helps with functionality which is common to all handlers.
"""
import logging

from mozci.mozci import valid_builder

LOG = logging.getLogger(__name__)

BUILDERNAME_REPLACEMENTS = [
    ('Rev5 MacOSX Yosemite 10.10', 'Rev7 MacOSX Yosemite 10.10.5'),
    ('TB Rev5 MacOSX Yosemite 10.10', 'TB Rev7 MacOSX Yosemite 10.10.5'),
]


def whitelisted_users(requester):
    return requester in (
        'aleth@instantbird.org',
        'archaeopteryx@coole-files.de',
        'mozilla@digitalimagecorp.de',
        'nigelbabu@gmail.com',
        'philringnalda@gmail.com',
    )


def _possibly_valid_builder(buildername):
    '''Return an equivalent valid builder if it can be found, otherwise, return None.

    Treeherder is sending us old buildernames and in some cases we can return the valid
    builder. We also safe guard when the substitution does not work or needs refreshing.
    '''
    if valid_builder(buildername):
        return buildername

    new_builder = None
    # We might be able to replace the builder for the right one
    # Bug 1242038 - Treeherder sends the wrong buildernames
    for repl in BUILDERNAME_REPLACEMENTS:
        if buildername.startswith(repl[0]):
            new_builder = buildername.replace(repl[0], repl[1])
            LOG.warning('Old builder: %s New builder: %s' %
                        (buildername, new_builder))
            break

    # We either did not replace or the replacement is also invalid
    if new_builder is not None and not valid_builder(new_builder):
        new_builder = None

    return new_builder


def filter_invalid_builders(buildernames):
    '''Remove list of buildernames (or single buildername) without invalid ones.

    It will also output invalid builders.

    Returns the original list only with valid buildernames.
    '''
    if type(buildernames) in (str, unicode):
        return _possibly_valid_builder(buildernames)

    invalid_builders = []
    for b in buildernames:
        validated_builder = _possibly_valid_builder(b)

        if validated_builder is None:
            # We have not been able to substitute it for something valid
            buildernames.remove(b)
            invalid_builders.append(b)

        elif validated_builder != b:
            # We have managed to find its equivalent valid builder
            buildernames.append(validated_builder)

    if invalid_builders:
        LOG.info('Invalid builders: %s' % str(invalid_builders))

    return buildernames
