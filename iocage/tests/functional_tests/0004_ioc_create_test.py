import pytest
from iocage.lib.ioc_create import IOCCreate

require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


@require_root
@require_zpool
def test_create(release, hardened):
    prop = ("tag=test",)
    prop_short = ("tag=test_short",)

    if hardened:
        release = "{}-STABLE".format(release)

    IOCCreate(release, prop, 0).create_jail()
    IOCCreate(release, prop_short, 0, short=True).create_jail()

    assert True == True
