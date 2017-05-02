import os

import pytest
from click.testing import CliRunner

from iocage import main as ioc

require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


@require_root
@require_zpool
def test_clean():
    # Unless we change directory (not sure why) this will crash pytest.
    os.chdir("/")
    actions = [["-j", "-f"], ["-a", "-f"]]

    runner = CliRunner()
    for action in actions:
        command = ["clean"] + action
        result = runner.invoke(ioc.cli, command)

        assert result.exit_code == 0
