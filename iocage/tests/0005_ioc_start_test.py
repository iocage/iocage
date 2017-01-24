from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_start import IOCStart


def test_start():
    jails, paths = IOCList("uuid").get_datasets()

    uuid = jails["test"]
    uuid_short = jails["test_short"]

    path = paths["test"]
    path_short = paths["test_short"]

    conf = IOCJson(path).load_json()
    conf_short = IOCJson(path_short).load_json()

    IOCStart(uuid, "test", path, conf)
    IOCStart(uuid_short, "test_short", path_short, conf_short)

    assert True == True
