"""Check datasets before execution"""
import logging
import sys
from subprocess import CalledProcessError, PIPE, Popen, check_output

import os

from iocage.lib.ioc_json import IOCJson


class IOCCheck(object):
    """Checks if the required iocage datasets are present"""

    def __init__(self, altpool):
        self.pool = IOCJson("").get_prop_value("pool")
        self.altpool = altpool
        self.lgr = logging.getLogger('ioc_check')

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
                        Popen(["zfs", "create", "-o", "compression=lz4",
                               "-o", "mountpoint=/iocage",
                               "{}/{}".format(self.pool,
                                              dataset)]).communicate()
                    else:
                        Popen(["zfs", "create", "-o", "compression=lz4",
                               "{}/{}".format(self.pool,
                                              dataset)]).communicate()
