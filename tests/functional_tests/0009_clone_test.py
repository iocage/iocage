# Copyright (c) 2014-2019, iocage
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import pytest


require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


@require_root
@require_zpool
def test_01_cloning_thickconfig_jail(
        resource_selector, skip_test, invoke_cli, jail
):
    jails = resource_selector.thickconfig_jails
    skip_test(not jails)

    thickconfig_jail = jails[0]
    invoke_cli(['stop', '-f', thickconfig_jail.name])

    assert thickconfig_jail.running is False, \
        f'Failed to stop {thickconfig_jail.name}'

    invoke_cli(
        ['clone', thickconfig_jail.name, '-n', 'cloned_jail']
    )

    jail = jail('cloned_jail')

    assert jail.exists is True
    assert thickconfig_jail.path in jail.root_dataset[
        'properties'
    ]['origin']['value']

    # Let's verify config as well
    # Apart from following keys, everything should be same
    keys = ['host_hostuuid', 'host_hostname', 'jail_zfs_dataset']

    conf1, conf2 = thickconfig_jail.config, jail.config
    for key in keys:
        conf1.pop(key)
        conf2.pop(key)

    assert conf1 == conf2, 'Config files do not match for cloned jail'


@require_root
@require_zpool
def test_02_cloning_thickconfig_jail_setting_props(
        resource_selector, skip_test, invoke_cli, jail
):
    jails = resource_selector.thickconfig_jails
    skip_test(not jails)

    thickconfig_jail = jails[0]

    invoke_cli(['stop', '-f', thickconfig_jail.name])

    assert thickconfig_jail.running is False, \
        f'Failed to stop {thickconfig_jail.name}'

    invoke_cli([
        'clone', thickconfig_jail.name, '-n',
        'cloned_jail2', 'notes=check_cloned_note'
    ])

    jail = jail('cloned_jail2')

    assert jail.exists is True
    assert jail.config.get('notes') == 'check_cloned_note'


@require_root
@require_zpool
def test_03_cloning_jail_using_count_flag(
        resource_selector, skip_test, invoke_cli, jail
):
    jails = resource_selector.startable_jails
    skip_test(not jails)

    count = 3
    clone_jail = jails[0]

    invoke_cli(['stop', '-f', clone_jail.name])

    assert clone_jail.running is False, f'Failed to stop {clone_jail.name}'

    invoke_cli([
        'clone', clone_jail.name, '-n',
        'cloned_jail_count_test', '-c', count,
        'notes=cloned_jail'
    ])

    for i in range(1, count + 1):
        cloned_jail = jail(f'cloned_jail_count_test_{i}')
        assert cloned_jail.exists is True
        assert clone_jail.path \
            in cloned_jail.root_dataset['properties']['origin']['value']
