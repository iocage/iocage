import iocage.lib.helpers


class ZFSBasejailStorage:

    def prepare(self):
        self._delete_clone_target_datasets()

    def apply(self, release=None):

        if release is None:
            release = self.jail.cloned_release

        return ZFSBasejailStorage.clone(self, release)

    def setup(self, release):
        iocage.lib.StandaloneJailStorage.StandaloneJailStorage.setup(
            self, release)

    def clone(self, release):

        current_basejail_type = self.jail.config["basejail_type"]
        if not current_basejail_type == "zfs":

            raise iocage.lib.errors.InvalidJailConfigValue(
                property_name="basejail_type",
                reason="Expected ZFS, but saw {current_basejail_type}",
                logger=self.logger
            )

        ZFSBasejailStorage._create_mountpoints(self)

        for basedir in iocage.lib.helpers.get_basedir_list():
            source_dataset_name = f"{release.base_dataset.name}/{basedir}"
            target_dataset_name = f"{self.jail_root_dataset_name}/{basedir}"
            self.clone_zfs_dataset(source_dataset_name, target_dataset_name)

    def _delete_clone_target_datasets(self, root=None):

        if root is None:
            root = list(self.jail_root_dataset.children)

        for child in root:
            root_dataset_prefix = f"{self.jail_root_dataset_name}/"
            relative_name = child.name.replace(root_dataset_prefix, "")
            basedirs = iocage.lib.helpers.get_basedir_list()

            if relative_name in basedirs:

                # Unmount if mounted
                try:
                    current_mountpoint = child.mountpoint
                    if current_mountpoint:
                        child.umount()
                        self.logger.verbose(
                            f"Clone target {current_mountpoint} unmounted"
                        )
                except:
                    pass

                # Delete existing snapshots
                for snapshot in child.snapshots:
                    try:
                        snapshot.delete()
                        self.logger.verbose(
                            f"Snapshot {current_mountpoint} deleted"
                        )
                    except:
                        pass

                child.delete()

            else:
                self._delete_clone_target_datasets(list(child.children))

    def _create_mountpoints(self):
        for basedir in ["dev", "etc"]:
            self.create_jail_mountpoint(basedir)
