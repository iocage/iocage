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

import datetime
import os

import pytest


require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool
require_image = pytest.mark.require_image


@require_root
@require_zpool
@require_image
def test_01_export_jail(invoke_cli, resource_selector, skip_test):
    jails = resource_selector.stopped_jails
    skip_test(not jails)

    jail = jails[0]
    invoke_cli(
        ['export', jail.name]
    )

    assert os.path.isdir(jail.zfs.images_dataset_path) is True, \
        f'{jail.zfs.images_dataset_path} does not exist'

    filename = f'{jail.name}_{datetime.datetime.utcnow().strftime("%F")}.zip'
    list_dir = os.listdir(jail.zfs.images_dataset_path)

    assert filename in list_dir, f'{filename} does not exist'

    assert filename.replace('zip', 'sha256') in list_dir, \
        f'{filename.replace("zip", "sha256")} does not exist'
