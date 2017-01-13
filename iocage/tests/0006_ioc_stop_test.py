from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_stop import IOCStop


def test_stop():
    jails, paths = IOCList("uuid").get_datasets()
    uuid = jails["test"]
    path = paths["test"]
    conf = IOCJson(path).load_json()

    IOCStop(uuid, "test", path, conf)

    assert True == True
