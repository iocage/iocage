import iocage.lib.Distribution
import iocage.lib.Datasets
import iocage.lib.helpers

import os
import platform
import libzfs


class Host:

    def __init__(self, root_dataset=None, zfs=None, logger=None):

        iocage.lib.helpers.init_logger(self, logger)
        iocage.lib.helpers.init_zfs(self, zfs)
        self.datasets = iocage.lib.Datasets.Datasets(
            root=root_dataset,
            logger=self.logger
        )
        self.distribution = iocage.lib.Distribution.Distribution(
            host=self,
            logger=self.logger
        )

        self.releases_dataset = None

    @property
    def userland_version(self):
        return float(self.release_version.partition("-")[0])

    @property
    def release_version(self):
        return os.uname()[2]

    @property
    def processor(self):
        return platform.processor()
