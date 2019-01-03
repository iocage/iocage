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


# Let's perform testing first on different types of jails
# Then we can move on to setting some specific properties and seeing
# do the props work as intended


# TODO: Plugin test left


def _set_and_test_note_prop(invoke_cli, value, jail):
    invoke_cli(
        ['set', f'notes={value}', jail.name]
    )

    assert jail.config.get('notes') == value, \
        f'Failed to set note value to {value}'


@require_root
@require_zpool
def test_01_set_prop_on_jail(resource_selector, invoke_cli, skip_test):
    jails = resource_selector.jails
    skip_test(not jails)

    _set_and_test_note_prop(
        invoke_cli, 'foo \"bar\"', jails[0]
    )


@require_root
@require_zpool
def test_02_set_prop_on_thickconfig_jail(
        resource_selector, invoke_cli, skip_test
):
    thickconfig_jails = resource_selector.thickconfig_jails
    skip_test(not thickconfig_jails)

    _set_and_test_note_prop(
        invoke_cli, 'foo \"bar\"', thickconfig_jails[0]
    )


@require_root
@require_zpool
def test_03_set_prop_on_basejail(resource_selector, invoke_cli, skip_test):
    basejails = resource_selector.basejails
    skip_test(not basejails)

    _set_and_test_note_prop(
        invoke_cli, 'foo \"bar\"', basejails[0]
    )


@require_root
@require_zpool
def test_04_set_prop_on_template_jail(resource_selector, invoke_cli, skip_test):
    template_jails = resource_selector.template_jails
    skip_test(not template_jails)

    _set_and_test_note_prop(
        invoke_cli, 'foo \"bar\"', template_jails[0]
    )
