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

import os
import json
import tempfile
import uuid

import pytest


require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool
require_dhcp = pytest.mark.require_dhcp
require_networking = pytest.mark.require_networking

# LIST OF FLAGS in create TO TEST
# [c, C , r, t, p, n, u, b, T, e, s, f]

# TODO: Test different jail props as well


@require_root
@require_zpool
def test_01_create_jail_with_uuid(release, invoke_cli, jail):
    u_flag = str(uuid.uuid4())

    invoke_cli(
        ['create', '-r', release, '-u', u_flag]
    )

    assert jail(u_flag).exists is True


@require_root
@require_zpool
def test_02_create_jail_with_name(release, jail, invoke_cli):
    invoke_cli(
        ['create', '-r', release, '-n', 'name_jail']
    )

    assert jail('name_jail').exists is True


@require_root
@require_zpool
def test_03_create_jail_with_uuid_and_short(release, jail, invoke_cli):
    u_flag = str(uuid.uuid4())

    invoke_cli(
        ['create', '-r', release, '-s', '-u', u_flag]
    )

    assert jail(u_flag[:8]).exists is True


@require_root
@require_zpool
def test_04_create_count_jails_with_name(release, jail, invoke_cli):
    count = 3

    invoke_cli(
        ['create', '-r', release, '-n', 'jail', '-c', count]
    )

    for i in range(1, count + 1):
        assert jail(f'jail_{i}').exists is True, f'jail_{i} does not exist'


@require_root
@require_zpool
def test_05_create_thickconfig_jail(release, jail, invoke_cli):
    invoke_cli(
        ['create', '-r', release, '-n', 'thickconfig', '-C']
    )

    jail = jail('thickconfig')

    assert jail.exists is True
    assert jail.is_thickconfig is True


@require_root
@require_zpool
def test_06_create_empty_jail(jail, invoke_cli):
    invoke_cli(
        ['create', '-e', '-n', 'empty_jail']
    )

    jail = jail('empty_jail')
    assert jail.exists is True
    assert jail.is_empty is True


@require_root
@require_zpool
def test_07_create_basejail(release, jail, invoke_cli):
    invoke_cli(
        ['create', '-r', release, '-n', 'basejail', '-b']
    )

    jail = jail('basejail')
    assert jail.exists is True
    assert jail.is_basejail is True


@require_root
@require_zpool
def test_08_create_thickjail(release, jail, invoke_cli):
    invoke_cli(
        ['create', '-r', release, '-n', 'thickjail', '-T']
    )

    jail = jail('thickjail')
    assert jail.exists is True
    assert jail.is_thickjail is True


@require_root
@require_zpool
@require_dhcp
def test_09_test_dhcp_connectivity_in_jail(release, jail, invoke_cli):
    invoke_cli(
        ['create', '-r', release, '-n', 'dhcp_jail', 'dhcp=on'],
        'Failed to create DHCP Jail'
    )

    jail = jail('dhcp_jail')
    assert jail.exists is True

    # Let's start it and test it's connectivity
    # Starting can have it's own issues - but that would at least tell us
    # that we don't have connectivity in a dhcp created jail

    invoke_cli(
        ['start', 'dhcp_jail'],
        'Failed to start DHCP Jail'
    )

    ip = jail.ip
    assert ip is not None and '0.0.0.0' not in ip


@require_root
@require_zpool
@require_networking
def test_10_create_jail_and_install_packages(release, jail, invoke_cli):
    # FIXME: Test to ensure the packages were installed

    fd, path = tempfile.mkstemp()
    try:
        with os.fdopen(fd, 'w') as tmp:
            tmp.write(json.dumps({
                'pkgs': ['nginx']
            }))

        invoke_cli(
            ['create', '-r', release, '-n', 'pkg_jail', '-p', path]
        )
    finally:
        os.remove(path)

    assert jail('pkg_jail').exists is True


@require_root
@require_zpool
def test_11_create_jail_specifying_few_props(release, jail, invoke_cli):
    invoke_cli(
        ['create', '-r', release, '-n', 'prop_config', 'notes=prop_jail']
    )

    assert jail('prop_config').exists is True


@require_root
@require_zpool
def test_12_create_template_jail(release, jail, invoke_cli):
    invoke_cli(
        ['create', '-r', release, '-n', 'template_jail_base', 'template=yes'],
        'Failed to create template jail base'
    )

    jail = jail('template_jail_base')

    assert jail.exists is True
    assert jail.is_template is True


@require_root
@require_zpool
def test_13_create_jail_from_template_jail(
        invoke_cli, jail, resource_selector, skip_test
):
    template_jails = resource_selector.template_jails
    skip_test(not template_jails)

    invoke_cli(
        ['create', '-t', template_jails[0].name, '-n', 'template_jail'],
        'Failed to create a jail from a template'
    )

    assert jail('template_jail').exists is True


@require_root
@require_zpool
def test_14_create_rc_jail(release, jail, invoke_cli):
    invoke_cli(
        ['create', '-r', release, '-n', 'rc_jail', 'boot=on'],
        'Failed to create and start jail with "boot=on"'
    )

    jail = jail('rc_jail')
    assert jail.exists is True
    assert jail.running is True, 'rc_jail not running on creation as it should'

    # Let's stop this jail and use it for future testing
    invoke_cli(
        ['stop', 'rc_jail'],
        'Failed to stop rc_jail'
    )

    assert jail.running is False, 'Failed to stop rc_jail'
