import pytest
from iocage.lib.ioc_check import IOCCheck

require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


@require_root
@require_zpool
def test_check():
    IOCCheck()

    assert True == True
