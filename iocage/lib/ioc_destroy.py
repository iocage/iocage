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
"""iocage destroy module."""
import glob
import os
import subprocess as su

import iocage.lib.ioc_json
import iocage.lib.ioc_stop
import libzfs


class IOCDestroy(object):
    """
    Destroy a jail's datasets and then if they have a RELEASE snapshot,
    destroy that as well.
    """

    def __init__(self, exit_on_error=False):
        self.pool = iocage.lib.ioc_json.IOCJson(
            exit_on_error=exit_on_error).json_get_value("pool")
        self.iocroot = iocage.lib.ioc_json.IOCJson(
            self.pool, exit_on_error=exit_on_error).json_get_value("iocroot")
        self.zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")
        self.ds = self.zfs.get_dataset

    @staticmethod
    def __stop_jails__(datasets, path=None, root=False):
        for dataset in datasets.dependents:
            if "jails" not in dataset.name:
                continue

            if dataset.type != libzfs.DatasetType.FILESYSTEM:
                continue

            if dataset.properties["mountpoint"].value == 'legacy':
                continue

            # This is just to setup a replacement.
            path = path.replace("templates", "jails")
            uuid = dataset.name.partition(f"{path}/")[2].rsplit("/", 1)[0]
            # We want the real path now.
            _path = dataset.properties["mountpoint"].value.replace("/root", "")
            # It gives us a string that says "none", not terribly
            # useful, fixing that.
            _path = _path if _path != "none" else None

            if (dataset.name.endswith(uuid) or root) and _path is not None:
                conf = iocage.lib.ioc_json.IOCJson(_path).json_load()
                iocage.lib.ioc_stop.IOCStop(uuid, _path, conf, silent=True)

    def __destroy_leftovers__(self, dataset, clean=False):
        """Removes parent datasets and logs."""
        uuid = dataset.name.rsplit("/root")[0].split("/")[-1]
        snapshot = False

        try:
            path = dataset.properties["mountpoint"].value
            umount_path = path.rstrip('/root')
        except libzfs.ZFSException as err:
            # This is either not mounted or doesn't exist anymore,
            # we don't care either way.

            if err.code != libzfs.Error.NOENT:
                raise
            path = None
        except KeyError:
            # This is a snapshot
            path = None
            snapshot = True

        if path:
            for file in glob.glob(f"{self.iocroot}/log/*"):
                if file == f"{self.iocroot}/log/{uuid}-console.log":
                    os.remove(file)

            # Dangling mounts are bad...mmkay?
            su.Popen(
                ["umount", "-afF", f"{umount_path}/fstab"],
                stderr=su.PIPE).communicate()
            su.Popen(
                ["umount", "-f", f"{umount_path}/root/dev/fd"],
                stderr=su.PIPE).communicate()
            su.Popen(
                ["umount", "-f", f"{umount_path}/root/dev"],
                stderr=su.PIPE).communicate()
            su.Popen(
                ["umount", "-f", f"{umount_path}/root/proc"],
                stderr=su.PIPE).communicate()
            su.Popen(
                ["umount", "-f", f"{umount_path}/root/compat/linux/proc"],
                stderr=su.PIPE).communicate()

        if not snapshot and \
                any(_type in dataset.name for _type
                    in ("jails", "templates", "releases")):
            # The jails parent won't show in the list.
            j_parent = self.ds(f"{dataset.name.replace('/root','')}")
            j_dependents = j_parent.dependents

            for j_dependent in j_dependents:
                if j_dependent.type == libzfs.DatasetType.FILESYSTEM:
                    j_dependent.umount(force=True)

                j_dependent.delete()

            j_parent.umount(force=True)
            j_parent.delete()

    def __destroy_dataset__(self, dataset):
        """Destroys the given datasets and snapshots."""

        if dataset.type == libzfs.DatasetType.FILESYSTEM:
            origin = dataset.properties["origin"].value

            try:
                snap_dataset, snap = origin.split("@")
                self.ds(snap_dataset).destroy_snapshot(snap)
            except ValueError:
                pass  # This means we don't have an origin.

            dataset.umount(force=True)

        dataset.delete()

    def __destroy_parse_datasets__(self, path, clean=False, stop=True):
        """
        Parses the datasets before calling __destroy_dataset__ with each
        entry.
        """
        try:
            datasets = self.ds(path)
        except libzfs.ZFSException:
            # Dataset can't be found, we don't care

            return

        single = True if len(list(datasets.dependents)) == 0 else False
        dependents = datasets.dependents

        if single:
            # Is actually a single dataset.
            self.__destroy_dataset__(datasets)
        else:
            if "templates" in path or "release" in path:
                # This will tell __stop_jails__ to actually try stopping on
                # a /root
                root = True
            else:
                # Otherwise we only stop when the uuid is the last entry in
                # the jails path.
                root = False

            if stop:
                try:
                    self.__stop_jails__(datasets, path, root)
                except (RuntimeError, FileNotFoundError, SystemExit):
                    # If a bad or missing configuration for a jail, this will
                    # get in the way.
                    pass

            for dataset in dependents:
                try:
                    self.__destroy_dataset__(dataset)
                    self.__destroy_leftovers__(dataset, clean=clean)
                except libzfs.ZFSException as err:
                    # This is either not mounted or doesn't exist anymore,
                    # we don't care either way.

                    if err.code == libzfs.Error.NOENT:
                        continue
                    else:
                        raise

    def destroy_jail(self, path, clean=False):
        """
        A convenience wrapper to call __stop_jails__ and
         __destroy_parse_datasets__
        """
        dataset_type, uuid = path.rsplit("/")[-2:]

        if clean:
            self.__destroy_parse_datasets__(path)

            return

        try:
            conf = iocage.lib.ioc_json.IOCJson(path).json_load()
            iocage.lib.ioc_stop.IOCStop(uuid, path, conf, silent=True)
        except (FileNotFoundError, RuntimeError, libzfs.ZFSException,
                SystemExit):
            # Broad exception as we don't care why this failed. iocage
            # may have been killed before configuration could be made,
            # it's meant to be nuked.
            pass

        try:
            self.__destroy_parse_datasets__(
                f"{self.pool}/iocage/{dataset_type}/{uuid}")
        except (libzfs.ZFSException, SystemExit):
            # The dataset doesn't exist, we don't care :)
            pass
