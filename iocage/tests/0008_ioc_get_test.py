from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList


def test_get():
    _, paths = IOCList("uuid").list_datasets()

    path = paths["newtest"]
    path_short = paths["newtest_short"]

    prop = IOCJson(path).json_get_value("tag")
    prop_short = IOCJson(path_short).json_get_value("tag")

    assert prop == "newtest"
    assert prop_short == "newtest_short"
