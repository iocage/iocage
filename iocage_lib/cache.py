from iocage_lib.zfs import all_properties


class Cache:
    def __init__(self):
        self.dataset_data = self.pool_data = None

    @property
    def datasets(self):
        if not self.dataset_data:
            self.dataset_data = all_properties()
        return self.dataset_data

    @property
    def pools(self):
        if not self.pool_data:
            self.pool_data = all_properties(resource_type='zpool')
        return self.pool_data

    def reset(self):
        self.dataset_data = self.pool_data = None


cache = Cache()
