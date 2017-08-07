import helpers

import libzfs


class Datasets:

    ZFS_POOL_ACTIVE_PROPERTY = "org.freebsd.ioc:active"

    def __init__(self, root=None, pool=None, zfs=None, logger=None):
        helpers.init_logger(self, logger)
        helpers.init_zfs(self, zfs)

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
            msg = ("iocage is not activated yet - "
                   "please run `iocage activate` first and select a pool")
            self.logger.error(msg)
            raise Exception(msg)
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

    def activate(self):
        self.activate_pool(self.root.pool)

    def activate_pool(self, pool):

        if self._is_pool_active(pool):
            msg = f"ZFS pool '{pool.name}' is already active"
            self.logger.warn(msg)

        if not isinstance(pool, libzfs.ZFSPool):
            msg = "Cannot activate invalid ZFS pool"
            self.logger.error(msg)
            raise Exception(msg)

        if pool.status == "UNAVAIL":
            msg = f"ZFS pool '{pool.name}' is UNAVAIL"
            self.logger.error(msg)
            raise Exception(msg)

        other_pools = filter(lambda x: x.name != pool.name, self.zfs.pools)
        for other_pool in other_pools:
            self._deactivate_pool(other_pool)

        self._activate_pool(pool)

        self.root = self._get_or_create_dataset(
            "iocage",
            pool=pool
        )

    def _is_pool_active(self, pool):
        prop = self.ZFS_POOL_ACTIVE_PROPERTY
        return self._get_pool_property(pool, prop) == "yes"

    def _get_pool_property(self, pool, prop):
        try:
            return pool.root_dataset.properties[prop].value
        except:
            return None

    def _get_dataset_property(self, dataset, prop):
        try:
            return dataset.properties[prop].value
        except:
            return None

    def _activate_pool(self, pool):
        self._set_pool_activation(pool.root_dataset, True)

    def _deactivate_pool(self, pool):
        self._set_pool_activation(pool.root_dataset, False)

    def _set_pool_activation(self, pool, state):
        prop = self.ZFS_POOL_ACTIVE_PROPERTY
        value = "yes" if state is True else "no"
        self._set_zfs_property(pool.root_dataset, prop, value)

    def _set_zfs_property(self, dataset, name, value):

        current_value = self._get_dataset_property(name)

        if current_value != value:
            self.logger.verbose(
                f"Set ZFS property {name}='{value}'"
                f" on dataset '{dataset.name}'"
            )
            dataset.properties[name] = libzfs.ZFSUserProperty(value)

    def _get_or_create_dataset(self, name, root_name=None, pool=None):

        try:
            return self.datasets[name]
        except:
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
            dataset.mount()
        self._datasets[name] = dataset

        return dataset
