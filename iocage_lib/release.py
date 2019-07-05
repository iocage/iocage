import os

from iocage_lib.resource import Resource


class Release(Resource):

    @property
    def path(self):
        return os.path.join(
            self.zfs.iocroot_path, 'releases', self.name
        ) if self.zfs.iocroot_path else None
