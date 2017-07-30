import Distribution
import Datasets
import helpers

import os
import platform
import libzfs


class Host:

    def __init__(self, root_dataset=None, zfs=None, logger=None):

        helpers.init_logger(self, logger)
        helpers.init_zfs(self, zfs)
        self.datasets = Datasets.Datasets(
            root=root_dataset,
            logger=self.logger
        )
        self.distribution = Distribution.Distribution(
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
