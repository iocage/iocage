# Copyright (c) 2014-2017, iocage
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

from iocage.lib.ioc_common import checkoutput


def pytest_addoption(parser):
    parser.addoption("--zpool", action="store", default=None,
                     help="Specify a zpool to use.")
    parser.addoption("--release", action="store", default="11.0-RELEASE",
                     help="Specify a RELEASE to use.")
    parser.addoption("--server", action="store", default="ftp.freebsd.org",
                     help="FTP server to login to.")
    parser.addoption("--user", action="store", default="anonymous",
                     help="The user to use for fetching.")
    parser.addoption("--password", action="store", default="anonymous@",
                     help="The password to use for fetching.")
    parser.addoption("--http", action="store_true",
                     help="Have --server define a HTTP server instead.")
    parser.addoption("--noupdate", action="store_true",
                     help="Decide whether or not to update the fetch to the"
                          " latest patch level.")
    parser.addoption("--auth", action="store", default=None,
                     help="Authentication method for HTTP fetching. Valid"
                          " values: basic, digest")
    parser.addoption("--file", action="store_true",
                     help="Use a local file directory for root-dir instead of "
                          "FTP or HTTP.")
    parser.addoption(
        "--root-dir", action="store",
        help="Root directory containing all the RELEASEs for fetching.")


def pytest_runtest_setup(item):
    if 'require_root' in item.keywords and not os.getuid() == 0:
        pytest.skip("Need to be root to run")

    if 'require_zpool' in item.keywords and not item.config.getvalue("zpool"):
        pytest.skip("Need --zpool option to run")


@pytest.fixture
def zpool(request):
    """Specify a zpool to use."""
    return request.config.getoption("--zpool")


@pytest.fixture
def release(request):
    """Specify a RELEASE to use."""
    return request.config.getoption("--release")


@pytest.fixture
def server(request):
    """FTP server to login to."""
    return request.config.getoption("--server")


@pytest.fixture
def user(request):
    """The user to use for fetching."""
    return request.config.getoption("--user")


@pytest.fixture
def password(request):
    """The password to use for fetching."""
    return request.config.getoption("--password")


@pytest.fixture
def root_dir(request):
    """Root directory containing all the RELEASEs for fetching."""
    return request.config.getoption("--root-dir")


@pytest.fixture
def http(request):
    """Have --server define a HTTP server instead."""
    return request.config.getoption("--http")


@pytest.fixture
def hardened(request):
    """Have fetch expect the default HardeneBSD layout instead."""
    freebsd_version = checkoutput(["freebsd-version"])

    if "HBSD" in freebsd_version:
        _hardened = True
    else:
        _hardened = False

    return _hardened


@pytest.fixture
def _file(request):
    """Use a local file directory for root-dir instead of FTP or HTTP."""
    return request.config.getoption("--file")


@pytest.fixture
def auth(request):
    """Authentication method for HTTP fetching. Valid values: basic, digest"""
    return request.config.getoption("--auth")


@pytest.fixture
def noupdate(request):
    """ Decide whether or not to update the fetch to the latest patch level."""
    return request.config.getoption("--noupdate")
