from iocage_lib.resource import Resource
from iocage_lib.zfs import ZFSException

import os


class Dataset(Resource):

    zfs_resource = 'zfs'

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
