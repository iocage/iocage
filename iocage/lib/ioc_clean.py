# Copyright (c) 2014-2017, iocage
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""Destroy all of a dataset type."""

import iocage.lib.ioc_common
import iocage.lib.ioc_destroy
import iocage.lib.ioc_json


class IOCClean(object):
    """Cleans datasets and snapshots of a given type."""

    def __init__(self, callback=None, silent=False, exit_on_error=False):
        self.pool = iocage.lib.ioc_json.IOCJson(
            exit_on_error=exit_on_error).json_get_value("pool")
        self.exit_on_error = exit_on_error
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

        iocage.lib.ioc_destroy.IOCDestroy(
            exit_on_error=self.exit_on_error).destroy_jail(
            f"{self.pool}/iocage/jails",
            clean=True)

    def clean_releases(self):
        """Cleans all releases and the jails created from them."""
        iocage.lib.ioc_common.logit({
            "level"  : "INFO",
            "message": "Cleaning iocage/download"
        },
            _callback=self.callback,
            silent=self.silent)

        iocage.lib.ioc_destroy.IOCDestroy(
            exit_on_error=self.exit_on_error
        ).destroy_jail(
            f"{self.pool}/iocage/download",
            clean=True)

        iocage.lib.ioc_common.logit({
            "level"  : "INFO",
            "message": "Cleaning iocage/releases"
        },
            _callback=self.callback,
            silent=self.silent)

        iocage.lib.ioc_destroy.IOCDestroy(
            exit_on_error=self.exit_on_error
        ).destroy_jail(
            f"{self.pool}/iocage/releases",
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

            iocage.lib.ioc_destroy.IOCDestroy(
                exit_on_error=self.exit_on_error
            ).__destroy_parse_datasets__(
                f"{self.pool}/{dataset}", clean=True)

    def clean_templates(self):
        """Cleans all templates and their respective children."""
        iocage.lib.ioc_common.logit({
            "level"  : "INFO",
            "message": "Cleaning iocage/templates"
        },
            _callback=self.callback,
            silent=self.silent)

        iocage.lib.ioc_destroy.IOCDestroy(
            exit_on_error=self.exit_on_error
        ).__destroy_parse_datasets__(
            f"{self.pool}/iocage/templates",
            clean=True)
