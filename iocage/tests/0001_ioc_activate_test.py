import os
import subprocess


def test_activate(zpool):
    if os.geteuid() != 0:
        raise RuntimeError(
            "You need to have root privileges to run any tests.")
    try:
        subprocess.check_call(["zfs", "set", "org.freebsd.ioc:active=yes",
                               zpool], stdout=subprocess.PIPE)
    except subprocess.CalledProcessError:
        exit("Pool: {} does not exist!".format(zpool))

    assert True == True
