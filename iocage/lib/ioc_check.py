"""Check datasets before execution"""
import os
import subprocess as su
import sys

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

        mounts = iocage.lib.ioc_common.checkoutput(
            ["zfs", "get", "-o", "name,value", "-t",
             "filesystem", "-H",
             "mountpoint"]).splitlines()

        mounts = dict([list(map(str, m.split("\t"))) for m in mounts])
        dups = {name: mount for name, mount in mounts.items() if
                mount == "/iocage"}

        for dataset in datasets:
            try:
                iocage.lib.ioc_common.checkoutput(
                    ["zfs", "get", "-H", "creation", "{}/{}".format(
                        self.pool, dataset)], stderr=su.PIPE)
            except su.CalledProcessError:
                if os.geteuid() != 0:
                    raise RuntimeError("Run as root to create missing"
                                       " datasets!")

                iocage.lib.ioc_common.logit({
                    "level"  : "INFO",
                    "message": f"Creating {self.pool}/{dataset}"
                },
                    _callback=self.callback,
                    silent=self.silent)
                if dataset == "iocage":
                    if len(dups) != 0:
                        mount = "mountpoint=/{}/iocage".format(self.pool)
                    else:
                        mount = "mountpoint=/iocage"

                    su.Popen(["zfs", "create", "-o", "compression=lz4",
                              "-o", mount, "{}/{}".format(
                            self.pool, dataset)]).communicate()
                else:
                    su.Popen(["zfs", "create", "-o", "compression=lz4",
                              "{}/{}".format(self.pool,
                                             dataset)]).communicate()
