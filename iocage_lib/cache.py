import os
import subprocess as su
import threading

from iocage_lib.zfs import (
    all_properties, dataset_exists, get_all_dependents, get_dependents_with_depth,
)


class Cache:

    cache_lock = threading.Lock()

    def __init__(self):
        self.fields = [
            'dataset_data', 'pool_data', 'dataset_dep_data', 'ioc_pool', 'ioc_dataset',
            '_freebsd_version',
        ]
        self.reset()

    @property
    def freebsd_version(self):
        if not self._freebsd_version:
            self._freebsd_version = su.run(
                ['freebsd-version'], stdout=su.PIPE, stderr=su.STDOUT
            ).stdout.decode().rstrip().split('-', 1)[0]
        return self._freebsd_version

    @property
    def iocage_activated_pool(self):
        return self.iocage_activated_pool_internal()

    def iocage_activated_pool_internal(self, lock=True):
        if lock:
            self.cache_lock.acquire()
        try:
            pools = self.pools_internal(lock=False)
            self.dataset_data = self.dataset_data or {}
            if not self.ioc_pool:
                if not all(self.dataset_data.get(p) for p in pools):
                    self.dataset_data.update(
                        all_properties([p for p in pools], types=['filesystem'])
                    )
                for p in filter(
                    lambda p: self.dataset_data.get(p, {}).get('org.freebsd.ioc:active') == 'yes',
                    pools
                ):
                    self.ioc_pool = p
            return self.ioc_pool
        finally:
            if lock:
                self.cache_lock.release()

    @property
    def iocage_activated_dataset(self):
        with self.cache_lock:
            ioc_pool = self.iocage_activated_pool_internal(lock=False)
            if ioc_pool:
                dependents = self.dependents_internal(ioc_pool, 1, lock=False)
                ioc_ds = os.path.join(ioc_pool, 'iocage')
            if not self.ioc_dataset and ioc_pool and ioc_ds in dependents:
                self.ioc_dataset = ioc_ds
            return self.ioc_dataset

    @property
    def datasets(self):
        with self.cache_lock:
            ioc_pool = self.iocage_activated_pool_internal(lock=False)
            if not self.dataset_data or set(self.dataset_data) == set(self.pool_data):
                ds = ''
                if ioc_pool:
                    ds = os.path.join(ioc_pool, 'iocage')
                self.dataset_data.update(all_properties(
                    [ds] if ds and dataset_exists(ds) else [], recursive=True, types=['filesystem']
                ))
            return self.dataset_data

    def dependents(self, dataset, depth=None):
        return self.dependents_internal(dataset, depth)

    def dependents_internal(self, dataset, depth=None, lock=True):
        if lock:
            self.cache_lock.acquire()
        try:
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
        finally:
            if lock:
                self.cache_lock.release()

    def update_dataset_data(self, dataset, props):
        with self.cache_lock:
            self.dataset_data = self.dataset_data or {}
            self.dataset_data[dataset] = props

    @property
    def pools(self):
        return self.pools_internal()

    def pools_internal(self, lock=True):
        if lock:
            self.cache_lock.acquire()
        try:
            if not self.pool_data:
                self.pool_data = all_properties(resource_type='zpool')
            return self.pool_data
        finally:
            if lock:
                self.cache_lock.release()

    def reset(self):
        with self.cache_lock:
            for f in self.fields:
                setattr(self, f, None)


cache = Cache()
