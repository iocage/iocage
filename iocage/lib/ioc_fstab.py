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
"""Manipulate a jails fstab"""
import datetime
import os
import shutil
import subprocess as su
import tempfile

import texttable

import iocage.lib.ioc_common
import iocage.lib.ioc_json
import iocage.lib.ioc_list


class IOCFstab(object):
    """Will add or remove an entry, and mount or umount the filesystem."""

    def __init__(self, uuid, action, source, destination, fstype, fsoptions,
                 fsdump, fspass, index=None, silent=False, callback=None,
                 header=False, _fstab_list=None, exit_on_error=False):
        self.pool = iocage.lib.ioc_json.IOCJson(
            exit_on_error=exit_on_error).json_get_value("pool")
        self.iocroot = iocage.lib.ioc_json.IOCJson(
            self.pool, exit_on_error=exit_on_error).json_get_value("iocroot")
        self.uuid = uuid
        self.action = action
        self.src = source
        self.dest = destination
        self.fstype = fstype
        self.fsoptions = fsoptions
        self.fsdump = fsdump
        self.fspass = fspass
        self.index = index
        self.mount = f"{self.src}\t{self.dest}\t{self.fstype}\t" \
                     f"{self.fsoptions}\t{self.fsdump}\t{self.fspass}"
        self._fstab_list = _fstab_list
        self.header = header
        self.silent = silent
        self.callback = callback

        if action != "list":
            self.__fstab_parse__()

    def __fstab_parse__(self):
        """
        Checks which action the user is asking for and calls the
        appropriate methods.
        """
        if self.action == "add":
            self.__fstab_add__()
            self.__fstab_mount__()
        elif self.action == "remove":
            dest = self.__fstab_remove__()
            self.__fstab_umount__(dest)
        elif self.action == "edit":
            self.__fstab_edit__()
        else:
            raise RuntimeError("Type of operation not specified!")

    def __fstab_add__(self):
        """Adds a users mount to the jails fstab"""
        with open(f"{self.iocroot}/jails/{self.uuid}/fstab", "r") as fstab:
            with iocage.lib.ioc_common.open_atomic(
                    f"{self.iocroot}/jails/{self.uuid}/fstab",
                    "w") as _fstab:
                # open_atomic will empty the file, we need these still.
                for line in fstab.readlines():
                    _fstab.write(line)

                date = datetime.datetime.utcnow().strftime("%F %T")
                _fstab.write(f"{self.mount} # Added by iocage on {date}\n")

        iocage.lib.ioc_common.logit({
            "level"  : "INFO",
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
        index = 0

        with open(f"{self.iocroot}/jails/{self.uuid}/fstab", "r") as fstab:
            with iocage.lib.ioc_common.open_atomic(
                    f"{self.iocroot}/jails/{self.uuid}/fstab",
                    "w") as _fstab:
                for line in fstab.readlines():
                    if line.rsplit("#")[0].rstrip() == self.mount or index \
                            == self.index and not removed:
                        removed = True
                        dest = line.split()[1]
                        continue

                    _fstab.write(line)
                    index += 1
        if removed:
            iocage.lib.ioc_common.logit({
                "level"  : "INFO",
                "message": f"Successfully removed mount from {self.uuid}"
                           "'s fstab"
            },
                _callback=self.callback,
                silent=self.silent)
            return dest  # Needed for umounting, otherwise we lack context.

        iocage.lib.ioc_common.logit({
            "level"  : "INFO",
            "message": "No matching fstab entry."
        },
            _callback=self.callback,
            silent=self.silent)
        exit()

    def __fstab_mount__(self):
        """Mounts the users mount if the jail is running."""
        status, _ = iocage.lib.ioc_list.IOCList().list_get_jid(self.uuid)
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
        status, _ = iocage.lib.ioc_list.IOCList().list_get_jid(self.uuid)
        if not status:
            return

        proc = su.Popen(["umount", "-f", dest], stdout=su.PIPE, stderr=su.PIPE)
        stdout_data, stderr_data = proc.communicate()

        if stderr_data:
            raise RuntimeError(f"{stderr_data.decode('utf-8')}")

    def __fstab_edit__(self):
        """
        Opens up the users EDITOR, or vi and replaces the jail's fstab
        with the new content.
        """
        editor = os.environ.get("EDITOR", "/usr/bin/vi")
        err_editor = editor.split("/")[-1]
        jail_fstab = f"{self.iocroot}/jails/{self.uuid}/fstab"
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
