import pytest
from iocage.cli.activate import activate_cmd
from click.testing import CliRunner

require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


@require_root
@require_zpool
def test_activate(zpool):
    runner = CliRunner()
    result = runner.invoke(activate_cmd, [zpool])

    assert result.exit_code == 0
