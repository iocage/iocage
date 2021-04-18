# Copyright (c) 2014-2018, iocage
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

import re

import pytest
import requests

from distutils.version import StrictVersion

require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool
require_upgrade = pytest.mark.require_upgrade
require_nat = pytest.mark.require_nat

JAIL_NAME = 'upgrade_jail'
OLD_RELEASE = '12.1-RELEASE'


@require_root
@require_zpool
@require_nat
@require_upgrade
def test_01_create_jail_with_older_release(invoke_cli, jail):
    invoke_cli(
        ['create', '-r', OLD_RELEASE, '-n', JAIL_NAME, 'nat=1',
         'allow_raw_sockets=1']
    )

    assert jail(JAIL_NAME).exists is True


@require_upgrade
@require_nat
@require_root
@require_zpool
def test_02_upgrade_jail(
        invoke_cli, skip_test, release, jail
):
    jail = jail(JAIL_NAME)

    skip_test(not jail)

    invoke_cli(
        ['upgrade', jail.name, '-r', release]
    )