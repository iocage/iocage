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


def common_function(invoke_cli, jails, skip_test):
    skip_test(not jails)

    jail = jails[0]
    invoke_cli(
        ['snapshot', jail.name, '-n', SNAP_NAME]
    )

    # We use count because of template and cloned jails
    assert [
        s.id.split('@')[1] for s in jail.recursive_snapshots
    ].count(SNAP_NAME) >= 2


@require_root
@require_zpool
def test_01_snapshot_of_jail(invoke_cli, resource_selector, skip_test):
    common_function(invoke_cli, resource_selector.not_cloned_jails, skip_test)


@require_root
@require_zpool
def test_02_snapshot_of_template_jail(invoke_cli, resource_selector, skip_test):
    common_function(
        invoke_cli, [
            j for j in resource_selector.template_jails if not j.is_cloned
        ], skip_test
    )


@require_root
@require_zpool
def test_03_snapshot_of_cloned_jail(invoke_cli, resource_selector, skip_test):
    common_function(invoke_cli, resource_selector.cloned_jails, skip_test)
