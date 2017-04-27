import pytest

from iocage.lib.iocage import IOCage

require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


@require_root
@require_zpool
def test_start():
    IOCage("test").start()
    IOCage("test_short").start()

    assert True == True
