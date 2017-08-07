import helpers

import pwd
import grp
import os


class Storage:

    def __init__(self, jail,
                 zfs=None,
                 auto_create=False,
                 safe_mode=True,
                 logger=None):

        helpers.init_logger(self, logger)
        helpers.init_zfs(self, zfs)

        self.jail = jail

        # when auto_create is enabled, non-existing zfs volumes will be
        # automatically created if not enabled, accessing non-existent
        # datasets will raise an error
        self.auto_create = auto_create

        # safe-mody only attaches zfs datasets to jails that were tagged with
        # jailed=on already exist
        self.safe_mode = safe_mode

    @property
    def zfs_datasets(self):
        return self.get_zfs_datasets(self.auto_create)

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

    def clone_zfs_dataset(self, source, target):

        snapshot_name = f"{source}@{self.jail.name}"

        # delete target dataset if it already exists
        try:
            self.logger.verbose(
                f"Deleting existing dataset {target}",
                jail=self.jail
            )
            existing_dataset = self.zfs.get_dataset(target)
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
                "Cloning was unsuccessful -"
                " trying to create the dataset first",
                jail=self.jail
            )
            self._create_dataset(parent)
            self._pool.create(parent, {}, create_ancestors=True)
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

    def _create_dataset(self, name, mount=True):
        self.logger.verbose(f"Creating ZFS dataset {name}")
        self._pool.create(name, {}, create_ancestors=True)
        if mount:
            ds = self.zfs.get_dataset(name)
            ds.mount()

    def _require_datasets_exist_and_jailed(self):
        existing_datasets = self.get_zfs_datasets(auto_create=False)
        for existing_dataset in existing_datasets:
            if existing_dataset.properties["jailed"] != "on":
                name = existing_dataset.name
                raise Exception(
                    f"Dataset {name} is not jailed."
                    f"Run 'zfs set jailed=on {name}' to allow mounting"
                )

    def _mount_jail_datasets(self, auto_create=None):

        auto_create = self.auto_create if auto_create is None else (
            auto_create is True)

        if self.safe_mode:
            self._require_datasets_exist_and_jailed()

        for dataset in self.zfs_datasets:

            self._unmount_local(dataset)

            # ToDo: bake jail feature into py-libzfs
            helpers.exec(
                ["zfs", "jail", self.jail.identifier, dataset.name])

            if dataset.properties['mountpoint']:
                for child in list(dataset.children):
                    self._ensure_dataset_exists(child)
                    self._mount_jail_dataset(child.name)

    def _mount_procfs(self):
        try:
            if self.jail.config.mount_procfs:
                helpers.exec([
                    "mount"
                    "-t",
                    "procfs"
                    "proc"
                    f"{self.path}/root/proc"
                ])
        except:
            msg = "Failed mounting procfs"
            self.logger.error(msg)
            raise Exception(msg)

    # ToDo: Remove unused function?
    def _mount_linprocfs(self):
        try:
            if not self.jail.config.mount_linprocfs:
                return
        except:
            pass

        linproc_path = "compat/linux/proc"
        self._jail_mkdirp(f"{self.path}/root/{linproc_path}")

        try:
            if self.jail.config.mount_procfs:
                helpers.exec([
                    "mount"
                    "-t",
                    "linprocfs"
                    "linproc"
                    f"{self.path}/root/{linproc_path}"
                ])
        except:
            msg = "Failed mounting linprocfs"
            self.logger.error(msg)
            raise Exception(msg)

    def _get_pool_name_from_dataset_name(self, dataset_name):
        return dataset_name.split("/", maxsplit=1)[0]

    def _get_pool_from_dataset_name(self, dataset_name):
        target_pool_name = self._get_pool_name_from_dataset_name(dataset_name)
        for zpool in list(self.zfs.pools):
            if zpool.name == target_pool_name:
                return zpool
        raise Exception(f"zpool {target_pool_name} does not exist")

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
