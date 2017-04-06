"""iocage destroy module."""
import glob
import json
import logging
import os
import shutil
from subprocess import CalledProcessError, PIPE, Popen, check_call

import libzfs

from iocage.lib.ioc_json import IOCJson


class IOCDestroy(object):
    """
    Destroy a jail's datasets and then if they have a RELEASE snapshot,
    destroy that as well.
    """

    def __init__(self):
        self.pool = IOCJson().json_get_value("pool")
        self.iocroot = IOCJson(self.pool).json_get_value("iocroot")
        self.lgr = logging.getLogger('ioc_destroy')
        self.zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")
        self.ds = self.zfs.get_dataset

    @staticmethod
    def __stop_jails__(path=None):
        """Stops every jail running forcefully."""

        if path:
            # We got ourselves a template child!
            jls = Popen(["jls", "jid", "path", "--libxo", "json"],
                        stdout=PIPE).communicate()[0]
            jls = json.loads(jls)["jail-information"]["jail"]
            jid = [jail["jid"] for jail in jls if path in jail["path"]]

            if jid:
                try:
                    check_call(["jail", "-r", jid[0]])
                except CalledProcessError as err:
                    raise RuntimeError("{}".format(err))
        else:
            jid = Popen(["jls", "jid"], stdout=PIPE).communicate()[0].decode(
                "utf-8").split()

            for j in jid:
                try:
                    check_call(["jail", "-r", j])
                except CalledProcessError as err:
                    raise RuntimeError("{}".format(err))

    def __destroy_leftovers__(self, dataset, clean=False):
        """Removes tags, parent datasets and logs."""
        uuid = dataset.name.rsplit("/root")[0].split("/")[-1]
        tags = f"{self.iocroot}/tags"
        snapshot = False

        try:
            path = dataset.properties["mountpoint"].value
            umount_path = path.rstrip('/root')
        except libzfs.ZFSException as err:
            # This is either not mounted or doesn't exist anymore,
            # we don't care either way.
            if err.code == libzfs.Error.NOENT:
                path = None
            else:
                raise
        except KeyError:
            # This is a snapshot
            path = None
            snapshot = True

        if path:
            if "templates" in path and clean:
                for file in glob.glob(f"{tags}/*"):
                    if os.readlink(file) == f"{self.iocroot}/jails/" \
                                            f"{uuid}" or file == \
                            f"{self.iocroot}/tags/{uuid}":
                        os.remove(file)
            elif "jails" in path and clean:
                shutil.rmtree(f"{self.iocroot}/tags", ignore_errors=True)
                os.mkdir(f"{self.iocroot}/tags")

                shutil.rmtree(f"{self.iocroot}/log", ignore_errors=True)
            else:
                for file in glob.glob(f"{tags}/*"):
                    if os.readlink(file) == path:
                        os.remove(file)

                for file in glob.glob(f"{self.iocroot}/log/*"):
                    if file == f"{self.iocroot}/log/{uuid}-console.log":
                        os.remove(file)

            # Dangling mounts are bad...mmkay?
            Popen(["umount", "-afF", f"{umount_path}/fstab"],
                  stderr=PIPE).communicate()
            Popen(["umount", "-f", f"{umount_path}/root/dev/fd"],
                  stderr=PIPE).communicate()
            Popen(["umount", "-f", f"{umount_path}/root/dev"],
                  stderr=PIPE).communicate()
            Popen(["umount", "-f", f"{umount_path}/root/proc"],
                  stderr=PIPE).communicate()
            Popen(["umount", "-f", f"{umount_path}/root/compat/linux/proc"],
                  stderr=PIPE).communicate()

        if not clean and not snapshot:
            if any(_type in dataset.name for _type in ("jails", "templates",
                                                       "releases")):
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

    def __destroy_parse_datasets__(self, path, clean=False):
        """
        Parses the datasets before calling __destroy_dataset__ with each 
        entry.
        """
        datasets = self.ds(path)
        single = True if len(list(datasets.dependents)) == 0 else False
        dependents = datasets.dependents

        if single:
            # Is actually a single dataset.
            self.__destroy_dataset__(datasets)
        else:
            for dataset in dependents:
                if "templates" in path or "release" in path:
                    self.__stop_jails__(dataset.name.replace(self.pool, ""))

                self.__destroy_dataset__(dataset)
                self.__destroy_leftovers__(dataset, clean=clean)

    def destroy_jail(self, path, clean=False):
        """
        A convenience wrapper to call __stop_jails__ and  
        __destroy_parse_datasets__
        """
        dataset_type, uuid = path.rsplit("/")[-2:]

        if clean:
            self.__stop_jails__(path)
        else:
            from iocage.lib.ioc_stop import IOCStop
            conf = IOCJson(path).json_load()

            IOCStop(uuid, "", path, conf, silent=True)

        self.__destroy_parse_datasets__(
            f"{self.pool}/iocage/{dataset_type}/{uuid}")
