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
def test_01_debug(invoke_cli):
    invoke_cli(
        ['debug']
    )


@require_root
@require_zpool
def test_02_debug_with_directory_flag(invoke_cli, zfs):
    iocage_dataset = zfs.iocage_dataset

    invoke_cli(
        ['debug', '-d', os.path.join(iocage_dataset['mountpoint'], 'debug2')]
    )


@require_root
@require_zpool
def test_03_verify_debug_directories(resource_selector, zfs):
    iocage_dataset = zfs.iocage_dataset
    directories = [
        os.path.join(iocage_dataset['mountpoint'], d)
        for d in ('debug', 'debug2')
    ]

    files_check = [f'{j}.txt' for j in resource_selector.all_jails] + [
        'host.txt'
    ]

    for directory in directories:
        assert os.path.exists(directory) is True
        assert os.path.isdir(directory) is True
        assert set(os.listdir(directory)) == set(files_check)
