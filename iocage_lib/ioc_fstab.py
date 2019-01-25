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
"""Manipulate a jails fstab"""
import datetime
import os
import shutil
import subprocess as su
import tempfile
import pathlib

import iocage_lib.ioc_common
import iocage_lib.ioc_json
import iocage_lib.ioc_list
import iocage_lib.ioc_exceptions
import texttable


class IOCFstab(object):

    """Will add or remove an entry, and mount or umount the filesystem."""

    def __init__(self, uuid, action, source, destination, fstype, fsoptions,
                 fsdump, fspass, index=None, silent=False, callback=None,
                 header=False, _fstab_list=None):
        self.pool = iocage_lib.ioc_json.IOCJson().json_get_value("pool")
        self.iocroot = iocage_lib.ioc_json.IOCJson(
            self.pool).json_get_value("iocroot")
        self.uuid = uuid
        self.action = action
        self.src = source
        self.dest = destination
        self.fstype = fstype
        self.fsoptions = fsoptions
        self.fsdump = fsdump
        self.fspass = fspass
        self.index = int(index) if index is not None else None
        self.mount = f"{self.src}\t{self.dest}\t{self.fstype}\t" \
            f"{self.fsoptions}\t{self.fsdump}\t{self.fspass}"
        self._fstab_list = _fstab_list
        self.header = header
        self.silent = silent
        self.callback = callback

        if action != 'list':
            self.fstab = list(self.__read_fstab__())

            if action != 'edit':
                self.dests = self.__validate_fstab__(self.fstab, 'all')

            self.__fstab_parse__()

    def __fstab_parse__(self):
        """
        Checks which action the user is asking for and calls the
        appropriate methods.
        """
        actions = ['add', 'remove', 'edit', 'replace']

        if self.action not in actions:
            raise RuntimeError("Type of operation not specified!")

        if self.action == "add":
            self.__validate_fstab__([self.mount])
            self.__fstab_add__()

            try:
                self.__fstab_mount__()
            except RuntimeError:
                iocage_lib.ioc_common.logit({
                    'level': 'WARNING',
                    'message': 'Mounting entry failed, check \'mount\''
                },
                    _callback=self.callback,
                    silent=self.silent
                )
        elif self.action == "remove":
            dest = self.__fstab_remove__()

            try:
                self.__fstab_umount__(dest)
            except RuntimeError:
                iocage_lib.ioc_common.logit({
                    'level': 'WARNING',
                    'message': 'Unmounting entry failed, check \'mount\''
                },
                    _callback=self.callback,
                    silent=self.silent
                )
        elif self.action == "edit":
            self.__fstab_edit__()
        elif self.action == "replace":
            self.__validate_fstab__([self.mount])
            self.__fstab_edit__(_string=True)
            self.__fstab_mount__()

    def __read_fstab__(self):
        with open(f"{self.iocroot}/jails/{self.uuid}/fstab", "r") as f:
            for line in f:
                yield line.rstrip()

    def __validate_fstab__(self, fstab, mode='single'):
        dests = {}
        verrors = []
        jail_root = f'{self.iocroot}/jails/{self.uuid}/root'

        for index, line in enumerate(fstab):
            try:
                source, destination, fstype, options, \
                    dump, _pass = line.split()[0:6]
            except ValueError:
                verrors.append(
                    f'Malformed fstab at line {index}: {repr(line)}'
                )
                continue

            source = pathlib.Path(source)
            missing_root = False
            dest = pathlib.Path(destination)

            if mode != 'all' and (
                self.action == 'add' or self.action == 'replace'
            ):
                if destination in self.dests.values():
                    if str(source) in self.dests.keys():
                        verrors.append(
                            f'Destination: {self.dest} already exists!'
                        )
                        break
                    else:
                        # They replace with the same destination
                        try:
                            self.__fstab_umount__(destination)
                        except RuntimeError:
                            # It's not mounted
                            pass

                if jail_root not in self.dest:
                    verrors.append(
                        f'Destination: {self.dest} must include '
                        f'jail\'s mountpoint! ({jail_root})'
                    )
                    break
            else:
                if jail_root not in destination:
                    verrors.append(
                        f'Destination: {destination} does not include '
                        f'jail\'s mountpoint! ({jail_root})'
                    )
                    missing_root = True

            if not source.is_dir():
                if fstype == 'nullfs':
                    verrors.append(f'Source: {source} does not exist!')
            if not source.is_absolute():
                if fstype == 'nullfs':
                    verrors.append(
                        f'Source: {source} must use an absolute path!'
                    )

            if not missing_root:
                if not dest.is_absolute():
                    verrors.append(
                        f'Destination: {dest} must use an absolute path!'
                    )

            if not dump.isdecimal():
                verrors.append(
                    f'Dump: {dump} must be a digit!'
                )
            if len(dump) > 1:
                verrors.append(
                    f'Dump: {dump} must be one digit long!'
                )
            if not _pass.isdecimal():
                verrors.append(
                    f'Pass: {_pass} must be a digit!'
                )
            if len(_pass) > 1:
                verrors.append(
                    f'Pass: {_pass} must be one digit long!'
                )
            dests[str(source)] = destination

        if verrors:
            iocage_lib.ioc_common.logit({
                'level': 'EXCEPTION',
                'message': verrors
            },
                _callback=self.callback,
                exception=iocage_lib.ioc_exceptions.ValidationFailed
            )

        return dests

    def __fstab_add__(self):
        """Adds a users mount to the jails fstab"""
        with iocage_lib.ioc_common.open_atomic(
                f'{self.iocroot}/jails/{self.uuid}/fstab',
                'w'
        ) as fstab:
            for line in self.fstab:
                fstab.write(f'{line}\n')

            date = datetime.datetime.utcnow().strftime("%F %T")
            fstab.write(f"{self.mount} # Added by iocage on {date}\n")

        iocage_lib.ioc_common.logit({
            "level": "INFO",
            "message": f"Successfully added mount to {self.uuid}'s fstab"
        },
            _callback=self.callback,
            silent=self.silent)

    def __fstab_remove__(self):
        """
        Removes the users mount by index or matching string.

        :return: The destination of the specified mount
        """
        removed = False

        with iocage_lib.ioc_common.open_atomic(
                f'{self.iocroot}/jails/{self.uuid}/fstab', 'w'
        ) as fstab:
            for index, line in enumerate(self.fstab):
                if line.rsplit("#")[0].rstrip() == self.mount or index \
                        == self.index:
                    removed = True
                    dest = line.split()[1]

                    continue

                fstab.write(f'{line}\n')

        if not removed:
            iocage_lib.ioc_common.logit({
                'level': 'EXCEPTION',
                'message': 'No matching fstab entry.'
            },
                _callback=self.callback,
                exception=iocage_lib.ioc_exceptions.ValueNotFound,
                silent=self.silent)

        iocage_lib.ioc_common.logit({
            'level': 'INFO',
            'message': f'Successfully removed mount from {self.uuid}\'s fstab'
        },
            _callback=self.callback,
            silent=self.silent)

        return dest  # Needed for umounting, otherwise we lack context.

    def __fstab_mount__(self):
        """Mounts the users mount if the jail is running."""
        status, _ = iocage_lib.ioc_list.IOCList().list_get_jid(self.uuid)

        if not status:
            return

        os.makedirs(self.dest, exist_ok=True)
        proc = su.Popen(["mount", "-t", self.fstype, "-o", self.fsoptions,
                         self.src, self.dest], stdout=su.PIPE, stderr=su.PIPE)

        stdout_data, stderr_data = proc.communicate()

        if stderr_data:
            raise RuntimeError(f"{stderr_data.decode('utf-8')}")

    def __fstab_umount__(self, dest):
        """
        Umounts the users mount if the jail is running.

        :param dest: The destination to umount.
        """
        status, _ = iocage_lib.ioc_list.IOCList().list_get_jid(self.uuid)

        if not status:
            return

        proc = su.Popen(["umount", "-f", dest], stdout=su.PIPE, stderr=su.PIPE)
        stdout_data, stderr_data = proc.communicate()

        if stderr_data:
            raise RuntimeError(f"{stderr_data.decode('utf-8')}")

    def __fstab_edit__(self, _string=False):
        """
        Opens up the users EDITOR, or vi and replaces the jail's fstab
        with the new content.

        If _string is True, then we replace the given index with the new mount
        """
        jail_fstab = f"{self.iocroot}/jails/{self.uuid}/fstab"

        if _string:
            matched = False
            with iocage_lib.ioc_common.open_atomic(
                    jail_fstab, "w") as fstab:

                for i, line in enumerate(self.fstab):
                    if i == self.index:
                        date = datetime.datetime.utcnow().strftime("%F %T")
                        fstab.write(
                            f"{self.mount} # Added by iocage on {date}\n")
                        matched = True

                        iocage_lib.ioc_common.logit({
                            "level": "INFO",
                            "message": f"Index {self.index} replaced."
                        },
                            _callback=self.callback,
                            silent=self.silent)
                    else:
                        fstab.write(line)

            if not matched:
                iocage_lib.ioc_common.logit({
                    "level": "EXCEPTION",
                    "message": f"Index {self.index} not found."
                },
                    _callback=self.callback,
                    silent=self.silent)

            return

        editor = os.environ.get("EDITOR", "/usr/bin/vi")
        err_editor = editor.split("/")[-1]
        tmp_fstab = tempfile.NamedTemporaryFile(suffix=".iocage")

        shutil.copy2(jail_fstab, tmp_fstab.name)
        proc = su.call([editor, tmp_fstab.name])

        if proc != 0:
            raise RuntimeError(f"An error occurred within {err_editor}!")

        with open(jail_fstab, "w") as fstab:
            for line in tmp_fstab.readlines():
                fstab.write(line.decode("utf-8"))

    def fstab_list(self):
        """Returns list of lists, or a table"""

        if not self.header:
            flat_fstab = [f for f in self._fstab_list]

            return flat_fstab

        table = texttable.Texttable(max_width=0)

        # We get an infinite float otherwise.
        table.set_cols_dtype(["t", "t"])
        self._fstab_list.insert(0, ["INDEX", "FSTAB ENTRY"])

        table.add_rows(self._fstab_list)

        return table.draw()
