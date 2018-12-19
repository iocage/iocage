# Copyright (c) 2014-2018, iocage
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
"""iocage upgrade module"""
import datetime
import fileinput
import os
import pathlib
import subprocess as su
import tempfile
import urllib.request

import iocage_lib.ioc_common
import iocage_lib.ioc_json
import iocage_lib.ioc_list


class IOCUpgrade(object):

    """Will upgrade a jail to the specified RELEASE."""

    def __init__(self,
                 new_release,
                 path,
                 silent=False,
                 callback=None,
                 ):
        self.pool = iocage_lib.ioc_json.IOCJson().json_get_value("pool")
        self.iocroot = iocage_lib.ioc_json.IOCJson(
            self.pool).json_get_value("iocroot")
        self.freebsd_version = iocage_lib.ioc_common.checkoutput(
            ["freebsd-version"])
        self.conf = iocage_lib.ioc_json.IOCJson(path.rsplit(
            '/root', 1)[0]).json_get_value('all')
        self.uuid = self.conf["host_hostuuid"]
        self.host_release = os.uname()[2]
        _release = self.conf["release"].rsplit("-", 1)[0]
        self.jail_release = _release if "-RELEASE" in _release else \
            self.conf["release"]
        self.new_release = new_release
        self.path = path
        self.status, self.jid = iocage_lib.ioc_list.IOCList.list_get_jid(
            self.uuid)
        self._freebsd_version = f"{self.iocroot}/jails/" \
            f"{self.uuid}/root/bin/freebsd-version"
        self.date = datetime.datetime.utcnow().strftime("%F")
        self.silent = silent

        path = '/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:'\
               '/usr/local/bin:/root/bin'
        self.upgrade_env = {
            'PAGER': '/bin/cat',
            'PATH': path,
            'PWD': '/',
            'HOME': '/',
            'TERM': 'xterm-256color'
        }

        self.callback = callback

    def upgrade_jail(self):
        tmp_dataset = self.zfs_get_dataset_name('/tmp')
        tmp_val = self.zfs_get_property(tmp_dataset, 'exec')

        if tmp_val == 'off':
            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': f'{tmp_dataset} needs exec=on!'
                },
                _callback=self.callback,
                silent=self.silent)

        if "HBSD" in self.freebsd_version:
            su.Popen(["hbsd-upgrade", "-j", self.jid]).communicate()

            return

        if not os.path.isfile(f"{self.path}/etc/freebsd-update.conf"):
            return

        self.__upgrade_check_conf__()

        f = "https://raw.githubusercontent.com/freebsd/freebsd" \
            "/master/usr.sbin/freebsd-update/freebsd-update.sh"

        tmp = None
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False)
            with urllib.request.urlopen(f) as fbsd_update:
                tmp.write(fbsd_update.read())
            tmp.close()
            os.chmod(tmp.name, 0o755)

            fetch_cmd = [
                tmp.name, "-b", self.path, "-d",
                f"{self.path}/var/db/freebsd-update/", "-f",
                f"{self.path}/etc/freebsd-update.conf",
                "--not-running-from-cron", "--currently-running "
                f"{self.jail_release}", "-r", self.new_release, "upgrade"
            ]
            with iocage_lib.ioc_exec.IOCExec(
                fetch_cmd,
                self.uuid,
                self.path.replace('/root', ''),
                unjailed=True,
                stdin_bytestring=b'y\n',
                callback=self.callback,
            ) as _exec:
                iocage_lib.ioc_common.consume_and_log(
                    _exec,
                    callback=self.callback
                )

            while not self.__upgrade_install__(tmp.name):
                pass

            new_release = iocage_lib.ioc_common.get_jail_freebsd_version(
                self.path,
                self.new_release
            )
        finally:
            if tmp:
                if not tmp.closed:
                    tmp.close()
                os.remove(tmp.name)

        iocage_lib.ioc_json.IOCJson(
            self.path.replace('/root', ''),
            silent=True).json_set_value(f"release={new_release}")

        return new_release

    def upgrade_basejail(self, snapshot=True):
        if "HBSD" in self.freebsd_version:
            # TODO: Not supported yet
            msg = "Upgrading basejails on HardenedBSD is not supported yet."
            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": msg
                },
                _callback=self.callback,
                silent=self.silent)

        release_p = pathlib.Path(f"{self.iocroot}/releases/{self.new_release}")
        self._freebsd_version = f"{self.iocroot}/releases/"\
            f"{self.new_release}/root/bin/freebsd-version"

        if not release_p.exists():
            msg = f"{self.new_release} is missing, please fetch it!"
            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": msg
                },
                _callback=self.callback,
                silent=self.silent)

        if snapshot:
            self.__snapshot_jail__()

        p = pathlib.Path(
            f"{self.iocroot}/releases/{self.new_release}/root/usr/src")
        p_files = []

        if p.exists():
            for f in p.iterdir():
                # We want to make sure files actually exist as well
                p_files.append(f)

        if not p_files:
            msg = f"{self.new_release} is missing 'src.txz', please refetch!"
            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": msg
                },
                _callback=self.callback,
                silent=self.silent)

        self.__upgrade_replace_basejail_paths__()
        ioc_up_dir = pathlib.Path(f"{self.path}/iocage_upgrade")

        if not ioc_up_dir.exists():
            ioc_up_dir.mkdir(exist_ok=True, parents=True)

        mount_cmd = [
            "mount_nullfs", "-o", "ro",
            f"{self.iocroot}/releases/{self.new_release}/root/usr/src",
            f"{self.path}/iocage_upgrade"
        ]
        try:
            iocage_lib.ioc_exec.SilentExec(
                mount_cmd,
                self.uuid,
                self.path.replace('/root', ''),
                unjailed=True
            )
        except iocage_lib.ioc_exceptions.CommandFailed:
            msg = "Mounting src into jail failed! Rolling back snapshot."
            self.__rollback_jail__()

            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": msg
                },
                _callback=self.callback,
                silent=self.silent)

        etcupdate_cmd = [
            "/usr/sbin/jexec", f"ioc-{self.uuid.replace('.', '_')}",
            "/usr/sbin/etcupdate", "-F", "-s", "/iocage_upgrade"
        ]
        try:
            iocage_lib.ioc_exec.SilentExec(
                etcupdate_cmd,
                self.uuid,
                self.path.replace('/root', ''),
                unjailed=True
            )
        except iocage_lib.ioc_exceptions.CommandFailed:
            # These are now the result of a failed merge, nuking and putting
            # the backup back
            msg = "etcupdate failed! Rolling back snapshot."
            self.__rollback_jail__()

            su.Popen([
                "umount", "-f", f"{self.path}/iocage_upgrade"
            ]).communicate()

            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": msg
                },
                _callback=self.callback,
                silent=self.silent)

        new_release = iocage_lib.ioc_common.get_jail_freebsd_version(
            f'{self.iocroot}/releases/{self.new_release}/root',
            self.new_release
        )

        iocage_lib.ioc_json.IOCJson(
            f"{self.path.replace('/root', '')}",
            silent=True).json_set_value(f"release={new_release}")

        mq = pathlib.Path(f"{self.path}/var/spool/mqueue")

        if not mq.exists():
            mq.mkdir(exist_ok=True, parents=True)

        iocage_lib.ioc_exec.SilentExec(
            ['newaliases'],
            self.uuid,
            self.path.replace('/root', ''),
        )

        umount_command = [
            "umount", "-f", f"{self.path}/iocage_upgrade"
        ]
        iocage_lib.ioc_exec.SilentExec(
            umount_command,
            self.uuid,
            self.path.replace('/root', ''),
            unjailed=True
        )

        return new_release

    def __upgrade_install__(self, name):
        """Installs the upgrade and returns the exit code."""
        install_cmd = [
            name, "-b", self.path, "-d",
            f"{self.path}/var/db/freebsd-update/", "-f",
            f"{self.path}/etc/freebsd-update.conf", "-r", self.new_release,
            "install"
        ]

        with iocage_lib.ioc_exec.IOCExec(
            install_cmd,
            self.uuid,
            self.path.replace('/root', ''),
            unjailed=True,
            callback=self.callback,
        ) as _exec:
            update_output = iocage_lib.ioc_common.consume_and_log(
                _exec,
                callback=self.callback
            )

        for i in update_output:
            if i == 'No updates are available to install.':
                return True

        return False

    def __upgrade_check_conf__(self):
        """
        Replaces freebsd-update.conf's default Components configuration to not
        update kernel
        """
        f = f"{self.path}/etc/freebsd-update.conf"
        text = "Components src world kernel"
        replace = "Components src world"

        self.__upgrade_replace_text__(f, text, replace)

    def __upgrade_replace_basejail_paths__(self):
        f = f"{self.iocroot}/jails/{self.uuid}/fstab"
        self.__upgrade_replace_text__(f, self.jail_release, self.new_release)

    @staticmethod
    def __upgrade_replace_text__(path, text, replace):
        with fileinput.FileInput(path, inplace=True, backup=".bak") as _file:
            for line in _file:
                print(line.replace(text, replace), end='')

        os.remove(f"{path}.bak")

    def __snapshot_jail__(self):
        import iocage_lib.iocage as ioc  # Avoids dep issues
        name = f"ioc_upgrade_{self.date}"
        ioc.IOCage(jail=self.uuid, skip_jails=True, silent=True).snapshot(name)

    def __rollback_jail__(self):
        import iocage_lib.iocage as ioc  # Avoids dep issues
        name = f"ioc_upgrade_{self.date}"
        iocage = ioc.IOCage(jail=self.uuid, skip_jails=True, silent=True)
        iocage.stop()
        iocage.rollback(name)
