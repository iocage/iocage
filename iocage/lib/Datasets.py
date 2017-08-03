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
        prop = self.ZFS_POOL_ACTIVE_PROPERTY
        for pool in self.zfs.pools:
            try:
                if pool.root_dataset.properties[prop].value == "yes":
                    return pool
            except:
                pass
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
            self.logger.warn(msg)
            #raise Exception(msg)

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
        iocage_dataset_name = f"{zfs_pool.name}/iocage"

        try:
            dataset = self.zfs.get_dataset(iocage_dataset_name)
        except:
            self.logger.verbose(f"Creating iocage root dataset {iocage_dataset_name}")
            zfs_pool.create(iocage_dataset_name, {
                "mountpoint": "/iocage"
            }, create_ancestors=True)
            dataset = self.get_dataset(iocage_dataset_name)
            dataset.mount()

        self.root = dataset

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
