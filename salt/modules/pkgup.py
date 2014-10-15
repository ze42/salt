'''
Module to help upgrade packages
'''

import re

# salt libs
import salt.utils


__virtualname__ = 'pkgup'


def __virtual__():
    '''
    Confirm this module is on a Debian based system
    '''
    if __grains__.get('os_family', False) != 'Debian':
        return False
    return __virtualname__


def _get_upgradable(packages=None):
    '''
    Utility function to get upgradable packages

    Sample return data:
    { 'pkgname': {'old': '1.2.3-45', 'new': '1.2.3-46', },... }
    '''

    cmd = ['apt-get', '--just-print', ]
    if packages is None:
        cmd.append('dist-upgrade')
    else:
        cmd.append('install')
        cmd.extend(packages)
    out = __salt__['cmd.run_stdout'](cmd, output_loglevel='debug', python_shell=False)

    ret = {
        'summary': {},
        'pkgs': {},
    }

    # 18 upgraded, 20 newly installed, 1 to remove and 3 not upgraded.
    summary = re.search('(?m)([0-9]+) upgraded, '   # upgraded
                    '([0-9]+) newly installed, '    # new
                    '([0-9]+) to remove and '       # removed
                    '([0-9]+) not upgrade.',        # kept back
                    out)
    if not summary:
        ret['summary']['error'] = 'Could not figure out what happened'
    else:
        sumkeys = ['upgrade', 'new', 'remove', 'kept', ]
        _sumget = lambda l, k: l[sumkeys.index(k)]
        for key in sumkeys:
            ret['summary'][key] = int(_sumget(summary.groups(), key))

    # rexp parses lines that look like the following:
    # Remv nginx-naxsi [1.2.1-2.2+wheezy3]
    # Inst gnupg2 (2.0.19-2+deb7u2 Debian:7.6/stable [amd64])
    # Inst qemu-user [1.1.2+dfsg-6a+deb7u4] \
    #        (2.1+dfsg-5~bpo70+1 Debian Backports:/wheezy-backports [amd64])
    #   (?m) multiline (match on each line indivualy)
    rexp = re.compile('(?m)^(?:Remv|Inst) '
                '([^ ]+)'                     # Package name
                '(?: \[([^]]+)\])?'           # Current version
                '(?: \(([^ ]+) (.*)\))?'      # New (+misc) version
                '(?: \[.*\])?$')              # breaks, no idea...
    keys = ['name', 'old', 'new', 'misc', ]
    _get = lambda l, k: l[keys.index(k)]

    upgrades = rexp.findall(out)

    for line in upgrades:
        name = _get(line, 'name')
        ret['pkgs'][name] = {}
        for key in keys[1:]:
            ret['pkgs'][name][key] = _get(line, key)

    # Check we have a matching summary
    if not 'error' in ret['summary']:
        err = (False, False)
        nw = (False, True)
        rm = (True, False)
        up = (True, True)
        count = {err: 0, nw: 0, rm: 0, up: 0, }
        for info in ret['pkgs'].values():
            count[(bool(info['old']), bool(info['new']))] += 1
        errors = []
        if count[err]:
            errors.append('{} packages with no version info'.format(count[err]))
        # sumkeys = ['upgrade', 'new', 'remove', 'kept', ],
        if count[nw] != ret['summary']['new']:
            errors.append('found {0}/{1} new packages'.format(
                        count[nw], ret['summary']['new']))
        if count[rm] != ret['summary']['remove']:
            errors.append('found {0}/{1} packages to remove'.format(
                        count[rm], ret['summary']['remove']))
        if count[up] != ret['summary']['upgrade']:
            errors.append('found {0}/{1} packages to upgrade'.format(
                        count[up], ret['summary']['upgrade']))
        if errors:
            ret['summary']['error'] = '\n'.join(errors)

    if 'error' in ret['summary']:
        print out

    return ret


def list_upgrades(refresh=True):
    '''
    List all available package upgrades.

    CLI Example:

    .. code-block:: bash

        salt '*' pkgup.list_upgrades
    '''
    if salt.utils.is_true(refresh):
        __salt__['pkg.refresh_db']()
    return _get_upgradable()


def list_install(name=None, refresh=False, pkgs=None):
    '''
    List all which packages would be upgraded on package installation.

    CLI Example:

    .. code-block:: bash

        salt '*' pkgup.list_install salt-minion
        salt '*' pkgup.list_install pkgs='["bash", "apt"]'
    '''
    # names: [a-z0-9.:+-]
    if pkgs is None:
        if name is None:
            raise CommandExecutionError('list_install: need a package name')
        pkgs = [name, ]
    if salt.utils.is_true(refresh):
        __salt__['pkg.refresh_db']()
    return _get_upgradable(pkgs)
