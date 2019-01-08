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
require_networking = pytest.mark.require_networking


@require_upgrade
@require_networking
@require_root
@require_zpool
def test_01_upgrade_jail(
    invoke_cli, jail, skip_test, release,
    freebsd_download_server, dhcp, jail_ip
):
    # This scenario should work in most cases
    # We can take the value of release specified, go down one version
    # Create a jail for this version and then upgrade to release
    # If it passes as desired, we can mark this as resolved

    req = requests.get(freebsd_download_server)
    assert req.status_code == 200

    releases = [
        StrictVersion(r) for r in re.findall(
            r'href="(\d.*)-RELEASE/"', req.content.decode('utf-8')
        )
    ]
    releases.sort()
    release = StrictVersion(release.split('-')[0])

    skip_test(release not in releases, f'{releases} does contain {release}')

    skip_test(releases.index(release) == 0, f'Cannot execute upgrade test')

    jail = jail('upgrade_test')
    # Let's create a jail now of version releases.index(release) - 1
    if (jail_ip and dhcp) or jail_ip:
        networking = [f'ip4_addr={jail_ip}']
    else:
        networking = ['dhcp=on']

    invoke_cli(
        [
            'create', '-r', f'{releases[releases.index(release) - 1]}-RELEASE',
            '-n', jail.name
        ] + networking
    )

    assert jail.exists is True

    invoke_cli(
        ['upgrade', jail.name, '-r', release]
    )
