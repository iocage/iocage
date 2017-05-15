"""Check datasets before execution"""
import os

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

        zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")
        pool = zfs.get(self.pool)
        has_duplicates = len(list(filter(lambda x: x.mountpoint == "/iocage",
                                         list(pool.root.datasets)))) > 0

        for dataset in datasets:

            zfs_dataset_name = "{}/{}".format(self.pool, dataset)

            is_existing = len(list(filter(lambda x: x.name == zfs_dataset_name,
                                          list(pool.root.datasets)))) > 0

            if not is_existing:

                if os.geteuid() != 0:
                    raise RuntimeError("Run as root to create missing"
                                       " datasets!")

                iocage.lib.ioc_common.logit({
                    "level"  : "INFO",
                    "message": f"Creating {self.pool}/{dataset}"
                },
                    _callback=self.callback,
                    silent=self.silent)

                dataset_options = {
                    "compression": "lz4",
                }

                if dataset == "iocage" and not has_duplicates:
                    dataset_options["mountpoint"] = "/iocage"
                elif dataset == "iocage" and has_duplicates:
                    dataset_options["mountpoint"] = f"/{self.pool}/iocage"

                pool.create(zfs_dataset_name, dataset_options)
