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
import re
import subprocess

import pytest

import iocage_lib.ioc_common


def pytest_addoption(parser):
    parser.addoption(
        '--zpool', action='store', default=None,
        help='Specify a zpool to use.'
    )
    parser.addoption(
        '--release', action='store', default='12.2-RELEASE',
        help='Specify a RELEASE to use.'
    )
    parser.addoption(
        '--server', action='store', default='download.freebsd.org',
        help='FTP server to login to.'
    )
    parser.addoption(
        '--user', action='store', default='anonymous',
        help='The user to use for fetching.'
    )
    parser.addoption(
        '--password', action='store', default='anonymous@',
        help='The password to use for fetching.'
    )
    parser.addoption(
        '--http', action='store_true',
        help='Have --server define a HTTP server instead.'
    )
    parser.addoption(
        '--noupdate', action='store_true',
        help='Decide whether or not to update the fetch to the latest '
             'patch level.'
    )
    parser.addoption(
        '--auth', action='store', default=None,
        help='Authentication method for HTTP fetching. Valid'
        ' values: basic, digest'
    )
    parser.addoption(
        '--file', action='store_true',
        help='Use a local file directory for root-dir instead of '
        'FTP or HTTP.'
    )
    parser.addoption(
        '--root-dir', action='store',
        help='Root directory containing all the RELEASEs for fetching.'
    )
    parser.addoption(
        '--jail_ip', action='store', default=None,
        help='Static IP to use creating jails'
    )
    parser.addoption(
        '--dhcp', action='store_true', default=False,
        help='Use DHCP for creating jails'
    )
    parser.addoption(
        '--upgrade', action='store_true', default=False,
        help='Decide whether or not to run upgrade tests'
    )
    parser.addoption(
        '--ping_ip', action='store', default='8.8.8.8',
        help='Use --ping_ip for testing connectivity within a jail'
    )
    parser.addoption(
        '--nat', action='store_true', default=False,
        help='Use NAT for creating jails'
    )
    parser.addoption(
        '--image', action='store_true', default=False,
        help='Run image operations (export/import)'
    )


def pytest_runtest_setup(item):
    if 'require_root' in item.keywords and not os.getuid() == 0:
        pytest.skip('Need to be root to run')

    if 'require_zpool' in item.keywords and not item.config.getvalue('zpool'):
        pytest.skip('Need --zpool option to run')

    if 'require_dhcp' in item.keywords and not item.config.getvalue('dhcp'):
        pytest.skip('Need --dhcp option to run')

    if 'require_nat' in item.keywords and not item.config.getvalue('nat'):
        pytest.skip('Need --nat option to run')

    if 'require_upgrade' in item.keywords and not item.config.getvalue(
        'upgrade'
    ):
        pytest.skip('Need --upgrade option to run')

    if (
        'require_jail_ip' in item.keywords
        and not item.config.getvalue('jail_ip')
    ):
        pytest.skip('Need --jail_ip option to run')

    if (
        'require_networking' in item.keywords
        and all(
            not v for v in (
                item.config.getvalue('--dhcp'),
                item.config.getvalue('--jail_ip'),
                item.config.getvalue('--nat')
            )
        )
    ):
        pytest.skip(
            'Need either --dhcp or --jail_ip  or --nat option to run, not all'
        )
    if 'require_image' in item.keywords and not item.config.getvalue('image'):
        pytest.skip('Need --image option to run')


@pytest.fixture
def zpool(request):
    """Specify a zpool to use."""
    return request.config.getoption('--zpool')


@pytest.fixture
def jail_ip(request):
    """Specify a jail ip to use."""
    return request.config.getoption('--jail_ip')


@pytest.fixture
def dhcp(request):
    """Specify if dhcp is to be used."""
    return request.config.getoption('--dhcp')


@pytest.fixture
def nat(request):
    """Specify if nat is to be used."""
    return request.config.getoption('--nat')


@pytest.fixture
def upgrade(request):
    """Specify if upgrade test is to be executed."""
    return request.config.getoption('--upgrade')


