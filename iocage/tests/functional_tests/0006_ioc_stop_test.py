import pytest

from iocage.lib.iocage import IOCage

require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


@require_root
@require_zpool
def test_stop():
    IOCage(["test", "test_short"]).stop()

    assert True == True
