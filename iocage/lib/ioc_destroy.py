"""iocage destroy module."""
import glob
import json
import os
import shutil
import subprocess as su

import libzfs

import iocage.lib.ioc_json
import iocage.lib.ioc_stop


class IOCDestroy(object):
    """
    Destroy a jail's datasets and then if they have a RELEASE snapshot,
    destroy that as well.
    """

    def __init__(self):
        self.pool = iocage.lib.ioc_json.IOCJson().json_get_value("pool")
        self.iocroot = iocage.lib.ioc_json.IOCJson(self.pool).json_get_value(
            "iocroot")
        self.zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")
        self.ds = self.zfs.get_dataset

    @staticmethod
    def __stop_jails__(datasets, path=None, root=False):
        for dataset in datasets.dependents:
            if "jails" in dataset.name:
                # This is just to setup a replacement.
                path = path.replace("templates", "jails")
                uuid = dataset.name.partition(f"{path}/")[2].rsplit("/", 1)[0]
                # We want the real path now.
                if dataset.type == libzfs.DatasetType.FILESYSTEM:
                    _path = dataset.properties["mountpoint"].value.replace(
                        "/root", "")

                    if dataset.name.endswith(uuid) or root:
                        conf = iocage.lib.ioc_json.IOCJson(_path).json_load()
                        iocage.lib.ioc_stop.IOCStop(uuid, "", _path, conf,
                                                    silent=True)

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
            path = path.replace("/root", "")

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
            su.Popen(["umount", "-afF", f"{umount_path}/fstab"],
                     stderr=su.PIPE).communicate()
            su.Popen(["umount", "-f", f"{umount_path}/root/dev/fd"],
                     stderr=su.PIPE).communicate()
            su.Popen(["umount", "-f", f"{umount_path}/root/dev"],
                     stderr=su.PIPE).communicate()
            su.Popen(["umount", "-f", f"{umount_path}/root/proc"],
                     stderr=su.PIPE).communicate()
            su.Popen(["umount", "-f", f"{umount_path}/root/compat/linux/proc"],
                     stderr=su.PIPE).communicate()

        if not snapshot:
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
            if "templates" in path or "release" in path:
                # This will tell __stop_jails__ to actually try stopping on
                # a /root
                root = True
            else:
                # Otherwise we only stop when the uuid is the last entry in
                # the jails path.
                root = False

            self.__stop_jails__(datasets, path, root)

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
        else:
            conf = iocage.lib.ioc_json.IOCJson(path).json_load()
            iocage.lib.ioc_stop.IOCStop(uuid, "", path, conf, silent=True)

            self.__destroy_parse_datasets__(
                f"{self.pool}/iocage/{dataset_type}/{uuid}")
