from iocage.lib.ioc_check import IOCCheck


def test_check(zpool):
    IOCCheck(zpool)

    assert True == True
