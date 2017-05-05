"""Destroy all of a dataset type."""
import libzfs

import iocage.lib.ioc_destroy
import iocage.lib.ioc_json


class IOCClean(object):
    """Cleans datasets and snapshots of a given type."""

    def __init__(self):
        self.pool = iocage.lib.ioc_json.IOCJson().json_get_value("pool")

    def clean_jails(self):
        """Cleans all jails and their respective snapshots."""
        iocage.lib.ioc_destroy.IOCDestroy().destroy_jail(
            f"{self.pool}/iocage/jails",
            clean=True)

    def clean_all(self):
        """Cleans everything related to iocage."""
        iocage.lib.ioc_destroy.IOCDestroy().__stop_jails__()

        zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")
        datasets = zfs.get_dataset(f"{self.pool}/iocage")

        for dataset in datasets.dependents:
            try:
                if dataset.type == libzfs.DatasetType.FILESYSTEM:
                    dataset.umount(force=True)
            except libzfs.ZFSException as err:
                # This is either not mounted or doesn't exist anymore,
                # we don't care either way.
                if err.code == libzfs.Error.NOENT:
                    continue
                else:
                    raise

            dataset.delete()

        datasets.umount(force=True)
        datasets.delete()

    def clean_templates(self):
        """Cleans all templates and their respective children."""
        iocage.lib.ioc_destroy.IOCDestroy().__destroy_parse_datasets__(
            f"{self.pool}/iocage/templates",
            clean=True)
