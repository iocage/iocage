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

import pytest


require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


@require_root
@require_zpool
def test_01_stop_rc_jails(invoke_cli, resource_selector):
    invoke_cli(
        ['stop', '--rc'],
        'Failed to stop --rc jails'
    )

    for jail in resource_selector.rcjails:
        assert jail.running is False, f'Failed to stop {jail}'


@require_root
@require_zpool
def test_02_stop(resource_selector, invoke_cli, skip_test):
    running_jails = resource_selector.running_jails
    skip_test(not running_jails)

    for jail in running_jails:
        invoke_cli(
            ['stop', jail.name],
            f'Failed to stop {jail}'
        )

        assert jail.running is False, f'Failed to stop {jail}'


@require_root
@require_zpool
def test_03_test_force_flag_stopping_jail(
    release, jail, invoke_cli, write_file, remove_file
):
    # Let's create our script file first
    script_file = '/tmp/test_stop_force_flag_test'
    test_file = '/tmp/test_stop_force_flag_file'
    write_file(
        script_file,
        f'#!/bin/sh\ntouch {test_file}'
    )

    os.chmod(script_file, 0o100)

    try:
        invoke_cli([
            'create', '-r', release, '-n', 'stop_force_flag_test',
            f'exec_prestop="{script_file}"'
        ])

        jail = jail('stop_force_flag_test')
        assert jail.exists is True

        invoke_cli(
            ['start', jail.name],
            'Failed to start stop_force_flag_test'
        )
        assert jail.running is True

        invoke_cli(
            ['stop', '-f', jail.name],
            'Failed to stop Jail'
        )
        invoke_cli(
            ['set', 'exec_prestop="/usr/bin/true"', jail.name]
        )

        assert jail.running is False
        assert not os.path.exists(test_file),\
            f'Pre-stop services being executed'

    finally:
        remove_file(script_file)
        remove_file(test_file)
