import os
import pytest
from iocage.lib.ioc_clean import IOCClean

require_root = pytest.mark.require_root
require_zpool = pytest.mark.require_zpool


@require_root
@require_zpool
def test_clean():
    # Unless we change directory (not sure why) this will crash pytest.
    os.chdir("/")

    IOCClean().clean_jails()
    IOCClean().clean_all()

    assert True == True
