import pytest
import subprocess

require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool

@require_root
@require_zpool
def test_activate(zpool):
    try:
        subprocess.check_call(["zfs", "set", "org.freebsd.ioc:active=yes",
                               zpool], stdout=subprocess.PIPE)
    except subprocess.CalledProcessError:
        exit("Pool: {} does not exist!".format(zpool))

    assert True == True
