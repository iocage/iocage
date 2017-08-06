import Distribution
import Datasets
import helpers

import os
import platform


class Host:

    def __init__(self, root_dataset=None, zfs=None, logger=None):

        helpers.init_logger(self, logger)
        helpers.init_zfs(self, zfs)
        self.datasets = Datasets.Datasets(
            root=root_dataset,
            logger=self.logger,
            zfs=self.zfs
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
    def release_minor_version(self):
        release_version_string = os.uname()[2]
        release_version_fragments = release_version_string.split("-")

        if len(release_version_fragments) < 3:
            return 0

        return int(release_version_fragments[2])

    @property
    def release_version(self):
        release_version_string = os.uname()[2]
        release_version_fragments = release_version_string.split("-")

        if len(release_version_fragments) > 1:
            return "-".join(release_version_fragments[0:2])

    @property
    def processor(self):
        return platform.processor()
