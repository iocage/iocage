import iocage.lib.helpers

import pwd
import grp
import os


class Storage:

    def __init__(self, jail,
                 zfs=None,
                 auto_create=False,
                 safe_mode=True,
                 logger=None):

        iocage.lib.helpers.init_logger(self, logger)
        iocage.lib.helpers.init_zfs(self, zfs)

        self.jail = jail

        # when auto_create is enabled, non-existing zfs volumes will be
        # automatically created if not enabled, accessing non-existent
        # datasets will raise an error
        self.auto_create = auto_create

        # safe-mody only attaches zfs datasets to jails that were tagged with
        # jailed=on already exist
        self.safe_mode = safe_mode

    @property
    def jail_root_dataset(self):
        return self.zfs.get_dataset(self.jail_root_dataset_name)

    @property
    def jail_root_dataset_name(self):
        return f"{self.jail.dataset.name}/root"

    @property
    def _pool(self):
        return self.jail.host.datasets.root.pool

    def clone_release(self, release):
        self.clone_zfs_dataset(
            release.root_dataset.name,
            self.jail_root_dataset_name
        )
        jail_name = self.jail.humanreadable_name
        self.logger.verbose(
            f"Cloned release '{release.name}' to {jail_name}",
            jail=self.jail
        )

    def delete_dataset_recursive(self, dataset, delete_snapshots=True):

        for child in dataset.children:
            self.delete_dataset_recursive(child)

        if dataset.mountpoint is not None:
            self.logger.spam("Unmounting {dataset.name}")
            dataset.umount()

        origin = None
        if delete_snapshots is False:
            origin_property = dataset.properties["origin"]
            if origin_property.value != "":
                origin = origin_property

        self.logger.verbose("Deleting dataset {dataset.name}")
        dataset.delete()

        if origin is not None:
            self.logger.verbose("Deleting snapshot {origin}")
            origin_snapshot = self.zfs.get_snapshot(origin)
            origin_snapshot.delete()

    def clone_zfs_dataset(self, source, target):

        snapshot_name = f"{source}@{self.jail.name}"

        # delete target dataset if it already exists
        try:
            existing_dataset = self.zfs.get_dataset(target)
            self.logger.verbose(
                f"Deleting existing dataset {target}",
                jail=self.jail
            )
            if existing_dataset.mountpoint is not None:
                existing_dataset.umount()
            existing_dataset.delete()
            del existing_dataset
        except:
            pass

        # delete existing snapshot if existing
        existing_snapshot = None
        try:
            existing_snapshot = self.zfs.get_snapshot(snapshot_name)
        except:
            pass

        if existing_snapshot:
            self.logger.verbose(
                f"Deleting existing snapshot {snapshot_name}",
                jail=self.jail
            )
            existing_snapshot.delete()

        # snapshot release
        self.zfs.get_dataset(source).snapshot(snapshot_name)
        snapshot = self.zfs.get_snapshot(snapshot_name)

        # clone snapshot
        try:
            self.logger.verbose(
                f"Cloning snapshot {snapshot_name} to {target}",
                jail=self.jail
            )
            snapshot.clone(target)
        except:
            parent = "/".join(target.split("/")[:-1])
            self.logger.debug(
                "Cloning was unsuccessful - "
                f"trying to create the parent dataset '{parent}' first",
                jail=self.jail
            )
            self._create_dataset(parent)
            snapshot.clone(target)

        target_dataset = self.zfs.get_dataset(target)
        target_dataset.mount()
        self.logger.verbose(
            f"Successfully cloned {source} to {target}",
            jail=self.jail
        )

    def create_jail_dataset(self):
        self._create_dataset(self.jail.dataset_name)

    def create_jail_root_dataset(self):
        self._create_dataset(self.jail_root_dataset_name)

    def get_or_create_jail_root_dataset(self):
        try:
            return self.jail_root_dataset
        except:
            self.create_jail_root_dataset()
        return self.jail_root_dataset

    def create_jail_mountpoint(self, basedir):
        basedir = f"{self.jail_root_dataset.mountpoint}/{basedir}"
        if not os.path.isdir(basedir):
            self.logger.verbose(f"Creating mountpoint {basedir}")
            os.makedirs(basedir)

    def _create_dataset(self, name, mount=True):
        self.logger.verbose(f"Creating ZFS dataset {name}")
        self._pool.create(name, {}, create_ancestors=True)
        if mount:
            ds = self.zfs.get_dataset(name)
            ds.mount()
        self.logger.spam(f"ZFS dataset {name} created")

    def _mount_procfs(self):
        try:
            if self.jail.config["mount_procfs"]:
                iocage.lib.helpers.exec([
                    "mount"
                    "-t",
                    "procfs"
                    "proc"
                    f"{self.path}/root/proc"
                ])
        except:
            raise iocage.lib.errors.MountFailed("procfs")

    # ToDo: Remove unused function?
    def _mount_linprocfs(self):
        try:
            if not self.jail.config["mount_linprocfs"]:
                return
        except:
            pass

        linproc_path = "compat/linux/proc"
        self._jail_mkdirp(f"{self.path}/root/{linproc_path}")

        try:
            if self.jail.config["mount_procfs"]:
                iocage.lib.helpers.exec([
                    "mount"
                    "-t",
                    "linprocfs"
                    "linproc"
                    f"{self.path}/root/{linproc_path}"
                ])
        except:
            raise iocage.lib.errors.MountFailed("linprocfs")

    def _unmount_local(self, dataset):
        if dataset.mountpoint:
            dataset.unmount()

    def _jail_mkdirp(self, directory,
                     permissions=0o775,
                     user="root",
                     group="wheel"):

        uid = pwd.getpwnam(user).pw_uid
        gid = grp.getgrnam(group).gr_gid
        folder = f"{self.jail.path}/{directory}"
        if not os.path.isdir(folder):
            os.mkdirs(folder, permissions)
            os.chown(folder, uid, gid, follow_symlinks=False)
