from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList


def test_get():
    _, paths = IOCList("uuid").get_datasets()
    path = paths["newtest"]

    prop = IOCJson(path).get_prop_value("tag")

    assert prop == "newtest"
