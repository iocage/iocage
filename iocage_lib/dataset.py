from iocage_lib.resource import Resource
from iocage_lib.zfs import (
    ZFSException, create_dataset, get_dependents, destroy_zfs_resource,
    umount_dataset, mount_dataset
)

import os


class Dataset(Resource):

    zfs_resource = 'zfs'

    def create(self, data):
        return create_dataset({'name': self.name, **data})

    @property
    def path(self):
        try:
            return self.properties['mountpoint']
        except ZFSException:
            # Unable to find zfs resource
            return ''

    def __eq__(self, other):
        return other.path == self.path

    @property
    def exists(self):
        return os.path.exists(self.path)

    def get_dependents(self, depth=1):
        for d in get_dependents(self.name, depth):
            yield Dataset(d)

    def destroy(self, recursive=False, force=False):
        return destroy_zfs_resource(self.name, recursive, force)

    def mount(self):
        return mount_dataset(self.name)

    def umount(self):
        return umount_dataset(self.name)
