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
        result_output = \
            '+-----+----------+-------+---------------+-----------+-----+\n' \
            '| JID |   UUID   | STATE |      TAG      |  RELEASE  | IP4 ' \
            '|\n+=====+==========+=======+===============+===========+=====+' \
            f'\n| -   | 771ec0cf | down  | newtest       | {release} | -   |' \
            '\n+-----+----------+-------+---------------+-----------+-----+' \
            f'\n| -   | dfb013e5 | down  | newtest_short | {release} | -   |' \
            '\n+-----+----------+-------+---------------+-----------+-----+\n'

        result_release_header_output = \
            '+---------------+\n| Bases fetched ' \
            f'|\n+===============+\n| {release}     |\n+---------------+\n'
    else:
        result_output = \
            '+-----+----------+-------+---------------+--------------+-----+' \
            '\n| JID |   UUID   | STATE |      TAG      |   RELEASE    | IP4' \
            ' |\n+=====+==========+=======+===============+==============+' \
            f'=====+\n| -   | 771ec0cf | down  | newtest       | {release} |' \
            ' -   |\n+-----+----------+-------+---------------+-------------' \
            f'-+-----+\n| -   | dfb013e5 | down  | newtest_short | {release}' \
            ' | -   |\n+-----+----------+-------+---------------+-----------' \
            '---+-----+\n'

        result_release_header_output = \
            '+---------------+\n| Bases fetched |\n+===============+\n' \
            f'| {release}  |\n+---------------+\n'

    result_noheader_output = f'-\t771ec0cf\tdown\tnewtest\t{release}\t-\n' \
                             f'-\tdfb013e5\tdown\tnewtest_short\t{release}' \
                             '\t-\n'
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
