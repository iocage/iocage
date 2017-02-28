import pytest
from iocage.lib.ioc_destroy import IOCDestroy
from iocage.lib.ioc_list import IOCList

require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


@require_root
@require_zpool
def test_destroy():
    jails, paths = IOCList("uuid").list_datasets()

    uuid = jails["newtest"]
    uuid_short = jails["newtest_short"]

    path = paths["newtest"]
    path_short = paths["newtest_short"]

    IOCDestroy(uuid, "newtest", path).destroy_jail()
    IOCDestroy(uuid_short, "newtest_short", path_short).destroy_jail()

    assert True == True
