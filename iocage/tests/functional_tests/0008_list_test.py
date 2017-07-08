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
import re

import pytest
from click.testing import CliRunner

from iocage import main as ioc

require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


@require_zpool
def test_list(release, hardened):
    runner = CliRunner()

    if hardened:
        release = release.replace("-RELEASE", "-STABLE")
        release = re.sub(r"\W\w.", "-", release)

    if hardened:
        # This has a couple less spaces than on vanilla FreeBSD.
        result_output = \
            '+-----+----------+-------+-----------+-----+\n' \
            '| JID |   NAME   | STATE |  RELEASE  | IP4 |\n' \
            '+=====+==========+=======+===========+=====+\n' \
            f'| -   | 771ec0cf | down  | {release} | -   |\n' \
            '+-----+----------+-------+-----------+-----+\n' \
            f'| -   | dfb013e5 | down  | {release} | -   |\n' \
            '+-----+----------+-------+-----------+-----+\n'

        result_release_header_output = \
            '+---------------+\n| Bases fetched ' \
            f'|\n+===============+\n| {release}     |\n+---------------+\n'
    else:
        result_output = \
            '+-----+----------+-------+--------------+-----+\n' \
            '| JID |   NAME   | STATE |   RELEASE    | IP4 |' \
            '\n+=====+==========+=======+==============+=====+\n' \
            f'| -   | 771ec0cf | down  | {release} | -   |\n' \
            '+-----+----------+-------+--------------+-----+\n' \
            f'| -   | dfb013e5 | down  | {release} | -   |\n' \
            '+-----+----------+-------+--------------+-----+\n'

        result_release_header_output = \
            '+---------------+\n| Bases fetched |\n+===============+\n' \
            f'| {release}  |\n+---------------+\n'

    result_noheader_output = f'-\t771ec0cf\tdown\t{release}\t-\n' \
                             f'-\tdfb013e5\tdown\t{release}\t-\n'

    result_release_noheader_output = f'{release}\n'

    result_header = runner.invoke(ioc.cli, ["list"])
    result_noheader = runner.invoke(ioc.cli, ["list", "-H"])
    result_release_header = runner.invoke(ioc.cli, ["list", "-r"])
    result_release_noheader = runner.invoke(ioc.cli, ["list", "-r", "-H"])
    assert result_header.exit_code == 0
    assert result_release_header.exit_code == 0
    assert result_noheader.exit_code == 0
    assert result_release_noheader.exit_code == 0

    assert result_header.output == result_output
    assert result_release_header.output == result_release_header_output
    assert result_noheader.output == result_noheader_output
    assert result_release_noheader.output == result_release_noheader_output
