"""Check datasets before execution"""
import os
import sys
from subprocess import CalledProcessError, PIPE, Popen

from iocage.lib.ioc_common import checkoutput
from iocage.lib.ioc_json import IOCJson
import iocage.lib.ioc_log as ioc_log


class IOCCheck(object):
    """Checks if the required iocage datasets are present"""

    def __init__(self, silent=False):
        self.pool = IOCJson().json_get_value("pool")
        self.lgr = ioc_log.getLogger('ioc_check')

        if silent:
            self.lgr.disabled = True

        self.__check_datasets__()

    def __check_datasets__(self):
        """
        Loops through the required datasets and if there is root
        privilege will then create them.
        """
        datasets = ("iocage", "iocage/download", "iocage/images",
                    "iocage/jails", "iocage/log", "iocage/releases",
                    "iocage/templates")

        mounts = checkoutput(["zfs", "get", "-o", "name,value", "-t",
                              "filesystem", "-H",
                              "mountpoint"]).splitlines()

        mounts = dict([list(map(str, m.split("\t"))) for m in mounts])
        dups = {name: mount for name, mount in mounts.items() if
                mount == "/iocage"}

        for dataset in datasets:
            try:
                checkoutput(["zfs", "get", "-H", "creation", "{}/{}".format(
                    self.pool, dataset)], stderr=PIPE)
            except CalledProcessError:
                if os.geteuid() != 0:
                    raise RuntimeError("Run as root to create missing"
                                       " datasets!")

                if "deactivate" not in sys.argv[1:]:
                    print("Creating {}/{}".format(self.pool, dataset))
                    if dataset == "iocage":
                        if len(dups) != 0:
                            mount = "mountpoint=/{}/iocage".format(self.pool)
                        else:
                            mount = "mountpoint=/iocage"

                        Popen(["zfs", "create", "-o", "compression=lz4",
                               "-o", mount, "{}/{}".format(
                                self.pool, dataset)]).communicate()
                    else:
                        Popen(["zfs", "create", "-o", "compression=lz4",
                               "{}/{}".format(self.pool,
                                              dataset)]).communicate()
