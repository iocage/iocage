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
import shutil

import pytest
import uuid


require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


def parse_fstab_list_output(data):
    rows = []
    for index, line in enumerate(data.split('\n')):
        if all(s not in line for s in ('----', '====')) and line and index != 1:
            rows.append(
                ' '.join(
                    [s.strip() for s in line.split('|') if s.strip()][1].split()
                )
            )
    return rows


JAIL = None
FAILED = True
SOURCE_DIR = None
DESTINATION_DIR = None


@require_root
@require_zpool
def test_01_add_fstab_entry(invoke_cli, resource_selector, skip_test):
    global JAIL, FAILED, DESTINATION_DIR, SOURCE_DIR

    jails = resource_selector.startable_jails_and_not_running
    skip_test(not jails)

    for jail in jails:
        if not jail.fstab:
            JAIL = jail.name
            break

    skip_test(not JAIL)

    SOURCE_DIR = f'/tmp/{str(uuid.uuid4())[:8]}'
    DESTINATION_DIR = f'/testing_dest{str(uuid.uuid4())[:8]}'
    destination_dir_absolute = os.path.join(
        jail.absolute_path, 'root', DESTINATION_DIR[1:]
    )

    os.makedirs(SOURCE_DIR)
    os.makedirs(destination_dir_absolute)

    invoke_cli([
        'fstab', '-a', jail.name, SOURCE_DIR, DESTINATION_DIR,
        'nullfs', 'rw', 0, 0
    ])

    assert any(destination_dir_absolute in s for s in jail.fstab) is True

    FAILED = False


@require_root
@require_zpool
def test_02_list_fstab_entry(invoke_cli, jail, skip_test):
    global FAILED
    skip_test(FAILED)

    FAILED = True

    result = invoke_cli(
        ['fstab', '-l', JAIL]
    )

    rows = parse_fstab_list_output(result.output)
    fstab = jail(JAIL).fstab

    assert rows == fstab and len(fstab) > 0

    FAILED = False


@require_root
@require_zpool
def test_03_replace_fstab_entry(invoke_cli, jail, skip_test):
    global FAILED
    skip_test(FAILED)

    jail = jail(JAIL)
    fstab = jail.fstab
    skip_test(not fstab)

    entry = fstab[0]
    new_entry = entry.split()
    new_entry[1] = DESTINATION_DIR + 'renamed'

    os.makedirs(
        os.path.join(jail.absolute_path, 'root', new_entry[1][1:])
    )

    invoke_cli([
        'fstab', '-R', 0, jail.name, *new_entry
    ])

    result = invoke_cli(
        ['fstab', '-l', jail.name]
    )
    rows = parse_fstab_list_output(result.output)

    assert len(jail.fstab) > 0

    assert rows[0].split()[1] == jail.fstab[0].split()[1]

    FAILED = False


@require_root
@require_zpool
def test_04_remove_fstab_entry(invoke_cli, jail, skip_test):
    try:
        skip_test(FAILED)

        jail = jail(JAIL)
        fstab = jail.fstab
        assert len(fstab) == 1

        invoke_cli(
            ['fstab', '-r', JAIL, 0]
        )

        assert len(jail.fstab) == 0

    finally:
        if os.path.exists(str(SOURCE_DIR)):
            shutil.rmtree(SOURCE_DIR)


# TODO: We should probably add tests for ensuring that mounting works as well
