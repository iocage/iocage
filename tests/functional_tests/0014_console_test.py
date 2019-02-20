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
import subprocess


require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


@require_root
@require_zpool
def test_01_jail_console(invoke_cli, resource_selector, skip_test):
    jails = resource_selector.startable_jails
    skip_test(not jails)

    jail = jails[0]
    if not jail.running:
        invoke_cli(
            ['start', jail.name]
        )

    assert jail.running is True

    failed = False
    try:
        console = subprocess.Popen(
            ['iocage', 'console', '-f', jail.name],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE
        )
        console.communicate('touch console_test_file'.encode())
    except subprocess.CalledProcessError as e:
        failed = str(e)

    invoke_cli(
        ['stop', jail.name],
        f'Failed to stop {jail.name}'
    )

    assert jail.running is False
    assert failed is False, f'Failed console test: {failed}'

    # Let's verify if the file exists
    assert os.path.exists(
        os.path.join(jail.absolute_path, 'root/root/console_test_file')
    ) is True, f'Failed console test, file not created'
