import collections.abc
import os

from iocage_lib.ioc_json import IOCZFS


class Resource:
    # TODO: Let's also rethink how best we should handle this in the future
    def __init__(self, name):
        self.zfs = IOCZFS()
        self.name = name.rsplit('/', 1)[-1]

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

    @property
    def path(self):
        raise NotImplementedError

    @property
    def exists(self):
        return os.path.exists(self.path or '')


class ListableResource(collections.abc.Iterable):

    resource = NotImplemented
    path = NotImplemented

    def __init__(self):
        self.zfs = IOCZFS()
        self.dataset_path = os.path.join(
            self.zfs.iocroot_dataset, self.path
        ) if self.zfs.iocroot_path else ''

    def __iter__(self):
        if self.dataset_path:
            for release in self.zfs.zfs_get_dataset_and_dependents(
                self.dataset_path, depth=1
            ):
                yield self.resource(release)
