from iocage_lib.resource import Resource
from iocage_lib.zfs import ZFSException, create_dataset

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
