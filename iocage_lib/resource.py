import collections.abc

from iocage_lib.cache import cache as iocage_cache
from iocage_lib.zfs import (
    properties, get_dependents, set_property,
    iocage_activated_dataset, inherit_property
)


class Resource:
    # TODO: Let's also rethink how best we should handle this in the future
    zfs_resource = NotImplementedError

    def __init__(self, name, cache=True):
        self.resource_name = self.name = name
        self._properties = None
        self.cache = cache

    @property
    def properties(self):
        if not self._properties:
            if self.cache:
                self._properties = iocage_cache.datasets[self.resource_name]
            if not self._properties:
                # For cases where we are using this for datasets which are not under
                # ioc pool, we don't cache that data and it has to be retrieved in
                # this case
                self._properties = properties(self.resource_name, self.zfs_resource)
                iocage_cache.update_dataset_data(self.resource_name, self._properties)
        return self._properties

    def set_property(self, prop, value):
        iocage_cache.reset()
        set_property(self.resource_name, prop, value, self.zfs_resource)

    def inherit_property(self, prop):
        iocage_cache.reset()
        inherit_property(self.resource_name, prop)

    def __bool__(self):
        return self.exists

    def __hash__(self):
        return hash(self.resource_name)

    def __repr__(self):
        return str(self.resource_name)

    def __str__(self):
        return str(self.resource_name)

    def iocage_path(self):
        if self.cache:
            return iocage_cache.iocage_activated_dataset or ''
        else:
            return iocage_activated_dataset() or ''

    @property
    def path(self):
        raise NotImplementedError

    @property
    def exists(self):
        raise NotImplementedError


class ListableResource(collections.abc.Iterable):

    resource = NotImplemented

    def __init__(self, cache=True):
        super().__init__()
        self.cache = cache


class ZFSListableResource(ListableResource):

    def __init__(self, path):
        self.dataset_path = path

    def __iter__(self):
        if self.dataset_path:
            for release in get_dependents(self.dataset_path, depth=1):
                yield self.resource(release)


class IocageListableResource(ZFSListableResource):

    resource = NotImplemented
    path = NotImplemented

    def __init__(self):
        super().__init__(iocage_activated_dataset())

    def __iter__(self):
        if self.dataset_path:
            for release in get_dependents(self.dataset_path, depth=1):
                yield self.resource(release)
