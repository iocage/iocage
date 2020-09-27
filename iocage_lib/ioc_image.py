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
"""iocage export and import module"""
import datetime
import re
import hashlib
import os
import subprocess as su
import tarfile
import zipfile

import iocage_lib.ioc_common
import iocage_lib.ioc_json

from iocage_lib.cache import cache


class IOCImage(object):
    """export() and import()"""

    def __init__(self, callback=None, silent=False):
        self.pool = iocage_lib.ioc_json.IOCJson().json_get_value("pool")
        self.iocroot = iocage_lib.ioc_json.IOCJson(
            self.pool).json_get_value("iocroot")
        self.date = datetime.datetime.utcnow().strftime("%F")
        self.callback = callback
        self.silent = silent

    def export_jail(self, uuid, path, compression_algo='zip'):
        """Make a recursive snapshot of the jail and export to a file."""
        images = f"{self.iocroot}/images"
        name = f"{uuid}_{self.date}"
        image = f"{images}/{name}"
        export_type, jail_name = path.rsplit('/', 2)[-2:]
        image_path = f"{self.pool}/iocage/{export_type}/{jail_name}"
        jail_list = []
        extension = 'zip' if compression_algo == 'zip' else 'tar.xz'

        # Looks like foo/iocage/jails/df0ef69a-57b6-4480-b1f8-88f7b6febbdf@BAR
        target = f"{image_path}@ioc-export-{self.date}"

        try:
            iocage_lib.ioc_common.checkoutput(
                ["zfs", "snapshot", "-r", target], stderr=su.STDOUT)
        except su.CalledProcessError as err:
            msg = err.output.decode('utf-8').rstrip()
            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": msg
                },
                _callback=self.callback,
                silent=self.silent)

        datasets = su.Popen(
            ["zfs", "list", "-H", "-r", "-o", "name", image_path],
            stdout=su.PIPE,
            stderr=su.PIPE).communicate()[0].decode("utf-8").split()

        for dataset in datasets:
            if dataset.split("/")[-1] == jail_name:
                _image = image
                jail_list.append(_image)
            else:
                image_name = dataset.partition(f"{image_path}")[2]
                name = image_name.replace("/", "_")
                _image = image + name
                jail_list.append(_image)
                target = f"{dataset}@ioc-export-{self.date}"

            # Sending each individually as sending them recursively to a file
            # does not work how one expects.
            try:
                with open(_image, "wb") as export:
                    msg = f"Exporting dataset: {dataset}"
                    iocage_lib.ioc_common.logit(
                        {
                            "level": "INFO",
                            "message": msg
                        },
                        self.callback,
                        silent=self.silent)

                    su.check_call(["zfs", "send", target], stdout=export)
            except su.CalledProcessError as err:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": err
                    },
                    _callback=self.callback,
                    silent=self.silent)

        iocage_lib.ioc_common.logit(
            {
                'level': 'INFO',
                'message': '\nPreparing compressed '
                f'file: {image}.{extension}.'
            },
            self.callback,
            silent=self.silent)

        final_image_path = os.path.join(images, f'{image}.{extension}')
        if compression_algo == 'zip':
            with zipfile.ZipFile(
                final_image_path, 'w',
                compression=zipfile.ZIP_DEFLATED, allowZip64=True
            ) as final:
                for jail in jail_list:
                    final.write(jail)
        else:
            with tarfile.open(final_image_path, mode='w:xz') as f:
                for jail in jail_list:
                    f.add(jail)

        with open(final_image_path, 'rb') as import_image:
            digest = hashlib.sha256()
            chunk_size = 10 * 1024 * 1024

            while True:
                chunk = import_image.read(chunk_size)

                if chunk == b'':
                    break

                digest.update(chunk)

            image_checksum = digest.hexdigest()

        with open(os.path.join(images, f'{image}.sha256'), 'w') as checksum:
            checksum.write(image_checksum)

        # Cleanup our mess.
        try:
            target = f"{self.pool}/iocage/jails/{uuid}@ioc-export-{self.date}"
            iocage_lib.ioc_common.checkoutput(
                ["zfs", "destroy", "-r", target], stderr=su.STDOUT)

            for jail in jail_list:
                os.remove(jail)

        except su.CalledProcessError as err:
            msg = err.output.decode('utf-8').rstrip()
            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": msg
                },
                _callback=self.callback,
                silent=self.silent)

        msg = f"\nExported: {image}.{extension}"
        iocage_lib.ioc_common.logit(
            {
                "level": "INFO",
                "message": msg
            },
            self.callback,
            silent=self.silent)

    def import_jail(self, jail, compression_algo=None, path=None):
        """Import from an iocage export."""
        # Path can be an absolute path pointing straight to the exported jail
        # or it can the directory where the exported jail lives
        # TODO: We should introduce parsers for this
        image_dir = path or os.path.join(self.iocroot, 'images')
        if not os.path.exists(image_dir):
            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': f'{image_dir} does not exist.'
                }
            )
        elif os.path.isfile(image_dir):
            image_dir, filename = image_dir.rsplit('/', 1)
        else:
            if not compression_algo:
                extension_regex = r'zip|tar\.xz'
            else:
                extension_regex = r'zip' if \
                    compression_algo == 'zip' else r'tar.xz'
            regex = re.compile(rf'{jail}.*(?:{extension_regex})')
            matches = [
                f for f in os.listdir(image_dir) if regex.match(f)
            ]

            if len(matches) > 1:
                msg = f"Multiple images found for {jail}:"

                for j in sorted(matches):
                    msg += f"\n  {j}"

                msg += '\nPlease explicitly select image or define ' \
                       'compression algorithm to use'

                iocage_lib.ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": msg
                    },
                    _callback=self.callback,
                    silent=self.silent)
            elif len(matches) < 1:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": f"{jail} not found!"
                    },
                    _callback=self.callback,
                    silent=self.silent)
            else:
                filename = matches[0]

        if filename.rsplit('.', 1)[-1] == 'zip':
            compression_algo = extension = 'zip'
        else:
            compression_algo = 'lzma'
            extension = 'tar.xz'

        image_target = f"{image_dir}/{filename}"
        uuid, date = filename[:-len(f'.{extension}')].rsplit('_', 1)

        if compression_algo == 'zip':
            reader = {
                'func': zipfile.ZipFile, 'params': ['r'], 'iter': 'namelist'
            }
        else:
            reader = {
                'func': tarfile.open, 'params': ['r:xz'], 'iter': 'getmembers'
            }

        with reader['func'](image_target, *reader['params']) as f:
            for member in getattr(f, reader['iter'])():
                if compression_algo != 'zip':
                    name = member.name
                else:
                    name = member

                z_dataset_type = name.split(f'{date}_', 1)[-1]
                z_dataset_type = z_dataset_type.split(f'{uuid}_', 1)[-1]
                if z_dataset_type == date:
                    # This is the parent dataset
                    z_dataset_type = uuid
                else:
                    z_dataset_type = \
                        f'{uuid}/{z_dataset_type.replace("_", "/")}'.rstrip(
                            '/'
                        )

                iocage_lib.ioc_common.logit(
                    {
                        'level': 'INFO',
                        'message': f'Importing dataset: {z_dataset_type}'
                    },
                    self.callback,
                    silent=self.silent
                )

                recv = su.Popen(
                    [
                        'zfs', 'recv', '-F', os.path.join(
                            self.pool, 'iocage/jails', z_dataset_type
                        )
                    ], stdin=su.PIPE
                )

                chunk_size = 10 * 1024 * 1024

                with (f.open(name) if compression_algo == 'zip' else f.extractfile(member)) as file:
                    data = file.read(chunk_size)
                    while data is not None and len(data) > 0:
                        recv.stdin.write(data)
                        data = file.read(chunk_size)

                recv.communicate()

        # Cleanup our mess.
        try:
            target = f"{self.pool}/iocage/jails/{uuid}@ioc-export-{date}"

            iocage_lib.ioc_common.checkoutput(
                ["zfs", "destroy", "-r", target], stderr=su.STDOUT)
        except su.CalledProcessError as err:
            msg = err.output.decode('utf-8').rstrip()
            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": msg
                },
                _callback=self.callback,
                silent=self.silent)

        # Templates become jails again once imported, let's make that reality.
        cache.reset()
        jail_json = iocage_lib.ioc_json.IOCJson(
            f'{self.iocroot}/jails/{uuid}', silent=True
        )
        if jail_json.json_get_value('type') == 'template':
            jail_json.json_set_value('type=jail')
            jail_json.json_set_value('template=0', _import=True)

        msg = f"\nImported: {uuid}"
        iocage_lib.ioc_common.logit(
            {
                "level": "INFO",
                "message": msg
            },
            self.callback,
            silent=self.silent)
