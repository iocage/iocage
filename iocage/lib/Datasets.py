import iocage.lib.helpers
import iocage.lib.errors

import libzfs


class Datasets:

    ZFS_POOL_ACTIVE_PROPERTY = "org.freebsd.ioc:active"

    def __init__(self, root=None, pool=None, zfs=None, logger=None):
        iocage.lib.helpers.init_logger(self, logger)
        iocage.lib.helpers.init_zfs(self, zfs)

        self._datasets = {}

        if isinstance(root, libzfs.ZFSDataset):
            self.root = root
            return

        if isinstance(pool, libzfs.ZFSPool):
            self.root = self._get_or_create_dataset(
                "iocage",
                root_name=pool.name,
                pool=pool
            )
            return

        active_pool = self.active_pool

        if active_pool is None:
            raise iocage.lib.errors.IocageNotActivated(logger=self.logger)
        else:
            self.root = self.zfs.get_dataset(f"{active_pool.name}/iocage")

    @property
    def active_pool(self):
        for pool in self.zfs.pools:
            if self._is_pool_active(pool):
                return pool
        return None

    @property
    def releases(self):
        return self._get_or_create_dataset("releases")

    @property
    def base(self):
        return self._get_or_create_dataset("base")

    @property
    def jails(self):
        return self._get_or_create_dataset("jails")

    @property
    def logs(self):
        return self._get_or_create_dataset("log")

    def activate(self, mountpoint=None):
        self.activate_pool(self.root.pool, mountpoint)

    def activate_pool(self, pool, mountpoint=None):

        if self._is_pool_active(pool):
            msg = f"ZFS pool '{pool.name}' is already active"
            self.logger.warn(msg)

        if not isinstance(pool, libzfs.ZFSPool):
            raise iocage.lib.errors.ZFSPoolInvalid("cannot activate")

        if pool.status == "UNAVAIL":
            raise iocage.lib.errors.ZFSPoolUnavailable(pool.name)

        other_pools = filter(lambda x: x.name != pool.name, self.zfs.pools)
        for other_pool in other_pools:
            self._deactivate_pool(other_pool)

        self._activate_pool(pool)

        root_dataset_args = {
            "pool": pool
        }

        if mountpoint is not None:
            root_dataset_args["mountpoint"] = mountpoint

        self.root = self._get_or_create_dataset(
            "iocage",
            **root_dataset_args
        )

    def _is_pool_active(self, pool):
        return "yes" == self._get_pool_property(
            pool,
            self.ZFS_POOL_ACTIVE_PROPERTY
        )

    def _get_pool_property(self, pool, prop):
        try:
            return pool.root_dataset.properties[prop].value
        except (KeyError, ValueError):
            return None

    def _get_dataset_property(self, dataset, prop):
        try:
            return dataset.properties[prop].value
        except:
            return None

    def _activate_pool(self, pool):
        self._set_pool_activation(pool, True)

    def _deactivate_pool(self, pool):
        self._set_pool_activation(pool, False)

    def _set_pool_activation(self, pool, state):
        value = "yes" if state is True else "no"
        self._set_zfs_property(
            pool.root_dataset,
            self.ZFS_POOL_ACTIVE_PROPERTY,
            value
        )

    def _set_zfs_property(self, dataset, name, value):
        current_value = self._get_dataset_property(dataset, name)
        if current_value != value:
            self.logger.verbose(
                f"Set ZFS property {name}='{value}'"
                f" on dataset '{dataset.name}'"
            )
            dataset.properties[name] = libzfs.ZFSUserProperty(value)

    def _get_or_create_dataset(self,
                               name,
                               root_name=None,
                               pool=None,
                               mountpoint=None):

        try:
            return self.datasets[name]
        except (AttributeError, KeyError):
            pass

        if root_name is None:
            root_name = self.root.name

        if pool is None:
            pool = self.root.pool

        name = f"{root_name}/{name}"
        try:
            dataset = self.zfs.get_dataset(name)
        except:
            pool.create(name, {})
            dataset = self.zfs.get_dataset(name)

            if mountpoint is not None:
                mountpoint_property = libzfs.ZFSUserProperty(mountpoint)
                dataset.properties["mountpoint"] = mountpoint_property

            dataset.mount()
        self._datasets[name] = dataset

        return dataset
