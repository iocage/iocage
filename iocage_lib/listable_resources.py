import collections.abc
import os

from iocage_lib.ioc_json import IOCZFS
from iocage_lib.release import Release


class ListableResource(collections.abc.Iterable):

    resource = NotImplemented
    path = NotImplemented

    def __init__(self):
        self.zfs = IOCZFS()
        self.dataset_path = os.path.join(
            self.zfs.iocroot_dataset, self.path
        ) if self.zfs.iocroot_dataset else ''

    def __iter__(self):
        if self.dataset_path:
            for release in self.zfs.zfs_get_dataset_and_dependents(
                self.dataset_path, depth=1
            ):
                yield self.resource(release)


class ListableReleases(ListableResource):

    resource = Release
    path = 'releases'
