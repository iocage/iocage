import pytest
from click.testing import CliRunner

from iocage import main as ioc

require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


@require_root
@require_zpool
def test_get():
    jails = ["newtest", "newtest_short"]
    runner = CliRunner()

    for jail in jails:
        result = runner.invoke(ioc.cli, ["get", "tag", jail])

        assert result.exit_code == 0
        assert result.output == f"{jail}\n"
