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


@require_root
@require_zpool
def test_01_df(
        invoke_cli, resource_selector, jails_as_rows, parse_rows_output
):
    result = invoke_cli(
        ['df']
    )

    # With no flag specified, iocage should sort wrt name
    orig_list = parse_rows_output(result.output, 'df')
    verify_list = jails_as_rows(
        resource_selector.all_jails, short_name=False
    )

    verify_list.sort(key=lambda r: r.sort_flag('name'))

    assert verify_list == orig_list


@require_root
@require_zpool
def test_02_df_sort_flag(
        invoke_cli, resource_selector, jails_as_rows, parse_rows_output
):
    flags = ['name', 'crt', 'res', 'qta', 'use', 'ava']
    verify_list = jails_as_rows(
        resource_selector.all_jails, short_name=False
    )

    for flag in flags:
        result = invoke_cli(
            ['df', '-s', flag]
        )

        orig_list = parse_rows_output(result.output, 'df')
        verify_list.sort(key=lambda r: r.sort_flag(flag))

        assert verify_list == orig_list, f'Mismatched df output for flag {flag}'
