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
        self.zfs = libzfs.ZFS()
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
                    raise RuntimeError("ERROR: {}".format(err))
        else:
            jid = Popen(["jls", "jid"], stdout=PIPE).communicate()[0].decode(
                "utf-8").split()

            for j in jid:
                try:
                    check_call(["jail", "-r", j])
                except CalledProcessError as err:
                    raise RuntimeError("ERROR: {}".format(err))

    def __destroy_datasets__(self, path, clean=False):
        """Destroys the given datasets and snapshots."""
        datasets = self.ds(path)

        for dataset in datasets.dependents:
            if "templates" in path:
                self.__stop_jails__(dataset.name.replace(self.pool, ""))

            if dataset.type == libzfs.DatasetType.FILESYSTEM:
                origin = dataset.properties["origin"].value

                try:
                    snap_dataset, snap = origin.split("@")
                    self.ds(snap_dataset).destroy_snapshot(snap)
                except ValueError:
                    pass  # This means we don't have an origin.

                dataset.umount(force=True)

            dataset.delete()

            if clean:
                if "templates" in path:
                    if "jails" in dataset.name:
                        # The jails parent won't show in the list.
                        j_parent = self.ds(
                            f"{dataset.name.replace('/root','')}")

                        j_parent.umount(force=True)
                        j_parent.delete()

                    # In the case of a template this will actually be the tag.
                    uuid = dataset.name.rsplit("/root")[0].split("/")[-1]
                    tags = f"{self.iocroot}/tags"

                    for file in glob.glob(f"{tags}/*"):
                        if os.readlink(file) == f"{self.iocroot}/jails/{" \
                                                f"uuid}" \
                                or file == f"{self.iocroot}/tags/{uuid}":
                            os.remove(file)

                    for file in glob.glob(f"{self.iocroot}/log/*"):
                        if file == f"{self.iocroot}/log/{uuid}-console.log":
                            os.remove(file)
                elif "jails" in path:
                    shutil.rmtree(f"{self.iocroot}/tags", ignore_errors=True)
                    os.mkdir(f"{self.iocroot}/tags")

                    shutil.rmtree(f"{self.iocroot}/log", ignore_errors=True)
            else:
                if "jails" in dataset.name or "templates" in dataset.name:
                    # The jails parent won't show in the list.
                    j_parent = self.ds(
                        f"{dataset.name.replace('/root','')}")

                    j_parent.umount(force=True)
                    j_parent.delete()

                uuid = dataset.name.rsplit("/root")[0].split("/")[-1]
                tags = f"{self.iocroot}/tags"

                for file in glob.glob(f"{tags}/*"):
                    if os.readlink(file) == f"{self.iocroot}/jails/{uuid}":
                        os.remove(file)

                for file in glob.glob(f"{self.iocroot}/log/*"):
                    if file == f"{self.iocroot}/log/{uuid}-console.log":
                        os.remove(file)

    def destroy_jail(self, path):
        """
        A convenience wrapper to call __stop_jails__ and  __destroy_datasets__
        """
        dataset_type = path.rsplit("/")[-2]
        uuid = path.rsplit("/")[-1]  # Is a tag if dataset_type is template

        self.__stop_jails__(path)
        self.__destroy_datasets__(f"{self.pool}/iocage/{dataset_type}/{uuid}")
