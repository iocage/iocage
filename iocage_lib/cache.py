import os

from iocage_lib.zfs import (
    all_properties, dataset_exists, iocage_activated_pool
)

import threading


class Cache:

    cache_lock = threading.Lock()

    def __init__(self):
        self.dataset_data = self.pool_data = None

    @property
    def datasets(self):
        with self.cache_lock:
            if not self.dataset_data:
                ds = ''
                ioc_pool = iocage_activated_pool()
                if ioc_pool:
                    ds = os.path.join(ioc_pool, 'iocage')
                self.dataset_data = all_properties(
                    ds if ds and dataset_exists(ds) else '', recursive=True, types=['filesystem']
                )
                if not self.dataset_data[ioc_pool]:
                    self.dataset_data.update(all_properties(ioc_pool, types=['filesystem']))
            return self.dataset_data

    def update_dataset_data(self, dataset, props):
        with self.cache_lock:
            self.dataset_data[dataset] = props

    @property
    def pools(self):
        with self.cache_lock:
            if not self.pool_data:
                self.pool_data = all_properties(resource_type='zpool')
            return self.pool_data

    def reset(self):
        with self.cache_lock:
            self.dataset_data = self.pool_data = None


cache = Cache()
