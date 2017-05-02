import pytest
from click.testing import CliRunner

from iocage import main as ioc

require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


@require_root
@require_zpool
def test_create(release, hardened):
    prop = "tag=test"
    prop_short = "tag=test_short"

    if hardened:
        release = f"{release}-STABLE"

    runner = CliRunner()
    result = runner.invoke(ioc.cli, ["create", "-r", release, prop])
    result_short = runner.invoke(ioc.cli, ["create", "-r", release, "-s",
                                           prop_short])

    assert result.exit_code == 0
    assert result_short.exit_code == 0
