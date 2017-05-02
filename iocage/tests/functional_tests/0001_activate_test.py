import pytest
from click.testing import CliRunner

from iocage import main as ioc

require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


@require_root
@require_zpool
def test_activate(zpool):
    runner = CliRunner()
    result = runner.invoke(ioc.cli, ['activate', zpool])

    assert result.exit_code == 0
