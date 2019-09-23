import collections.abc
import os


from iocage_lib.zfs import (
    ZFSException, dataset_properties, get_dependents, set_dataset_property,
    iocage_activated_dataset
)


class Resource:
    # TODO: Let's also rethink how best we should handle this in the future
    def __init__(self, name):
        self.name = name

    def __bool__(self):
        return self.exists

    def __hash__(self):
        return hash(self.path)

    def __repr__(self):
        return str(self.name)

    def __str__(self):
        return str(self.name)

    def __eq__(self, other):
        return other.path == self.path

    def iocage_path(self):
        return iocage_activated_dataset() or ''

    @property
    def path(self):
        raise NotImplementedError

    @property
    def exists(self):
        return os.path.exists(self.path or '')


class ZFSResource(Resource):
    @property
    def path(self):
        try:
            return self.properties['mountpoint']
        except ZFSException:
            # Unable to find zfs resource
            return False

    @property
    def properties(self):
        return dataset_properties(self.name)

    def set_property(self, prop, value):
        set_dataset_property(self.name, prop, value)


class ListableResource(collections.abc.Iterable):

    resource = NotImplemented


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
