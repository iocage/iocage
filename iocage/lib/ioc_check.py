"""Check datasets before execution"""
import logging
import os
import sys
from subprocess import CalledProcessError, PIPE, Popen, check_output

from iocage.lib.ioc_json import IOCJson


class IOCCheck(object):
    """Checks if the required iocage datasets are present"""

    def __init__(self, altpool, silent=False):
        self.pool = IOCJson().json_get_value("pool")
        self.altpool = altpool
        self.lgr = logging.getLogger('ioc_check')

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
        if not self.pool:
            if not self.altpool:
                raise RuntimeError("Please supply a pool to activate.")

            self.pool = self.altpool

        mounts = check_output(["zfs", "get", "-o", "name,value", "-t",
                               "filesystem", "-H",
                               "mountpoint"]).splitlines()

        mounts = dict([map(str, m.split("\t")) for m in mounts])
        dups = {name: mount for name, mount in mounts.iteritems() if
                mount == "/iocage"}

        for dataset in datasets:
            try:
                check_output(["zfs", "get", "-H", "creation", "{}/{}".format(
                    self.pool, dataset)], stderr=PIPE)
            except CalledProcessError:
                if os.geteuid() != 0:
                    raise RuntimeError("Run as root to create missing"
                                       " datasets!")

                if "deactivate" not in sys.argv[1:]:
                    self.lgr.info("Creating {}/{}".format(self.pool, dataset))
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
