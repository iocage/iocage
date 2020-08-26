# Copyright (c) 2014-2019, iocage
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
import threading
import shutil

import iocage_lib.ioc_common
import iocage_lib.ioc_json

from iocage_lib.cache import cache
from iocage_lib.dataset import Dataset
from iocage_lib.zfs import ZFSException

DATASET_CREATION_LOCK = threading.Lock()


class IOCCheck(object):

    """Checks if the required iocage datasets are present"""

    def __init__(
        self, silent=False, callback=None, migrate=False, reset_cache=False,
    ):
        self.reset_cache = reset_cache
        if reset_cache:
            cache.reset()
        self.pool = iocage_lib.ioc_json.IOCJson(
            silent=silent,
            checking_datasets=True
        ).json_get_value("pool")
        self.callback = callback
        self.silent = silent

        self.__check_fd_mount__()
        self.__check_datasets__()

        self.pool_root_dataset = Dataset(self.pool, cache=reset_cache)
        self.iocage_dataset = Dataset(
            os.path.join(self.pool, 'iocage'), cache=reset_cache
        )

        if migrate:
            self.__check_migrations__()

        self.__clean_files__()

    def __clean_files__(self):
        shutil.rmtree(
            os.path.join(self.iocage_dataset.path, '.plugin_index'),
            ignore_errors=True
        )

    def __check_migrations__(self):
        if not self.iocage_dataset.path.startswith(
            self.pool_root_dataset.path
        ):
            self.iocage_dataset.inherit_property('mountpoint')

    def __check_datasets__(self):
        """
        Loops through the required datasets and if there is root
        privilege will then create them.
        """
        datasets = ("iocage", "iocage/download", "iocage/images",
                    "iocage/jails", "iocage/log", "iocage/releases",
                    "iocage/templates")

        for dataset in datasets:
            zfs_dataset_name = f"{self.pool}/{dataset}"
            try:
                ds = Dataset(zfs_dataset_name, cache=self.reset_cache)

                if not ds.exists:
                    raise ZFSException(-1, 'Dataset does not exist')
                elif not ds.path:
                    iocage_lib.ioc_common.logit({
                        "level": "EXCEPTION",
                        "message": f'Please set a mountpoint on {ds.name}'
                    },
                        _callback=self.callback)
            except ZFSException:
                # Doesn't exist

                if os.geteuid() != 0:
                    raise RuntimeError("Run as root to create missing"
                                       " datasets!")

                iocage_lib.ioc_common.logit({
                    "level": "INFO",
                    "message": f"Creating {self.pool}/{dataset}"
                },
                    _callback=self.callback,
                    silent=self.silent)

                dataset_options = {
                    "compression": "lz4",
                    "aclmode": "passthrough",
                    "aclinherit": "passthrough"
                }

                with DATASET_CREATION_LOCK:
                    ds = Dataset(zfs_dataset_name, cache=self.reset_cache)
                    if not ds.exists:
                        ds.create({'properties': dataset_options})

            prop = ds.properties.get("exec")
            if prop != "on":
                iocage_lib.ioc_common.logit({
                    "level": "EXCEPTION",
                    "message": f"Dataset \"{dataset}\" has "
                               f"exec={prop} (should be on)"
                },
                    _callback=self.callback)

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

            iocage_lib.ioc_common.logit({
                "level": level,
                "message": msg
            },
                _callback=self.callback,
                silent=self.silent)
