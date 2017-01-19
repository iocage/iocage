"""iocage destroy module."""
import logging
from subprocess import CalledProcessError, PIPE, Popen, check_call

import os

from iocage.lib.ioc_json import IOCJson


class IOCDestroy(object):
    """
    Destroy a jail's datasets and then if they have a RELEASE snapshot,
    destroy that as well.
    """

    def __init__(self, uuid, jail, path, silent):
        self.pool = IOCJson().get_prop_value("pool")
        self.iocroot = IOCJson(self.pool).get_prop_value("iocroot")
        self.uuid = uuid
        self.jail = jail
        self.path = path
        self.release = IOCJson(self.path).get_prop_value("release")
        self.lgr = logging.getLogger('ioc_destroy')

        if silent:
            self.lgr.disabled = True

    def destroy_jail(self):
        """Destroys a jail and then attempts to destroy the snapshot"""
        self.lgr.info("Destroying {} ({})".format(self.uuid, self.jail))
        self.path = self.path.replace(self.iocroot, "/iocage")
        Popen(["zfs", "destroy", "-r", self.pool + self.path]).communicate()

        try:
            self.destroy_snapshot()
            self.destroy_tag()
        except CalledProcessError:
            pass

    def destroy_snapshot(self):
        """Destroys a snapshot for a jail."""
        try:
            check_call(["zfs", "destroy", "-R",
                        "{}/iocage/releases/{}@{}".format(self.pool,
                                                          self.release,
                                                          self.uuid)],
                       stdout=PIPE, stderr=PIPE)
        except CalledProcessError:
            pass

        try:
            # Old basejails.
            check_call(["zfs", "destroy", "-R",
                        "{}/iocage/base/{}@{}".format(self.pool,
                                                      self.release,
                                                      self.uuid)],
                       stdout=PIPE, stderr=PIPE)
            check_call(["zfs", "destroy", "-R",
                        "{}/iocage/base@{}".format(self.pool, self.uuid)],
                       stdout=PIPE, stderr=PIPE)
        except CalledProcessError:
            pass

    def destroy_tag(self):
        """Destroys the tag associated with the jail."""
        tags = "{}/tags".format(self.iocroot)
        try:
            os.remove("{}/{}".format(tags, self.jail))
        except OSError:
            pass
