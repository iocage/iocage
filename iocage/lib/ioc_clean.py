"""Destroy all of a dataset type."""
import logging
import os
import shutil
from subprocess import CalledProcessError, PIPE, Popen, STDOUT, check_call, \
    check_output

from iocage.lib.ioc_destroy import IOCDestroy
from iocage.lib.ioc_json import IOCJson


class IOCClean(object):
    """Cleans datasets and snapshots of a given type."""

    def __init__(self):
        self.pool = IOCJson().json_get_value("pool")
        self.iocroot = IOCJson(self.pool).json_get_value("iocroot")
        self.lgr = logging.getLogger('ioc_clean')

    @staticmethod
    def __clean_stop_jails__():
        """Stops every jail running forcefully."""
        jls = Popen(["jls", "jid"], stdout=PIPE).communicate()[0].split()

        for j in jls:
            try:
                check_call(["jail", "-r", j])
            except CalledProcessError as err:
                raise RuntimeError("ERROR: {}".format(err))

    def clean_jails(self):
        """Cleans all jails and their respective snapshots."""
        self.__clean_stop_jails__()

        # Faster then one by one deletion
        try:
            check_output(["zfs", "destroy", "-r", "-f",
                          "{}/iocage/jails".format(self.pool)],
                         stderr=STDOUT)
            check_output(["zfs", "destroy", "-r", "-f",
                          "{}/iocage/templates".format(self.pool)],
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
            shutil.rmtree("{}/tags".format(self.iocroot), ignore_errors=True)
            os.mkdir("{}/tags".format(self.iocroot))

        if os.path.exists("{}/log".format(self.iocroot)):
            shutil.rmtree("{}/log".format(self.iocroot), ignore_errors=True)

    def clean_all(self):
        """Cleans everything related to iocage."""
        self.__clean_stop_jails__()

        try:
            check_call(["zfs", "destroy", "-R", "-f",
                        "{}/iocage".format(self.pool)])
        except CalledProcessError as err:
            raise RuntimeError("ERROR: {}".format(err))

    def clean_templates(self):
        """Cleans all jails and their respective snapshots."""
        self.__clean_stop_jails__()

        datasets = check_output(["zfs", "get", "-o", "name,value", "-t",
                                 "filesystem", "-H",
                                 "origin"]).splitlines()

        datasets = dict([map(str, c.split("\t")) for c in datasets])
        children_dict = {name: mount for name, mount in datasets.iteritems() if
                         "{}/iocage/templates".format(self.pool) in mount}
        template_dict = {name: mount for name, mount in datasets.iteritems() if
                         "{}/iocage/releases".format(self.pool) in mount}

        for jail in children_dict.iterkeys():
            if "/jails" in jail:
                jail = jail.rstrip("/root")
                uuid = jail.split("/")[3]
                path = jail.replace("{}/iocage".format(self.pool), self.iocroot)
                conf = IOCJson(path).json_load()
                tag = conf["tag"]

                IOCDestroy(uuid, tag, path, silent=True).destroy_jail()

        for template in template_dict.iterkeys():
            if "/templates" in template:
                template = template.rstrip("/root")
                path = template.replace("{}/iocage".format(self.pool),
                                        self.iocroot)
                conf = IOCJson(path).json_load()
                uuid = conf["host_hostuuid"]
                tag = conf["tag"]

                IOCDestroy(uuid, tag, path, silent=True).destroy_jail()
