import pytest
import uuid

import Jail

import helper_functions

class TestJail(object):

    @pytest.fixture
    def local_release(self, release, root_dataset, force_clean, zfs):

        if not release.fetched:
            release.fetch()

        yield release

        if force_clean:
            release.dataset.umount()
            release.dataset.delete()

        del release

    def test_create_jail(self, host, local_release, logger, zfs, root_dataset):

        jail = Jail.Jail(host=host, logger=logger, zfs=zfs)
        jail.create(local_release.name)

        def cleanup():
            dataset = zfs.get_dataset(f"{root_dataset.name}/jails/{jail.uuid}")
            helper_functions.unmount_and_destroy_dataset_recursive(dataset)

        try:
            assert isinstance(jail.uuid, uuid.UUID)
            assert len(str(jail.uuid)) == 36
            assert jail.config.basejail == False
            assert not jail.config.basejail_type
        except Exception as e:
            cleanup()
            print(e)
            raise

        cleanup()
        

    def test_create_basejail(self, host, local_release, logger, zfs, root_dataset):

        jail = Jail.Jail({
            "basejail": True
        }, host=host, logger=logger, zfs=zfs)
        jail.create(local_release.name)

        def cleanup():
            dataset = zfs.get_dataset(f"{root_dataset.name}/jails/{jail.uuid}")
            helper_functions.unmount_and_destroy_dataset_recursive(dataset)

        try:
            assert isinstance(jail.uuid, uuid.UUID)
            assert len(str(jail.uuid)) == 36
            assert jail.config.basejail == True
            assert jail.config.basejail_type == "nullfs"
        except Exception as e:
            cleanup()
            print(e)
            raise

        cleanup()
