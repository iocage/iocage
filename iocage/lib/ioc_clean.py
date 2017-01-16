"""Destroy all of a dataset type."""
import logging
import shutil
from subprocess import CalledProcessError, PIPE, Popen, STDOUT, check_call, \
    check_output

import os

from iocage.lib.ioc_json import IOCJson


class IOCClean(object):
    """Cleans datasets and snapshots of a given type."""

    def __init__(self):
        self.pool = IOCJson().get_prop_value("pool")
        self.iocroot = IOCJson(self.pool).get_prop_value("iocroot")
        self.lgr = logging.getLogger('ioc_clean')

    @staticmethod
    def __stop_jails():
        """Stops every jail running forcefully."""
        jls = Popen(["jls", "jid"], stdout=PIPE).communicate()[
            0].split()

        for j in jls:
            try:
                check_call(["jail", "-r", j])
            except CalledProcessError as err:
                raise RuntimeError("ERROR: {}".format(err))

    def clean_jails(self):
        """Cleans all jails and their respective snapshots."""
        self.__stop_jails()

        # Faster then one by one deletion
        try:
            check_output(["zfs", "destroy", "-r", "-f",
                          "{}/iocage/jails".format(self.pool)],
                         stderr=STDOUT)
        except CalledProcessError as err:
            if "snapshot" not in err.output.strip():
                raise RuntimeError("ERROR: {}".format(err.output.strip()))

        # Faster then one by one deletion
        try:
            check_output(["zfs", "destroy", "-R", "-f",
                          "{}/iocage/releases@%".format(self.pool)],
                         stderr=STDOUT)
        except CalledProcessError as err:
            if "snapshot" not in err.output.strip():
                raise RuntimeError("ERROR: {}".format(err.output.strip()))

        try:
            check_call(["zfs", "create", "-o", "compression=lz4",
                        "{}/iocage/jails".format(self.pool)])
        except CalledProcessError:
            raise RuntimeError("ERROR: Creating {}/iocage/jails "
                               "failed!".format(self.pool))

        if os.path.exists("{}/tags".format(self.iocroot)):
            shutil.rmtree("{}/tags".format(self.iocroot),
                          ignore_errors=True)
            os.mkdir("{}/tags".format(self.iocroot))

    def clean_all(self):
        """Cleans everything related to iocage."""
        self.__stop_jails()

        try:
            check_call(["zfs", "destroy", "-R", "-f",
                        "{}/iocage".format(self.pool)])
        except CalledProcessError as err:
            raise RuntimeError("ERROR: {}".format(err))
