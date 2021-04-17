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
import time

import pytest
import uuid


require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


def common_restart_jail(
        invoke_cli, resource_selector, skip_test, command, write_file
):
    jails = resource_selector.startable_jails_and_not_running
    skip_test(not jails)

    jail = jails[0]
    # Let's add a script which will run when the jail shuts down
    script_path = f'/tmp/testing_restart_script{uuid.uuid4()}'
    temp_file_path = f'/tmp/testing_restart_file{uuid.uuid4()}'

    script_absolute_path = os.path.join(
        jail.absolute_path, 'root', script_path[1:]
    )
    write_file(
        script_absolute_path,
        f'#!/bin/sh\ntouch {temp_file_path}'
    )
    assert os.path.exists(script_absolute_path) is True

    os.chmod(script_absolute_path, 0o111)

    invoke_cli(
        ['set', f'exec_stop={script_path}', jail.name]
    )
    assert jail.config.get('exec_stop') == script_path

    invoke_cli(
        ['start', jail.name]
    )
    assert jail.running is True

    command.append(jail.name)
    invoke_cli(
        command
    )
    assert jail.running is True

    assert os.path.exists(
        os.path.join(jail.absolute_path, 'root', temp_file_path[1:])
    ) is True


def common_restart_all_jails(invoke_cli, resource_selector, skip_test, command):
    jails = resource_selector.running_jails
    if not jails:
        jails = resource_selector.startable_jails_and_not_running
        for jail in jails:
            invoke_cli(
                ['start', jail.name]
            )

    skip_test(not jails)

    for jail in jails:
        assert jail.running is True

    command.append('ALL')
    result = invoke_cli(
        command
    )

    for jail in jails:
        if '* Starting empty_jail' in result.output:
            continue

        jail_running = False
        for i in range(0, 5):
            if jail.running:
                jail_running = True
                break
            time.sleep(10)

        assert jail_running is True

    for jail in resource_selector.running_jails:
        invoke_cli(
            ['stop', jail.name]
        )
        assert jail.running is False


@require_root
@require_zpool
def test_01_restart_jail(invoke_cli, resource_selector, skip_test, write_file):
    common_restart_jail(
        invoke_cli, resource_selector, skip_test,
        ['restart'], write_file
    )


@require_root
@require_zpool
def test_02_soft_restart_jail(invoke_cli, resource_selector, skip_test, write_file):
    common_restart_jail(
        invoke_cli, resource_selector, skip_test,
        ['restart', '-s'], write_file
    )


@require_root
@require_zpool
def test_03_restart_all_jails(invoke_cli, resource_selector, skip_test):
    common_restart_all_jails(invoke_cli, resource_selector, skip_test, ['restart'])




@require_root
@require_zpool
def test_04_soft_restart_all_jails(invoke_cli, resource_selector, skip_test):
    common_restart_all_jails(
        invoke_cli, resource_selector, skip_test, ['restart', '-s']
    )