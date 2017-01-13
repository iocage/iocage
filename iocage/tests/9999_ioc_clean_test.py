import os

from iocage.lib.ioc_clean import IOCClean


def test_clean():
    # Unless we change directory (not sure why) this will crash pytest.
    os.chdir("/")

    IOCClean().clean_jails()
    IOCClean().clean_all()

    assert True == True
