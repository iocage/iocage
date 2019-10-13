from iocage_lib.zfs import all_properties


class Cache:
    def __init__(self):
        self.dataset_data = None

    @property
    def datasets(self):
        if not self.dataset_data:
            self.dataset_data = all_properties()
        return self.dataset_data

    def reset(self):
        self.dataset_data = None


cache = Cache()
