from iocage.lib.ioc_create import IOCCreate


def test_create(release):
    prop = ("tag=test",)
    IOCCreate(release, prop, 0, None).create_jail()

    assert True == True