@pytest.fixture
def ping_ip(request):
    """Specify ip to be used to test connectivity within a jail"""
    return request.config.getoption('--ping_ip')


@pytest.fixture
def release(request, hardened):
    """Specify a RELEASE to use."""
    release = request.config.getoption('--release')
    if hardened:
        release = release.replace('-RELEASE', '-STABLE')
        release = re.sub(r'\W\w.', '-', release)
    return release


@pytest.fixture
def server(request):
    """FTP server to login to."""
    return request.config.getoption('--server')


@pytest.fixture
def user(request):
    """The user to use for fetching."""
    return request.config.getoption('--user')


@pytest.fixture
def password(request):
    """The password to use for fetching."""
    return request.config.getoption('--password')


@pytest.fixture
def root_dir(request):
    """Root directory containing all the RELEASEs for fetching."""
    return request.config.getoption('--root-dir')


@pytest.fixture
def http(request):
    """Have --server define a HTTP server instead."""
    return request.config.getoption('--http')


@pytest.fixture
def hardened(request):
    """Have fetch expect the default HardeneBSD layout instead."""
    # TODO: This isn't probably being used anywhere except for
    # in release fixture, let's move it there and remove this

    freebsd_version = iocage_lib.ioc_common.checkoutput(['freebsd-version'])

    if 'HBSD' in freebsd_version:
        _hardened = True
    else:
        _hardened = False

    return _hardened


@pytest.fixture
def _file(request):
    """Use a local file directory for root-dir instead of FTP or HTTP."""
    return request.config.getoption('--file')


@pytest.fixture
def auth(request):
    """Authentication method for HTTP fetching. Valid values: basic, digest"""
    return request.config.getoption('--auth')


@pytest.fixture
def noupdate(request):
    """ Decide whether or not to update the fetch to the latest patch level."""
    return request.config.getoption('--noupdate')

@pytest.fixture
def image(request):
    """Run the export and import operations."""
    return request.config.getoption('--image')

@pytest.fixture
def invoke_cli():
    def invoke(cmd, reason=None, assert_returncode=True):
        cmd.insert(0, 'iocage')
        cmd = [str(c) for c in cmd]

        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        reason = f'{reason}: {result.stderr}' if reason else result.stderr

        if assert_returncode:
            # Empty or Template jails that should not be started/stopped but
            # sometimes make it in due to a race
            try:
                reason = reason.decode()
            except AttributeError:
                pass

            if 'execvp: /bin/sh: No such' not in reason:
                assert result.returncode == 0, reason

        result.output = result.stdout.decode('utf-8')

        return result

    return invoke


@pytest.fixture
def write_file():
    def write_to_file(location, data):
        with iocage_lib.ioc_common.open_atomic(location, 'w') as f:
            f.write(data)

    return write_to_file


@pytest.fixture
def remove_file():
    def remove(path):
        if os.path.exists(path):
            os.remove(path)

    return remove


@pytest.fixture
def zfs():
    from tests.data_classes import ZFS
    return ZFS()


@pytest.fixture
def jail():
    from tests.data_classes import Jail
    return Jail


@pytest.fixture
def resource_selector():
    from tests.data_classes import ResourceSelector
    return ResourceSelector()


@pytest.fixture
def skip_test():
    def skip(condition, reason=''):
        # if condition evaluates to True, let's skip the test
        if condition:
            pytest.skip(reason)

    return skip


@pytest.fixture
def freebsd_download_server():
    return f'http://download.freebsd.org/ftp/releases/{os.uname()[4]}'


@pytest.fixture
def parse_rows_output():
    from tests.data_classes import Row

    def _output_list(data, type):
        rows = []
        for index, line in enumerate(data.split('\n')):
            if all(
                    s not in line for s in ('----', '====')
            ) and line and index != 1:
                rows.append(Row(line, type))
        return rows

    return _output_list


@pytest.fixture
def jails_as_rows():
    def _default_jails(resources, **kwargs):
        return [
            resource.convert_to_row(**kwargs)
            for resource in resources
        ]

    return _default_jails


@pytest.fixture
def run_console():
    def _run_console(cmd):
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return proc

    return _run_console
