"""Check datasets before execution"""
import os
import subprocess as su
import sys
import libzfs

import iocage.lib.ioc_common
import iocage.lib.ioc_json


class IOCCheck(object):
    """Checks if the required iocage datasets are present"""

    def __init__(self, silent=False, callback=None):
        self.pool = iocage.lib.ioc_json.IOCJson(silent=silent).json_get_value(
            "pool")
        self.callback = callback
        self.silent = silent

        self.__check_datasets__()

    def __check_datasets__(self):
        """
        Loops through the required datasets and if there is root
        privilege will then create them.
        """
        datasets = ("iocage", "iocage/download", "iocage/images",
                    "iocage/jails", "iocage/log", "iocage/releases",
                    "iocage/templates")

        zfs = libzfs.ZFS()
        pool = zfs.get(self.pool)
        hasDuplicates = len(list(filter(lambda x: x.mountpoint == "/iocage", list(pool.root.datasets)))) > 0

        for dataset in datasets:

            zfsDatasetName = "{}/{}".format(self.pool, dataset)

            isExisting = len(list(filter(lambda x: x.name == zfsDatasetName, list(pool.root.datasets)))) > 0

            if not isExisting:

                if os.geteuid() != 0:
                    raise RuntimeError("Run as root to create missing"
                                       " datasets!")

                iocage.lib.ioc_common.logit({
                    "level"  : "INFO",
                    "message": f"Creating {self.pool}/{dataset}"
                },
                    _callback=self.callback,
                    silent=self.silent)

                datasetOptions = {
                    "compression": "lz4",
                    "mountpoint": "/{}/{}".format(self.pool, dataset)
                }

                if (dataset == "iocage") and not hasDuplicates:
                    datasetOptions.mountpoint = "/iocage"

                pool.create(zfsDatasetName, datasetOptions)
