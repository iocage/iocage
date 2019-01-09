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


require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool

SNAP_NAME = 'snaptest'


@require_root
@require_zpool
def test_01_remove_snapshot(invoke_cli, resource_selector, skip_test):
    jails = resource_selector.all_jails_having_snapshots
    skip_test(not jails)

    snap_jail = None
    for jail in jails:
        if not jail.is_template and not jail.is_cloned and any(
            SNAP_NAME in snap.id for snap in jail.recursive_snapshots
        ):
            snap_jail = jail
            break

    skip_test(not snap_jail)

    remove_snap = None
    for snap in snap_jail.recursive_snapshots:
        if SNAP_NAME in snap.id:
            remove_snap = snap
            break

    assert remove_snap.exists is True

    invoke_cli(
        ['snapremove', '-n', remove_snap.id.split('@')[1], snap_jail.name]
    )

    assert remove_snap.exists is False
