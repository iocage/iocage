from iocage_lib.zfs import all_properties

import fcntl


class Cache:

    lock_file = '/tmp/iocage_cache_lock'

    def __init__(self):
        self.dataset_data = self.pool_data = None

    @property
    def datasets(self):
        with open(self.lock_file, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            if not self.dataset_data:
                self.dataset_data = all_properties()
            return self.dataset_data

    @property
    def pools(self):
        with open(self.lock_file, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            if not self.pool_data:
                self.pool_data = all_properties(resource_type='zpool')
            return self.pool_data

    def reset(self):
        with open(self.lock_file, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            self.dataset_data = self.pool_data = None


cache = Cache()
