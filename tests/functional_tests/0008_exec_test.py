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
def test_01_exec_on_jail(resource_selector, skip_test, invoke_cli):
    jails = resource_selector.startable_jails_and_not_running
    skip_test(not jails)

    jail = jails[0]
    invoke_cli(
        ['exec', '-f', jail.name, 'touch', '/tmp/testing_file']
    )

    assert jail.running is True

    assert os.path.exists(
        os.path.join(jail.absolute_path, 'root/tmp/testing_file')
    ) is True


@require_root
@require_zpool
def test_02_exec_jail_user_on_jail(resource_selector, skip_test, invoke_cli):
    jails = resource_selector.startable_jails_and_not_running
    skip_test(not jails)

    jail = jails[0]
    invoke_cli(
        [
            'exec', '-f', jail.name, 'pw', 'useradd', '-n', 'foo', '-s',
            '/bin/sh', '-m'
        ]
    )

    result = invoke_cli(['exec', '-f', '-U', 'foo', jail.name, 'whoami'])
    assert jail.running is True

    # If the jail is started, lots of output we don't care about
    output = result.output.split()[-1].strip()

    assert output == 'foo', f'Jail user "foo" does not match output: {output}'


@require_root
@require_zpool
def test_03_exec_host_user_on_jail(resource_selector, skip_test, invoke_cli):
    jails = resource_selector.startable_jails_and_not_running
    skip_test(not jails)

    jail = jails[0]
    result = invoke_cli(
        ['exec', '-f', '-u', 'nobody', jail.name, 'whoami']
    )
    assert jail.running is True

    # If the jail is started, lots of output we don't care about
    output = result.output.split()[-1].strip()

    assert output == 'nobody', \
        f'Host user "nobody" does not match output: {output}'
