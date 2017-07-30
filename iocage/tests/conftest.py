import pytest
import sys
import os

import helper_functions

# Inject lib directory to path
iocage_lib_dir = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    "..", "lib"
))
if iocage_lib_dir not in sys.path:
    sys.path = [iocage_lib_dir] + sys.path

_force_clean = False
def pytest_addoption(parser):
    parser.addoption("--force-clean", action="store_true",
        help="Force cleaning the /iocage-test dataset")

def pytest_generate_tests(metafunc):
    _force_clean = metafunc.config.getoption("force_clean")

print("force_clean?", _force_clean)


@pytest.fixture
def force_clean():
    return _force_clean

@pytest.fixture
def zfs():
    import libzfs
    return libzfs.ZFS(history=True, history_prefix="<iocage>")

@pytest.fixture
def pool(zfs):
    try:
        return zfs.get_dataset_by_path("/iocage").pool
    except:
        raise Exception("Please activate iocage before running tests")

@pytest.fixture
def logger():
    import Logger
    return Logger.Logger()

@pytest.fixture
def root_dataset(force_clean, zfs, pool):

    dataset_name = f"{pool.name}/iocage-test"

    if force_clean:
        try:
            dataset = zfs.get_dataset(dataset_name)
            helper_functionsunmount_and_destroy_dataset_recursive(dataset)
        except:
            pass

    try:
        pool.create(dataset_name, {})
    except:
        if force_clean:
            raise
        pass

    dataset = zfs.get_dataset(dataset_name)
    if not dataset.mountpoint:
        dataset.mount()

    yield dataset

    if force_clean:
        helper_functionsunmount_and_destroy_dataset_recursive(dataset)

@pytest.fixture
def host(root_dataset, logger, zfs):
    import Host
    host = Host.Host(root_dataset=root_dataset, logger=logger, zfs=zfs)
    yield host
    del host
    
@pytest.fixture
def release(host, logger, zfs):
    import Release
    return Release.Release(name=host.release_version, host=host, logger=logger, zfs=zfs)
