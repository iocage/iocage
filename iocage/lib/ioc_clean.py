"""Destroy all of a dataset type."""
import logging

import libzfs

from iocage.lib.ioc_destroy import IOCDestroy
from iocage.lib.ioc_json import IOCJson


class IOCClean(object):
    """Cleans datasets and snapshots of a given type."""

    def __init__(self):
        self.pool = IOCJson().json_get_value("pool")
        self.lgr = logging.getLogger('ioc_clean')
        self.zfs = libzfs.ZFS()
        self.ds = self.zfs.get_dataset

    def clean_jails(self):
        """Cleans all jails and their respective snapshots."""
        IOCDestroy().__stop_jails__()
        IOCDestroy().__destroy_datasets__(f"{self.pool}/iocage/jails",
                                          clean=True)

    def clean_all(self):
        """Cleans everything related to iocage."""
        IOCDestroy().__stop_jails__()

        datasets = self.ds(f"{self.pool}/iocage")

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

    def clean_templates(self):
        """Cleans all templates and their respective children."""
        IOCDestroy().__destroy_datasets__(f"{self.pool}/iocage/templates",
                                          clean=True)
