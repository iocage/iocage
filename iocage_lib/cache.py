import os

from iocage_lib.zfs import (
    all_properties, dataset_exists, get_all_dependents, get_dependents_with_depth,
)

import threading


class Cache:

    cache_lock = threading.Lock()

    def __init__(self):
        self.fields = ['dataset_data', 'pool_data', 'dataset_dep_data', 'ioc_pool', 'ioc_dataset']
        self.reset()

    @property
    def iocage_activated_pool(self):
        with self.cache_lock:
            self.dataset_data = self.dataset_data or {}
            if not self.ioc_pool:
                if not all(self.dataset_data.get(p) for p in self.pools):
                    self.dataset_data.update(
                        all_properties([p for p in self.pools], types=['filesystem'])
                    )
                for p in filter(
                    lambda p: self.dataset_data.get(p, {}).get('org.freebsd.ioc:active') == 'yes',
                    self.pools
                ):
                    self.ioc_pool = p
            return self.ioc_pool

    @property
    def iocage_activated_dataset(self):
        with self.cache_lock:
            if not self.ioc_dataset:
                ioc_pool = self.iocage_activated_pool
                if ioc_pool and os.path.join(ioc_pool, 'iocage') in self.dependents(ioc_pool, 1):
                    self.ioc_dataset = os.path.join(ioc_pool, 'iocage')
            return self.ioc_dataset

    @property
    def datasets(self):
        with self.cache_lock:
            if not self.dataset_data:
                ds = ''
                ioc_pool = self.iocage_activated_pool
                if ioc_pool:
                    ds = os.path.join(ioc_pool, 'iocage')
                self.dataset_data.update(all_properties(
                    [ds if ds and dataset_exists(ds) else ''], recursive=True, types=['filesystem']
                ))
            return self.dataset_data

    def dependents(self, dataset, depth=None):
        with self.cache_lock:
            if not self.dataset_dep_data:
                self.dataset_dep_data = {}
                for ds in get_all_dependents():
                    self.dataset_dep_data[ds] = []
                    for k in self.dataset_dep_data:
                        if ds.startswith(k):
                            self.dataset_dep_data[k].append(ds)

            return get_dependents_with_depth(
                dataset, self.dataset_dep_data.get(dataset, []), depth
            )

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
            for f in self.fields:
                setattr(self, f, None)


cache = Cache()
