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


# TODO: Probably make a decorator to skip tests if those jails aren't there


def _test_value_and_match_config(jail, key, invoke_cli):
    result = invoke_cli(
        ['get', key, jail.name]
    )

    value = str(jail.config.get(key))
    assert result.output.strip() == value, \
        f'{key}\'s value "{value}" does not match output: {result.output}'


@require_root
@require_zpool
def test_01_get_on_jails(resource_selector, invoke_cli, skip_test):
    jails = resource_selector.jails
    skip_test(not jails)

    _test_value_and_match_config(
        jails[0], 'host_hostuuid', invoke_cli
    )


@require_root
@require_zpool
def test_02_get_on_thickconfig_jails(resource_selector, invoke_cli, skip_test):
    thickconfig_jails = resource_selector.thickconfig_jails
    skip_test(not thickconfig_jails)

    _test_value_and_match_config(
        thickconfig_jails[0], 'dhcp', invoke_cli
    )


@require_root
@require_zpool
def test_03_get_all_flag_on_jails(resource_selector, invoke_cli, skip_test):
    jails = resource_selector.jails
    skip_test(not jails)

    invoke_cli(
        ['get', 'all', jails[0].name]
    )


@require_root
@require_zpool
def test_04_get_jid_flag_on_jails(resource_selector, invoke_cli, skip_test):
    jails = resource_selector.startable_jails_and_not_running
    skip_test(not jails)

    jail = jails[0]
    result = invoke_cli(
        ['get', '-j', jail.name]
    )

    assert result.output.strip() == '-'

    # Jail is not running, let's start it
    invoke_cli(
        ['start', jail.name]
    )

    result = invoke_cli(
        ['get', '-j', jail.name]
    )

    assert jail.jid == int(result.output.strip())

    invoke_cli(
        ['stop', jail.name],
        f'Failed to stop {jail}'
    )

    assert jail.running is False


@require_root
@require_zpool
def test_05_get_state_flag_on_jails(resource_selector, invoke_cli, skip_test):
    jails = resource_selector.startable_jails_and_not_running
    skip_test(not jails)

    jail = jails[0]
    result = invoke_cli(
        ['get', '-s', jail.name]
    )

    assert result.output.strip() == 'down'

    invoke_cli(
        ['start', jail.name]
    )

    assert jail.running is True

    result = invoke_cli(
        ['get', '-s', jail.name]
    )
    assert result.output.strip() == 'up'

    invoke_cli(
        ['stop', jail.name]
    )

    assert jail.running is False


@require_root
@require_zpool
def test_06_get_recursive_flag_on_jails(invoke_cli):
    invoke_cli(
        ['get', '-r', 'dhcp']
    )
