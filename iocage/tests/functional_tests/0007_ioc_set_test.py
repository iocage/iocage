import pytest
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList

require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


@require_root
@require_zpool
def test_set():
    _, paths = IOCList("uuid").list_datasets()

    path = paths["test"]
    path_short = paths["test_short"]

    IOCJson(path, silent=True).json_set_value("tag=newtest")
    IOCJson(path_short, silent=True).json_set_value("tag=newtest_short")

    assert True == True
