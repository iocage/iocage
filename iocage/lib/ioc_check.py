# Copyright (c) 2014-2017, iocage
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""Check datasets before execution"""
import collections
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

        self.__check_fd_mount__()
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
        zpools = zfs.pools
        iocage_datasets = []
        for p in zpools:
            try:
                z = zfs.get_dataset(f"{p.name}/iocage")
                iocage_datasets.append(z)
            except libzfs.ZFSException:
                # Doesn't exist, that's fine
                continue

        pool = zfs.get(self.pool)
        has_duplicates = len(list(filter(lambda x: x.mountpoint == "/iocage",
                                         iocage_datasets))) > 0

        for dataset in datasets:
            zfs_dataset_name = f"{self.pool}/{dataset}"
            try:
                zfs.get_dataset(zfs_dataset_name)
            except libzfs.ZFSException:
                # Doesn't exist
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
                zfs.get_dataset(zfs_dataset_name).mount()

    def __check_fd_mount__(self):
        """
        Checks if /dev/fd is mounted, and if not, give the user a
        warning.
        """
        if os.path.ismount("/dev/fd"):
            # all good!
            return

        messages = collections.OrderedDict([
            ("1-NOTICE", "*" * 80),
            ("2-WARNING", "fdescfs(5) is not mounted, performance"
                          " may suffer. Please run:"),
            ("3-INFO", "mount -t fdescfs null /dev/fd"),
            ("4-WARNING", "You can also permanently mount it in"
                          " /etc/fstab with the following entry:"),
            ("5-INFO", "fdescfs /dev/fd  fdescfs  rw  0  0"),
            ("6-NOTICE", f"{'*' * 80}\n")
        ])

        for level, msg in messages.items():
            level = level.partition("-")[2]

            iocage.lib.ioc_common.logit({
                "level"  : level,
                "message": msg
            },
                _callback=self.callback,
                silent=self.silent)
