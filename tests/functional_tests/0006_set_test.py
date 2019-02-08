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
import re


require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


# Let's perform testing first on different types of jails
# Then we can move on to setting some specific properties and seeing
# do the props work as intended


# TODO: Plugin test left


def _set_and_test_prop(invoke_cli, value, jail, prop='notes'):
    invoke_cli(
        ['set', f'{prop}={value}', jail.name]
    )

    assert jail.config.get(prop) == value, \
        f'Failed to set {prop} value to {value}'


@require_root
@require_zpool
def test_01_set_prop_on_jail(resource_selector, invoke_cli, skip_test):
    jails = resource_selector.jails
    skip_test(not jails)

    _set_and_test_prop(
        invoke_cli, 'foo \"bar\"', jails[0]
    )


@require_root
@require_zpool
def test_02_set_prop_on_thickconfig_jail(
        resource_selector, invoke_cli, skip_test
):
    thickconfig_jails = resource_selector.thickconfig_jails
    skip_test(not thickconfig_jails)

    _set_and_test_prop(
        invoke_cli, 'foo \"bar\"', thickconfig_jails[0]
    )


@require_root
@require_zpool
def test_03_set_prop_on_basejail(resource_selector, invoke_cli, skip_test):
    basejails = resource_selector.basejails
    skip_test(not basejails)

    _set_and_test_prop(
        invoke_cli, 'foo \"bar\"', basejails[0]
    )


@require_root
@require_zpool
def test_04_set_prop_on_template_jail(resource_selector, invoke_cli, skip_test):
    template_jails = resource_selector.template_jails
    skip_test(not template_jails)

    _set_and_test_prop(
        invoke_cli, 'foo \"bar\"', template_jails[0]
    )


@require_root
@require_zpool
def test_04_set_cpuset_prop_on_jail(
    resource_selector, invoke_cli, skip_test, run_console
):
    jails = resource_selector.startable_jails_and_not_running
    skip_test(not jails)

    # We need to get the no of cpus first
    cpuset_output = run_console(['cpuset', '-g', '-s', '0'])
    skip_test(cpuset_output.returncode)

    cpuset_num = re.findall(
        r'.*mask:.*(\d+)$',
        cpuset_output.stdout.decode().split('\n')[0]
    )
    skip_test(not cpuset_num)

    cpuset_num = int(cpuset_num[0])

    # We would like to test following formats now
    # 0,1,2,3
    # 0-2
    # all
    # off
    #
    # However if the num of cpu is only one, we can't do ranges or multiple
    # values in that case

    possible_variations = ['off', 'all']
    if cpuset_num:
        possible_variations.extend([
            f'0-{cpuset_num}',
            f','.join(
                map(
                    str,
                    range(cpuset_num + 1)
                )
            )
        ])

    jail = jails[0]
    for variation in possible_variations:
        _set_and_test_prop(
            invoke_cli, variation, jail, 'cpuset'
        )

    if cpuset_num:
        invoke_cli(
            ['start', jail.name],
            f'Jail {jail} failed to start'
        )

        assert jail.running is True

        jail_cpusets = jail.cpuset
        assert set(jail_cpusets) == set(
            map(int, possible_variations[-1].split(','))
        )

        invoke_cli(
            ['stop', jail.name],
            f'Jail {jail} failed to stop'
        )

        assert jail.running is False
