import pytest
import uuid
import json
import os

import iocage.lib.Jail

import helper_functions

def read_jail_config_json(config_file):
    with open(config_file, "r") as conf:
        return json.load(conf)

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


    def test_can_be_created(self, host, local_release, logger, zfs, root_dataset, capsys):

        jail = iocage.lib.Jail.Jail(host=host, logger=logger, zfs=zfs)
        jail.create(local_release.name)

        dataset = zfs.get_dataset(f"{root_dataset.name}/jails/{jail.name}")

        def cleanup():
            helper_functions.unmount_and_destroy_dataset_recursive(dataset)

        try:
            uuid.UUID(jail.name)
            assert len(str(jail.name)) == 36
            assert jail.config.basejail == False
            assert not jail.config.basejail_type

            assert dataset.mountpoint is not None
            assert os.path.isfile(f"{dataset.mountpoint}/config.json")
            assert os.path.isdir(f"{dataset.mountpoint}/root")

            data = read_jail_config_json(f"{dataset.mountpoint}/config.json")

            try:
                assert data["basejail"] is "no"
            except (KeyError) as e:
                pass

            try:
                assert (data["basejail"] is "") or (data["basejail"] == "none")
            except (KeyError) as e:
                pass

        except Exception as e:
            cleanup()
            raise e

        cleanup()

        
class TestNullFSBasejail(object):

    @pytest.fixture
    def local_release(self, release, root_dataset, force_clean, zfs):

        if not release.fetched:
            release.fetch()

        yield release

        if force_clean:
            release.dataset.umount()
            release.dataset.delete()

        del release

    def test_can_be_created(self, host, local_release, logger, zfs, root_dataset):

        jail = iocage.lib.Jail.Jail({
            "basejail": True
        }, host=host, logger=logger, zfs=zfs)
        jail.create(local_release.name)

        dataset = zfs.get_dataset(f"{root_dataset.name}/jails/{jail.name}")

        def cleanup():
            helper_functions.unmount_and_destroy_dataset_recursive(dataset)

        try:
            uuid.UUID(jail.name)
            assert len(str(jail.name)) == 36
            assert jail.config.basejail == True
            assert jail.config.basejail_type == "nullfs"

            assert dataset.mountpoint is not None
            assert os.path.isfile(f"{dataset.mountpoint}/config.json")
            assert os.path.isdir(f"{dataset.mountpoint}/root")

            data = read_jail_config_json(f"{dataset.mountpoint}/config.json")

            assert data["basejail"] == "yes"

            try:
                assert data["basejail_type"] == "nullfs"
            except KeyError as e:
                pass

        except Exception as e:
            cleanup()
            raise e

        cleanup()
