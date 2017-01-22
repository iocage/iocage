from iocage.lib.ioc_create import IOCCreate


def test_create(release):
    prop = ("tag=test",)
    prop_short = ("tag=test_short",)
    IOCCreate(release, prop, 0).create_jail()
    IOCCreate(release, prop_short, 0, short=True).create_jail()

    assert True == True
