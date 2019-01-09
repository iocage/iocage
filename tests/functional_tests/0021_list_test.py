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

import re

import pytest
import requests


require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool

# TODO: Tests for ip6, -O, -P are left

SHORT_FLAGS = ['jid', 'name', 'state', 'release', 'ip4']
ALL_FLAGS = [
    'jid', 'name', 'boot', 'state', 'type', 'release', 'ip4', 'ip6', 'template'
]


def _short_flag_common(
    invoke_cli, command, jails, jails_as_rows, parse_rows_output
):
    verify_list = jails_as_rows(jails, all=True)

    for flag in SHORT_FLAGS:
        cmd = command.copy()
        cmd.extend(['-s', flag])
        result = invoke_cli(
            cmd
        )

        orig_list = parse_rows_output(result.output, 'all')
        verify_list.sort(key=lambda r: r.sort_flag(flag))

        assert verify_list == orig_list


@require_root
@require_zpool
def test_01_list_default(
    invoke_cli, resource_selector, parse_rows_output, jails_as_rows
):
    result = invoke_cli(
        ['list']
    )

    # With no flag specified, iocage should sort wrt name
    orig_list = parse_rows_output(result.output, 'all')
    verify_list = jails_as_rows(resource_selector.jails, all=True)

    verify_list.sort(key=lambda r: r.sort_flag('name'))

    assert verify_list == orig_list


@require_root
@require_zpool
def test_02_list_default_sort_flags(
    invoke_cli, resource_selector, jails_as_rows, parse_rows_output
):
    _short_flag_common(
        invoke_cli, ['list'], resource_selector.jails,
        jails_as_rows, parse_rows_output
    )


@require_root
@require_zpool
def test_03_list_releases_flag(
    invoke_cli, resource_selector, parse_rows_output, jails_as_rows
):
    result = invoke_cli(
        ['list', '-r']
    )

    orig_list = parse_rows_output(result.output, 'releases_only')
    verify_list = jails_as_rows(resource_selector.releases)

    verify_list.sort(key=lambda r: r.sort_flag('release'))

    assert orig_list == verify_list


@require_root
@require_zpool
def test_04_list_base_jails_with_sorting_flags(
    invoke_cli, resource_selector, jails_as_rows, parse_rows_output
):
    _short_flag_common(
        invoke_cli, ['list', '-B'], resource_selector.basejails,
        jails_as_rows, parse_rows_output
    )


@require_root
@require_zpool
def test_05_list_template_jails_with_sorting_flags(
    invoke_cli, resource_selector, jails_as_rows, parse_rows_output
):
    _short_flag_common(
        invoke_cli, ['list', '-t'], resource_selector.template_jails,
        jails_as_rows, parse_rows_output
    )


@require_root
@require_zpool
def test_06_list_jails_with_quick_flag(
    invoke_cli, resource_selector, parse_rows_output, jails_as_rows
):
    mapping = {
        '-b': 'releases',
        '': 'jails',
        '-t': 'template_jails'
    }

    for resource_flag in mapping:
        command = ['list', '-q']
        if resource_flag:
            command.append(resource_flag)

        result = invoke_cli(
            command
        )

        orig_list = parse_rows_output(result.output, 'quick')
        verify_list = jails_as_rows(
            getattr(resource_selector, mapping[resource_flag]),
            short_name=False
        )

        assert set(orig_list) == set(verify_list)


@require_root
@require_zpool
def test_07_list_remote_releases(invoke_cli, freebsd_download_server):
    result = invoke_cli(
        ['list', '-R']
    )

    orig_list = [s.strip() for s in result.output.split('\n') if s.strip()]

    req = requests.get(freebsd_download_server)
    assert req.status_code == 200

    releases = re.findall(
        r'href="(\d.*RELEASE)/"', req.content.decode('utf-8')
    )

    assert set(releases) == set(orig_list)


@require_root
@require_zpool
def test_08_list_jails_with_full_flag_and_sort(
    invoke_cli, resource_selector, jails_as_rows, parse_rows_output
):
    verify_list = jails_as_rows(
        resource_selector.jails, short_name=False, full=True
    )

    for flag in ALL_FLAGS:
        if 'ip6' == flag:
            # TODO: Let's add support for it moving on
            continue

        result = invoke_cli(
            ['list', '-l', '-s', flag]
        )

        orig_list = parse_rows_output(result.output, 'full')
        verify_list.sort(key=lambda r: r.sort_flag(flag))

        assert orig_list == verify_list
