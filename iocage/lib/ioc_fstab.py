"""Manipulate a jails fstab"""
import logging
from datetime import datetime

from iocage.lib.ioc_common import open_atomic
from iocage.lib.ioc_json import IOCJson


class IOCFstab(object):
    """Will add or remove an entry, and mount or umount the filesystem."""

    def __init__(self, uuid, tag, action, source, destination, fstype,
                 fsoptions, fsdump, fspass, index=None, silent=False):
        self.lgr = logging.getLogger('ioc_fstab')
        self.pool = IOCJson().json_get_value("pool")
        self.iocroot = IOCJson(self.pool).json_get_value("iocroot")
        self.uuid = uuid
        self.tag = tag
        self.action = action
        self.src = source
        self.dest = destination
        self.fstype = fstype
        self.fsoptions = fsoptions
        self.fsdump = fsdump
        self.fspass = fspass
        self.index = index
        self.mount = "{}\t{}\t{}\t{}\t{}\t{}".format(self.src, self.dest,
                                                     self.fstype,
                                                     self.fsoptions,
                                                     self.fsdump,
                                                     self.fspass)

        if silent:
            self.lgr.disabled = True

        self.__fstab_parse__()

    def __fstab_parse__(self):
        if self.action == "add":
            self.__fstab_add__()
        elif self.action == "remove":
            self.__fstab_remove__()
        else:
            raise RuntimeError("Type of operation not specified!")

    def __fstab_add__(self):
        with open("{}/jails/{}/fstab".format(self.iocroot,
                                             self.uuid), "r") as \
                fstab:
            with open_atomic("{}/jails/{}/fstab".format(self.iocroot,
                                                        self.uuid), "w"
                             ) as _fstab:
                # open_atomic will empty the file, we need these still.
                for line in fstab.readlines():
                    _fstab.write(line)

                _fstab.write("{} # Added by iocage on {}\n".format(
                    self.mount, datetime.utcnow().strftime("%F %T")))

        self.lgr.info(
            "Successfully added mount to {} ({})'s fstab".format(self.uuid,
                                                                 self.tag))

    def __fstab_remove__(self):
        removed = False
        index = 0

        with open("{}/jails/{}/fstab".format(self.iocroot,
                                             self.uuid), "r") as \
                fstab:
            with open_atomic("{}/jails/{}/fstab".format(self.iocroot,
                                                        self.uuid), "w"
                             ) as _fstab:
                for line in fstab.readlines():
                    if line.rsplit("#")[0].rstrip() == self.mount or index \
                            == self.index and not removed:
                        removed = True
                        continue
                    else:
                        _fstab.write(line)

                    index += 1
        if removed:
            self.lgr.info(
                "Successfully removed mount from {} ({})'s fstab".format(
                    self.uuid, self.tag))
        else:
            self.lgr.info("No fstab entry matching: {}".format(self.mount))
