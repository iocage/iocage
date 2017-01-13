from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_start import IOCStart


def test_start():
    jails, paths = IOCList("uuid").get_datasets()
    uuid = jails["test"]
    path = paths["test"]
    conf = IOCJson(path).load_json()

    IOCStart(uuid, path).start_jail("test", conf)

    assert True == True
