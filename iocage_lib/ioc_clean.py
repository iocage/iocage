# Copyright (c) 2014-2019, iocage
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

import iocage_lib.ioc_common
import iocage_lib.ioc_destroy
import iocage_lib.ioc_json
import shutil

from iocage_lib.dataset import Dataset


class IOCClean:
    """Cleans datasets and snapshots of a given type."""

    def __init__(self, callback=None, silent=False):
        self.pool = iocage_lib.ioc_json.IOCJson().json_get_value('pool')
        self.iocroot = iocage_lib.ioc_json.IOCJson(self.pool).json_get_value(
            'iocroot')

        self.callback = callback
        self.silent = silent

    def clean_jails(self):
        """Cleans all jails and their respective snapshots."""
        iocage_lib.ioc_common.logit({
            'level': 'INFO',
            'message': 'Cleaning iocage/jails'
        },
            _callback=self.callback,
            silent=self.silent)

        iocage_lib.ioc_destroy.IOCDestroy().destroy_jail(
            f'{self.pool}/iocage/jails',
            clean=True
        )

    def clean_releases(self):
        """Cleans all releases and the jails created from them."""
        iocage_lib.ioc_common.logit({
            'level': 'INFO',
            'message': 'Cleaning iocage/download'
        },
            _callback=self.callback,
            silent=self.silent)

        iocage_lib.ioc_destroy.IOCDestroy().destroy_jail(
            f'{self.pool}/iocage/download',
            clean=True
        )

        iocage_lib.ioc_common.logit({
            'level': 'INFO',
            'message': 'Cleaning iocage/releases'
        },
            _callback=self.callback,
            silent=self.silent)

        iocage_lib.ioc_destroy.IOCDestroy().destroy_jail(
            f'{self.pool}/iocage/releases',
            clean=True)

    def clean_all(self):
        """Cleans everything related to iocage."""
        datasets = ('iocage', 'iocage/download', 'iocage/images',
                    'iocage/log', 'iocage/releases', 'iocage/jails',
                    'iocage/templates')

        for dataset in reversed(datasets):
            iocage_lib.ioc_common.logit({
                'level': 'INFO',
                'message': f'Cleaning {dataset}'
            },
                _callback=self.callback,
                silent=self.silent)

            iocage_lib.ioc_destroy.IOCDestroy().__destroy_parse_datasets__(
                f'{self.pool}/{dataset}', clean=True)

    def clean_templates(self):
        """Cleans all templates and their respective children."""
        iocage_lib.ioc_common.logit({
            "level": "INFO",
            "message": "Cleaning iocage/templates"
        },
            _callback=self.callback,
            silent=self.silent)

        iocage_lib.ioc_destroy.IOCDestroy().__destroy_parse_datasets__(
            f"{self.pool}/iocage/templates",
            clean=True)

    def clean_images(self):
        """Destroys the images dataset"""
        iocage_lib.ioc_common.logit({
            'level': 'INFO',
            'message': 'Cleaning iocage/images'
        },
            _callback=self.callback,
            silent=self.silent)

        Dataset(f'{self.pool}/iocage/images').destroy(True, True)

    def clean_debug(self):
        """Removes the debug directory"""
        iocage_lib.ioc_common.logit({
            'level': 'INFO',
            'message': 'Cleaning iocage/debug'
        },
            _callback=self.callback,
            silent=self.silent)

        try:
            shutil.rmtree(f'{self.iocroot}/debug')
        except Exception:
            # Doesn't exist, we don't care
            pass
