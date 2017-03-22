import pytest
from iocage.lib.ioc_destroy import IOCDestroy
from iocage.lib.ioc_list import IOCList

require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


@require_root
@require_zpool
def test_destroy():
    jails, paths = IOCList("uuid").list_datasets()

    path = paths["newtest"]
    path_short = paths["newtest_short"]

    IOCDestroy().destroy_jail(path)
    IOCDestroy().destroy_jail(path_short)

    assert True == True
