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
            self.root = self._get_or_create_dataset("iocage", root_name=pool.name)
            return

        active_pool = self.active_pool

        if active_pool is None:
            msg = ("iocage is not activated yet - "
                   "please run `iocage activate` first and select a pool")
            self.logger.error(msg)
            raise Exception(msg)
        else:
            self.root = active_pool.root_dataset
                

    @property
    def active_pool(self):
        prop = self.ZFS_POOL_ACTIVE_PROPERTY
        for pool in self.zfs.pools:
            if pool.root_dataset.properties[prop] == "yes":
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

    def activate(self):
        self.activate_pool(self.root.pool)

    def activate_pool(self, zfs_pool):

        prop = self.ZFS_POOL_ACTIVE_PROPERTY

        is_pool_already_active = False
        try:
            if zfs_pool.root_dataset.properties[prop].value == "yes":
                is_pool_already_active = True
        except:
            pass

        if is_pool_already_active:
            msg = f"ZFS pool '{zfs_pool.name}' is already active"
            self.logger.error(msg)
            raise Exception(msg)

        if not isinstance(zfs_pool, libzfs.ZFSPool):
            print(zfs_pool)
            msg = "Cannot activate invalid ZFS pool"
            self.logger.error(msg)
            raise Exception(msg)

        if zfs_pool.status == "UNAVAIL":
            msg = f"ZFS pool '{zfs_pool.name}' is UNAVAIL"
            self.logger.error(msg)
            raise Exception(msg)

        for pool in self.zfs.pools:
            if (pool.name != zfs_pool.name):
                self._set_zfs_property(pool.root_dataset, prop, "no")

        self._set_zfs_property(zfs_pool.root_dataset, prop, "yes")

    def _set_zfs_property(self, dataset, name, value):

        current_value = None
        try:
            current_value = dataset.properties[name].value
        except:
            pass

        if current_value != value:
            self.logger.verbose(
                f"Set ZFS property {name}='{value}' on dataset '{dataset.name}'"
            )
            dataset.properties[name] = libzfs.ZFSUserProperty(value)

    def _get_or_create_dataset(self, name, root_name=None):

        try:
            return self.datasets[name]
        except:
            pass

        if root_name is None:
            root_name = self.root.name

        name = f"{root_name}/{name}"
        try:
            dataset = self.zfs.get_dataset(name)
        except:
            self.root.pool.create(name, {})
            dataset = self.zfs.get_dataset(name)
            dataset.mount()
        self._datasets[name] = dataset

        return dataset
