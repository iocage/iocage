"""Destroy all of a dataset type."""

import iocage.lib.ioc_common
import iocage.lib.ioc_destroy
import iocage.lib.ioc_json


class IOCClean(object):
    """Cleans datasets and snapshots of a given type."""

    def __init__(self, callback=None, silent=False):
        self.pool = iocage.lib.ioc_json.IOCJson().json_get_value("pool")
        self.callback = callback
        self.silent = silent

    def clean_jails(self):
        """Cleans all jails and their respective snapshots."""
        iocage.lib.ioc_common.logit({
            "level"  : "INFO",
            "message": "Cleaning iocage/jails"
        },
            _callback=self.callback,
            silent=self.silent)

        iocage.lib.ioc_destroy.IOCDestroy().destroy_jail(
            f"{self.pool}/iocage/jails",
            clean=True)

    def clean_all(self):
        """Cleans everything related to iocage."""
        datasets = ("iocage", "iocage/download", "iocage/images",
                    "iocage/jails", "iocage/log", "iocage/releases",
                    "iocage/templates")

        for dataset in reversed(datasets):
            iocage.lib.ioc_common.logit({
                "level"  : "INFO",
                "message": f"Cleaning {dataset}"
            },
                _callback=self.callback,
                silent=self.silent)

            iocage.lib.ioc_destroy.IOCDestroy().__destroy_parse_datasets__(
                f"{self.pool}/{dataset}", clean=True)

    def clean_templates(self):
        """Cleans all templates and their respective children."""
        iocage.lib.ioc_common.logit({
            "level"  : "INFO",
            "message": "Cleaning iocage/templates"
        },
            _callback=self.callback,
            silent=self.silent)

        iocage.lib.ioc_destroy.IOCDestroy().__destroy_parse_datasets__(
            f"{self.pool}/iocage/templates",
            clean=True)
