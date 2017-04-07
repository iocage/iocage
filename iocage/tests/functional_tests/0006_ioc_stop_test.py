import pytest

import iocage.lib.libiocage as libiocage

require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


@require_root
@require_zpool
def test_stop():
    libiocage.IOCageMng().mng_jail(False, ["test", "test_short"], 'stop')

    assert True == True
