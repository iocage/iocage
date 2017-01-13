from iocage.lib.ioc_destroy import IOCDestroy
from iocage.lib.ioc_list import IOCList


def test_destroy():
    jails, paths = IOCList("uuid").get_datasets()
    uuid = jails["newtest"]
    path = paths["newtest"]

    IOCDestroy(uuid, "newtest", path).destroy_jail()

    assert True == True
