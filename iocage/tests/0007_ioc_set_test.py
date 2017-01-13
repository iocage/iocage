from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList


def test_set():
    _, paths = IOCList("uuid").get_datasets()
    path = paths["test"]

    IOCJson(path, silent=True).set_prop_value("tag=newtest")

    assert True == True
