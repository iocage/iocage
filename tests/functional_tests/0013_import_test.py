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

import glob
import os
import pytest
import re


require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool
require_image = pytest.mark.require_image


@require_root
@require_zpool
@require_image
def test_01_import_jail(invoke_cli, jail, skip_test, remove_file, zfs):
    images_dataset_path = zfs.images_dataset_path
    list_dir = glob.glob(
        os.path.join(images_dataset_path, '*zip')
    )
    skip_test(
        not list_dir,
        'Empty images dataset path'
    )

    exported_jail = re.findall(
        r'(.*)_\d+-\d+-\d+.zip', list_dir[0]
    )[0].split('/')[-1]

    jail = jail(exported_jail, zfs)
    if jail.exists:
        invoke_cli(
            ['destroy', '-f', exported_jail]
        )

    assert jail.exists is False, f'Failed to destroy {exported_jail}'

    invoke_cli(
        ['import', exported_jail]
    )

    assert jail.exists is True, f'{exported_jail} jail did not import'
