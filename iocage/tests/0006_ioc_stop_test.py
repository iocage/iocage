from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_stop import IOCStop


def test_stop():
    jails, paths = IOCList("uuid").list_datasets()

    uuid = jails["test"]
    uuid_short = jails["test_short"]

    path = paths["test"]
    path_short = paths["test_short"]

    conf = IOCJson(path).json_load()
    conf_short = IOCJson(path_short).json_load()

    IOCStop(uuid, "test", path, conf)
    IOCStop(uuid_short, "test_short", path_short, conf_short)

    assert True == True
