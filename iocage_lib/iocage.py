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

import collections
import datetime
import json
import operator
import os
import subprocess as su

import iocage_lib.ioc_clean as ioc_clean
import iocage_lib.ioc_common as ioc_common
import iocage_lib.ioc_create as ioc_create
import iocage_lib.ioc_destroy as ioc_destroy
import iocage_lib.ioc_exec as ioc_exec
import iocage_lib.ioc_fetch as ioc_fetch
import iocage_lib.ioc_fstab as ioc_fstab
import iocage_lib.ioc_image as ioc_image
import iocage_lib.ioc_json as ioc_json
import iocage_lib.ioc_list as ioc_list
import iocage_lib.ioc_plugin as ioc_plugin
import iocage_lib.ioc_start as ioc_start
import iocage_lib.ioc_stop as ioc_stop
import iocage_lib.ioc_upgrade as ioc_upgrade
import iocage_lib.ioc_debug as ioc_debug
import iocage_lib.ioc_exceptions as ioc_exceptions

from iocage_lib.cache import cache
from iocage_lib.dataset import Dataset
from iocage_lib.pools import Pool, PoolListableResource
from iocage_lib.release import Release
from iocage_lib.snapshot import SnapshotListableResource, Snapshot


class PoolAndDataset:

    def get_pool(self):
        """
        Helper to get the current pool.

        Return:
                string: with the pool name.
        """

        return ioc_json.IOCJson().json_get_value("pool")

    def get_iocroot(self):
        """
        Helper to get the iocroot.

        Return:
                string: with the iocroot name.
        """
        return ioc_json.IOCJson().json_get_value("iocroot")


class IOCage:

    def __init__(
        self, jail=None, rc=False, callback=None, silent=False,
        activate=False, skip_jails=False, reset_cache=False,
    ):
        self.rc = rc
        self.silent = silent

        # FreeNAS won't be entering through the CLI, so we set sane defaults
        os.environ.get("IOCAGE_SKIP", "FALSE")
        os.environ.get("IOCAGE_FORCE", "TRUE")

        if reset_cache:
            self.reset_cache()

        self.generic_iocjson = ioc_json.IOCJson()
        if not activate:
            self.pool = self.generic_iocjson.pool
            self.iocroot = self.generic_iocjson.iocroot

            if not skip_jails:
                # When they need to destroy a jail with a missing or bad
                # configuration, this gets in our way otherwise.
                self.jails = self.list("uuid")

        self.skip_jails = skip_jails
        self.jail = jail
        self._all = True if self.jail and 'ALL' in self.jail else False
        self.callback = callback
        self.is_depend = False

    @staticmethod
    def reset_cache():
        cache.reset()

    def __all__(self, jail_order, action, ignore_exception=False):
        # So we can properly start these.
        self._all = False

        for j in jail_order:
            # We want this to be the real jail now.
            self.jail = j
            uuid, path = self.__check_jail_existence__()
            status, jid = self.list("jid", uuid=uuid)

            if action == 'stop':
                self.stop(j, ignore_exception=ignore_exception)
            elif action == 'start':
                if not status:
                    err, msg = self.start(j, ignore_exception=ignore_exception)

                    if err:
                        ioc_common.logit(
                            {
                                'level': 'ERROR',
                                'message': msg
                            },
                            _callback=self.callback, silent=self.silent
                        )
                else:
                    message = f"{uuid} ({j}) is already running!"
                    ioc_common.logit(
                        {
                            'level': 'WARNING',
                            'message': message
                        },
                        _callback=self.callback, silent=self.silent
                    )

    def __jail_order__(self, action, ignore_exception=False):
        """Helper to gather lists of all the jails by order and boot order."""
        jail_order = {}
        boot_order = {}

        _reverse = True if action == 'stop' else False

        for jail in self.jails:
            self.jail = jail
            uuid, path = self.__check_jail_existence__()
            conf = ioc_json.IOCJson(path).json_get_value('all')
            boot = conf['boot']
            priority = conf['priority']
            jail_order[jail] = int(priority)

            # This removes having to grab all the JSON again later.

            if boot:
                boot_order[jail] = int(priority)

            jail_order = collections.OrderedDict(
                sorted(
                    jail_order.items(),
                    key=operator.itemgetter(1),
                    reverse=_reverse))
            boot_order = collections.OrderedDict(
                sorted(
                    boot_order.items(),
                    key=operator.itemgetter(1),
                    reverse=_reverse))

        if self.rc:
            self.__rc__(boot_order, action, ignore_exception)
        elif self._all:
            self.__all__(jail_order, action, ignore_exception)

    def __rc__(self, boot_order, action, ignore_exception=False):
        """Helper to start all jails with boot=on"""
        # So we can properly start these.
        self.rc = False

        for j in boot_order.keys():
            # We want this to be the real jail now.
            self.jail = j

            uuid, path = self.__check_jail_existence__()
            status, _ = self.list("jid", uuid=uuid)

            if action == 'stop':
                if status:
                    message = f"  Stopping {uuid}"
                    ioc_common.logit(
                        {
                            'level': 'INFO',
                            'message': message
                        },
                        _callback=self.callback, silent=self.silent
                    )

                    self.stop(j, ignore_exception=ignore_exception)
                else:
                    message = f"{uuid} is not running!"
                    ioc_common.logit(
                        {
                            'level': 'INFO',
                            'message': message
                        },
                        _callback=self.callback, silent=self.silent
                    )
            elif action == 'start':
                if not status:
                    message = f"  Starting {uuid}"
                    ioc_common.logit(
                        {
                            'level': 'INFO',
                            'message': message
                        },
                        _callback=self.callback, silent=self.silent
                    )

                    err, msg = self.start(j, ignore_exception=ignore_exception)

                    if err:
                        ioc_common.logit(
                            {
                                'level': 'ERROR',
                                'message': msg
                            },
                            _callback=self.callback, silent=self.silent
                        )
                else:
                    message = f"{uuid} is already running!"
                    ioc_common.logit(
                        {
                            'level': 'WARNING',
                            'message': message
                        },
                        _callback=self.callback, silent=self.silent
                    )

    def __check_jail_existence__(self):
        """
        Helper to check if jail dataset exists
        Return:
                tuple: The jails uuid, path
        """

        if os.path.isdir(f"{self.iocroot}/jails/{self.jail}"):
            path = f"{self.iocroot}/jails/{self.jail}"

            return self.jail, path
        elif os.path.isdir(f"{self.iocroot}/templates/{self.jail}"):
            path = f"{self.iocroot}/templates/{self.jail}"

            return self.jail, path
        else:
            if self.skip_jails:
                # We skip jails for performance, but if they didn't match be
                #  now need to gather the list and iterate.
                self.jails = self.list("uuid")

            # We got a partial, time to search.
            _jail = {
                uuid: path

                for (uuid, path) in self.jails.items()

                if uuid.startswith(self.jail)
            }

            if len(_jail) == 1:
                uuid, path = next(iter(_jail.items()))

                return uuid, path
            elif len(_jail) > 1:
                msg = f"Multiple jails found for {self.jail}:"

                for u, p in sorted(_jail.items()):
                    msg += f"\n  {u} ({p})"

                ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": msg
                    },
                    _callback=self.callback,
                    silent=self.silent)
            else:
                msg = f"jail '{self.jail}' not found!"

                ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": msg
                    },
                    _callback=self.callback,
                    silent=self.silent)

    @staticmethod
    def __check_jail_type__(_type, uuid):
        """
        Return:
            tuple: True if error with a message, or False/None
        """

        if _type in ("jail", "plugin", "clonejail", "pluginv2"):
            return False, None
        elif _type == 'basejail':
            return (True, "Please run \"iocage migrate\" before trying to"
                    f" start {uuid}")
        elif _type == 'template':
            return (True, "Please convert back to a jail before trying to"
                    f" start {uuid}")
        else:
            return True, f"{_type} is not a supported jail type."

    @staticmethod
    def __mount__(path, _type):
        if _type == "devfs":
            cmd = ["mount", "-t", "devfs", "devfs", path]
        else:
            cmd = ["mount", "-a", "-F", path]

        _, stderr = su.Popen(cmd, stdout=su.PIPE, stderr=su.PIPE).communicate()

        return stderr

    @staticmethod
    def __umount__(path, _type):
        if _type == "devfs":
            cmd = ["umount", path]
        else:
            cmd = ["umount", "-a", "-F", path]

        _, stderr = su.Popen(cmd, stdout=su.PIPE, stderr=su.PIPE).communicate()

        return stderr

    def activate(self, zpool):
        """Activates the zpool for iocage usage"""
        zpool = Pool(zpool, cache=False)
        if not zpool.exists:
            ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": f"ZFS pool '{zpool}' not found!"
                },
                _callback=self.callback,
                silent=self.silent)

        for pool in PoolListableResource():
            if pool == zpool:
                locked_error = None
                if pool.root_dataset.locked:
                    locked_error = f'ZFS pool "{zpool}" root dataset is locked'

                iocage_ds = Dataset(os.path.join(zpool.name, 'iocage'))
                if iocage_ds.exists and iocage_ds.locked:
                    locked_error = f'ZFS dataset "{iocage_ds.name}" is locked'
                if locked_error:
                    ioc_common.logit(
                        {
                            'level': 'EXCEPTION',
                            'message': locked_error,
                        },
                        _callback=self.callback,
                        silent=self.silent,
                    )
                else:
                    pool.activate_pool()
            else:
                pool.deactivate_pool()

    def deactivate(self, zpool):
        zpool = Pool(zpool, cache=False)
        if not zpool.exists:
            ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': f'ZFS pool "{zpool}" not found!'
                },
                _callback=self.callback,
                silent=self.silent)
        zpool.deactivate_pool()

    def chroot(self, command):
        """Deprecated: Chroots into a jail and runs a command, or the shell."""
        ioc_common.logit(
            {
                "level": "INFO",
                "message":
                (
                    "iocage chroot is deprecated. "
                    "If you need to execute a {} inside the jail use: {}"
                ).format(*[
                    ["shell", "iocage console"],
                    ["command", "iocage exec"]
                ][int(len(command) != 0)])
            },
            _callback=self.callback,
            silent=self.silent)

    def clean(self, d_type):
        """Destroys all of a specified dataset types."""
        if d_type == 'jails':
            ioc_clean.IOCClean(silent=self.silent).clean_jails()
            ioc_common.logit(
                {
                    'level': 'INFO',
                    'message': 'All iocage jail datasets have been destroyed.'
                },
                _callback=self.callback,
                silent=self.silent)
        elif d_type == 'all':
            ioc_clean.IOCClean(silent=self.silent).clean_all()
            ioc_common.logit(
                {
                    'level': 'INFO',
                    'message': 'All iocage datasets have been destroyed.'
                },
                _callback=self.callback,
                silent=self.silent)
        elif d_type == 'release':
            ioc_clean.IOCClean(silent=self.silent).clean_releases()
            ioc_common.logit(
                {
                    'level': 'INFO',
                    'message': 'All iocage RELEASE and jail datasets have been'
                               ' destroyed.'
                },
                _callback=self.callback,
                silent=self.silent)
        elif d_type == 'template':
            ioc_clean.IOCClean(silent=self.silent).clean_templates()
            ioc_common.logit(
                {
                    'level': 'INFO',
                    'message':
                    'All iocage template datasets have been destroyed.'
                },
                _callback=self.callback,
                silent=self.silent)
        elif d_type == 'images':
            ioc_clean.IOCClean(silent=self.silent).clean_images()
            ioc_common.logit(
                {
                    'level': 'INFO',
                    'message': 'The iocage images dataset has been destroyed.'
                },
                _callback=self.callback,
                silent=self.silent)
        elif d_type == 'debug':
            ioc_clean.IOCClean(silent=self.silent).clean_debug()
            ioc_common.logit(
                {
                    'level': 'INFO',
                    'message': 'All iocage debugs have been destroyed.'
                },
                _callback=self.callback,
                silent=self.silent)
        else:
            ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": "Please specify a dataset type to clean!"
                },
                _callback=self.callback,
                silent=self.silent)

    def create(self,
               release,
               props,
               count=0,
               pkglist=None,
               template=False,
               short=False,
               _uuid=None,
               basejail=False,
               thickjail=False,
               empty=False,
               clone=None,
               skip_batch=False,
               thickconfig=False,
               clone_basejail=False):
        """Creates the jail dataset"""
        count = 0 if count == 1 and not skip_batch else count

        if short and _uuid:
            _uuid = _uuid[:8]

            if len(_uuid) != 8:
                ioc_common.logit(
                    {
                        "level":
                        "EXCEPTION",
                        "message":
                        "Need a minimum of 8 characters to use --short"
                        " (-s) and --uuid (-u) together!"
                    },
                    _callback=self.callback,
                    silent=self.silent)

        if not template and not release and not empty and not clone:
            ioc_common.logit(
                {
                    "level":
                    "EXCEPTION",
                    "message":
                    "Must supply either --template (-t) or"
                    " --release (-r)!"
                },
                _callback=self.callback,
                silent=self.silent)

        if release is not None:
            if os.path.isdir(
                f'{self.iocroot}/releases/{release.upper()}'
            ) and not template and not empty and not clone:
                release = release.upper()

        if not os.path.isdir(
            f'{self.iocroot}/releases/{release}'
        ) and not template and not empty and not clone:
            freebsd_version = ioc_common.checkoutput(["freebsd-version"])

            if "HBSD" in freebsd_version:
                hardened = True
            else:
                hardened = False

            arch = os.uname()[4]

            if arch in {'i386', 'arm64'}:
                files = ['MANIFEST', 'base.txz', 'src.txz']
            else:
                files = ['MANIFEST', 'base.txz', 'lib32.txz', 'src.txz']

            try:
                if int(release.rsplit('-')[0].rsplit('.')[0]) < 12:
                    # doc.txz has relevance here still
                    files.append('doc.txz')
            except (AttributeError, ValueError):
                # Non-standard naming scheme, assuming it's current
                pass

            ioc_fetch.IOCFetch(
                release,
                hardened=hardened,
                files=files,
                silent=self.silent
            ).fetch_release()

        if clone:
            clone_uuid, path = self.__check_jail_existence__()

            if 'templates' in path:
                template = True

            status, _ = self.list("jid", uuid=clone_uuid)

            if status:
                ioc_common.logit(
                    {
                        "level":
                        "EXCEPTION",
                        "message":
                        f"Jail: {self.jail} must not be running to be"
                        " cloned!"
                    },
                    _callback=self.callback,
                    silent=self.silent)

            release = clone_uuid
            clone = self.jail

        try:
            if count > 1 and not skip_batch:
                for j in range(1, count + 1):

                    self.create(
                        release,
                        props,
                        j,
                        pkglist=pkglist,
                        template=template,
                        short=short,
                        _uuid=f"{_uuid}_{j}" if _uuid else None,
                        basejail=basejail,
                        thickjail=thickjail,
                        empty=empty,
                        clone=clone,
                        skip_batch=True,
                        thickconfig=thickconfig,
                        clone_basejail=clone_basejail)
            else:
                ioc_create.IOCCreate(
                    release,
                    props,
                    count,
                    pkglist,
                    silent=self.silent,
                    template=template,
                    short=short,
                    basejail=basejail,
                    thickjail=thickjail,
                    empty=empty,
                    uuid=_uuid,
                    clone=clone,
                    thickconfig=thickconfig,
                    clone_basejail=clone_basejail
                ).create_jail()
        except BaseException:
            if clone:
                su.run(
                    [
                        'zfs', 'destroy', '-r',
                        f'{self.pool}/iocage/jails/{clone}@{_uuid}'
                    ]
                )
            raise

        return False, None

    def destroy_release(self, download=False):
        """Destroy supplied RELEASE and the download dataset if asked"""
        path = f"{self.pool}/iocage/releases/{self.jail}"

        release = Release(self.jail)
        # Let's make sure the release exists before we try to destroy it
        if not release:
            ioc_common.logit({
                'level': 'EXCEPTION',
                'message': f'Release: {self.jail} not found!'
            })

        ioc_common.logit(
            {
                "level": "INFO",
                "message": f"Destroying RELEASE dataset: {self.jail}"
            },
            _callback=self.callback,
            silent=self.silent)

        ioc_destroy.IOCDestroy().__destroy_parse_datasets__(path, stop=False)

        if download:
            path = f"{self.pool}/iocage/download/{self.jail}"
            ioc_common.logit(
                {
                    "level": "INFO",
                    "message":
                    f"Destroying RELEASE download dataset: {self.jail}"
                },
                _callback=self.callback,
                silent=self.silent)

            ioc_destroy.IOCDestroy().__destroy_parse_datasets__(path,
                                                                stop=False)

    def destroy_jail(self, force=False):
        """
        Destroys the supplied jail, to reduce perfomance hit,
        call IOCage with skip_jails=True
        """
        try:
            self.jails = self.list("uuid")
        except (RuntimeError, SystemExit) as err:
            err = str(err)

            if "Configuration is missing" in err:
                uuid = err.split()[5]
                path = f"{self.pool}/iocage/jails/{uuid}"

                if uuid == self.jail:
                    ioc_destroy.IOCDestroy().__destroy_parse_datasets__(
                        path, stop=False)

                    ioc_common.logit(
                        {
                            "level": "INFO",
                            "message": f"{uuid} destroyed"
                        },
                        _callback=self.callback,
                        silent=self.silent)

                    return
                else:
                    ioc_common.logit(
                        {
                            "level": "EXCEPTION",
                            "message": err
                        },
                        _callback=self.callback,
                        silent=self.silent)
        except FileNotFoundError as err:
            # Jail is lacking a configuration, time to nuke it from orbit.
            uuid = str(err).rsplit("/")[-2]
            path = f"{self.pool}/iocage/jails/{uuid}"

            if uuid == self.jail:
                ioc_destroy.IOCDestroy().__destroy_parse_datasets__(path)

                return
            else:
                ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": err
                    },
                    _callback=self.callback,
                    silent=self.silent)

        uuid, path = self.__check_jail_existence__()
        status, _ = self.list("jid", uuid=uuid)

        if status:
            if not force:
                ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": (f"Jail {uuid} is still running, "
                                    f"please stop the jail first "
                                    f"or destroy it with -f")
                    },
                    _callback=self.callback,
                    silent=self.silent)
            else:
                ioc_common.logit(
                    {
                        "level": "INFO",
                        "message": f"Stopping {uuid}"
                    },
                    _callback=self.callback,
                    silent=self.silent)

        ioc_common.logit(
            {
                "level": "INFO",
                "message": f"Destroying {uuid}"
            },
            _callback=self.callback,
            silent=self.silent)

        ioc_destroy.IOCDestroy().destroy_jail(path)

    def df(self):
        """Returns a list containing the resource usage of all jails"""
        jail_list = []

        for jail, path in self.jails.items():
            conf = ioc_json.IOCJson(path).json_get_value('all')
            mountpoint = f"{self.pool}/iocage/jails/{jail}"

            template = conf["type"]

            if template == "template":
                mountpoint = f"{self.pool}/iocage/templates/{jail}"

            ds = Dataset(mountpoint)
            zconf = ds.properties

            compressratio = zconf["compressratio"]
            reservation = zconf["reservation"]
            quota = zconf["quota"]
            used = zconf["used"]
            available = zconf["available"]

            jail_list.append(
                [jail, compressratio, reservation, quota, used, available])

        return jail_list

    def exec_all(
        self, command, host_user='root', jail_user=None, console=False,
        start_jail=False, interactive=False, unjailed=False, msg_return=False
    ):
        """Runs exec for all jails"""
        self._all = False
        for jail in self.jails:
            self.jail = jail
            self.exec(
                command, host_user, jail_user, console, start_jail,
                interactive, unjailed, msg_return
            )

    def exec(
        self, command, host_user='root', jail_user=None, console=False,
        start_jail=False, interactive=False, unjailed=False, msg_return=False
    ):
        """Executes a command in the jail as the supplied users."""
        if self._all:
            self.exec_all(
                command, host_user, jail_user, console, start_jail,
                interactive, unjailed, msg_return
            )
            return

        pkg = unjailed

        if host_user and jail_user is not None:
            ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': 'Please only specify either host_user or'
                    ' jail_user, not both!'
                },
                _callback=self.callback,
                silent=self.silent)

        uuid, path = self.__check_jail_existence__()
        exec_clean = self.get('exec_clean')

        if exec_clean:
            env_path = '/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:' \
                '/usr/local/bin:/root/bin'
            env_lang = os.environ.get('LANG', 'en_US.UTF-8')
            su_env = {
                'PATH': env_path,
                'PWD': '/',
                'HOME': '/',
                'TERM': 'xterm-256color',
                'LANG': env_lang,
                'LC_ALL': env_lang
            }
        else:
            su_env = os.environ.copy()

        status, jid = self.list("jid", uuid=uuid)

        if not status and not start_jail:
            if not ioc_common.INTERACTIVE:
                ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": f'{self.jail} is not running! Please supply'
                                   ' start_jail=True or start the jail'
                    },
                    _callback=self.callback,
                    silent=self.silent)
            else:
                ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": f'{self.jail} is not running! Please supply'
                                   ' --force (-f) or start the jail'
                    },
                    _callback=self.callback,
                    silent=self.silent)
        elif not status:
            self.start()
            status, jid = self.list("jid", uuid=uuid)

        if pkg:
            ip4_addr = self.get("ip4_addr")
            ip6_addr = self.get("ip6_addr")
            dhcp = self.get("dhcp")
            nat = self.get('nat')

            if (
                ip4_addr == ip6_addr == "none" and not dhcp and not nat
            ):
                ioc_common.logit(
                    {
                        "level":
                        "EXCEPTION",
                        "message":
                        "The jail requires an IP address before you "
                        "can use pkg. Set one and restart the jail."
                    },
                    _callback=self.callback,
                    silent=self.silent)

            command = ["pkg", "-j", jid] + list(command)

        if console:
            login_flags = self.get('login_flags').split()
            console_cmd = ['login', '-p'] + login_flags

            try:
                ioc_exec.InteractiveExec(console_cmd, path, uuid=uuid)
            except BaseException as e:
                ioc_common.logit(
                    {
                        'level': 'ERROR',
                        'message': 'Console failed!\nThe cause could be bad '
                                   f'permissions for {path}/root/usr/lib.'
                    },
                    _callback=self.callback,
                    silent=False
                )
                raise e
            return

        if interactive:
            ioc_exec.InteractiveExec(
                command,
                path,
                uuid=uuid,
                host_user=host_user,
                jail_user=jail_user,
                skip=True
            )
            return

        try:
            with ioc_exec.IOCExec(
                command,
                path,
                uuid=uuid,
                host_user=host_user,
                jail_user=jail_user,
                unjailed=pkg,
                su_env=su_env
            ) as _exec:
                output = ioc_common.consume_and_log(
                    _exec
                )

                if msg_return:
                    return output['stdout']

                for line in output['stdout']:
                    ioc_common.logit(
                        {
                            "level": "INFO",
                            "message": line
                        },
                        _callback=self.callback,
                        silent=self.silent)
        except ioc_exceptions.CommandFailed as e:
            msgs = [_msg.decode().rstrip() for _msg in e.message]
            if msgs:
                ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": '\n'.join(msgs)
                    },
                    _callback=self.callback,
                    silent=self.silent)
            else:
                ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": f'Command: {command} failed!'
                    },
                    _callback=self.callback,
                    silent=self.silent)

    def export(self, compression_algo='zip'):
        """Will export a jail"""
        uuid, path = self.__check_jail_existence__()
        status, _ = self.list("jid", uuid=uuid)

        if status:
            ioc_common.logit(
                {
                    "level":
                    "EXCEPTION",
                    "message":
                    f"{uuid} is running, stop the jail before"
                    " exporting!"
                },
                _callback=self.callback,
                silent=self.silent)

        ioc_image.IOCImage().export_jail(
            uuid, path, compression_algo=compression_algo
        )

    def fetch(self, **kwargs):
        """Fetches a release or plugin."""
        release = kwargs.pop("release", None)
        name = kwargs.pop("name", None)
        props = kwargs.pop("props", ())
        plugins = kwargs.pop("plugins", False)
        plugin_name = kwargs.pop("plugin_name", None)
        count = kwargs.pop("count", 1)
        accept = kwargs.pop("accept", False)
        _list = kwargs.pop("list", False)
        remote = kwargs.pop("remote", False)
        http = kwargs.get("http", True)
        hardened = kwargs.get("hardened", False)
        header = kwargs.pop("header", True)
        _long = kwargs.pop("_long", False)
        official = kwargs.pop("official", False)
        branch = kwargs.pop("branch", None)
        keep_jail_on_failure = kwargs.pop("keep_jail_on_failure", False)
        thick_config = kwargs.pop("thickconfig", False)

        freebsd_version = ioc_common.checkoutput(["freebsd-version"])
        arch = os.uname()[4]

        if not _list:
            if not kwargs.get('files', None):
                if arch in {'i386', 'arm64'}:
                    kwargs['files'] = ['MANIFEST', 'base.txz', 'src.txz']
                else:
                    kwargs['files'] = ['MANIFEST', 'base.txz', 'lib32.txz',
                                       'src.txz']

                    try:
                        if int(release.rsplit('-')[0].rsplit('.')[0]) < 12:
                            # doc.txz has relevance here still
                            kwargs['files'].append('doc.txz')
                    except (AttributeError, ValueError):
                        # Non-standard naming scheme, assuming it's current
                        pass

            if "HBSD" in freebsd_version:
                if kwargs["server"] == "download.freebsd.org":
                    kwargs["hardened"] = True
                else:
                    kwargs["hardened"] = False
            else:
                kwargs["hardened"] = False

        if plugins or plugin_name:
            if _list:
                rel_list = ioc_plugin.IOCPlugin(
                    branch=branch,
                    thickconfig=thick_config,
                    **kwargs
                ).fetch_plugin_index(
                    "", _list=True, list_header=header, list_long=_long,
                    icon=True, official=official
                )

                return rel_list

            if plugins:
                ioc_plugin.IOCPlugin(
                    release=release,
                    plugin=plugin_name,
                    branch=branch,
                    thickconfig=thick_config,
                    **kwargs).fetch_plugin_index(
                        props, accept_license=accept, official=official)

                return

            plugin_obj = ioc_plugin.IOCPlugin(
                release=release, plugin=plugin_name,
                branch=branch, silent=self.silent,
                keep_jail_on_failure=keep_jail_on_failure,
                callback=self.callback, **kwargs,
                thickconfig=thick_config,
            )

            i = 1
            check_jail_name = name or plugin_obj.retrieve_plugin_json().get(
                'name', plugin_name
            )
            while True:
                if check_jail_name not in self.jails:
                    jail_name = check_jail_name
                    break
                elif f'{check_jail_name}_{i}' not in self.jails:
                    jail_name = f'{check_jail_name}_{i}'
                    break
                i += 1

            self.jails[jail_name] = jail_name   # Not a valid value
            if count == 1:
                plugin_obj.jail = jail_name
                plugin_obj.fetch_plugin(props, 0, accept)
            else:
                for j in range(1, count + 1):
                    # Repeating this block in case they have gaps in their
                    # plugins
                    # Allows plugin_1, plugin_2, and such to happen instead of
                    # plugin_1_1, plugin_1_2
                    while True:
                        if jail_name not in self.jails:
                            break
                        elif f'{check_jail_name}_{i}' not in self.jails:
                            jail_name = f'{check_jail_name}_{i}'
                            break

                        i += 1

                    self.jails[jail_name] = jail_name   # Not a valid value
                    plugin_obj.jail = jail_name
                    plugin_obj.fetch_plugin(props, j, accept)
        else:
            kwargs.pop('git_repository', None)
            kwargs.pop('git_destination', None)

            if _list:
                if remote:
                    rel_list = ioc_fetch.IOCFetch(
                        "", http=http, hardened=hardened).fetch_release(
                            _list=True)
                else:
                    rel_list = self.list("base")

                return rel_list

            ioc_fetch.IOCFetch(
                release,
                silent=self.silent, callback=self.callback,
                **kwargs).fetch_release()

    def fstab(self,
              action,
              source,
              destination,
              fstype,
              options,
              dump,
              _pass,
              index=None,
              add_path=False,
              header=False):
        """Adds an fstab entry for a jail"""
        uuid, path = self.__check_jail_existence__()

        if action != "list":
            if add_path:
                destination = f"{self.iocroot}/jails/{uuid}/root{destination}"

            if destination and len(destination) > 88:
                ioc_common.logit(
                    {
                        "level":
                        "WARNING",
                        "message":
                        "The destination's mountpoint exceeds 88 "
                        "characters, this may cause failure!"
                    },
                    _callback=self.callback,
                    silent=self.silent)

        if action == "list":
            fstab = ioc_fstab.IOCFstab(
                uuid,
                action,
                source,
                destination,
                fstype,
                options,
                dump,
                _pass,
                index=index,
                header=header,
            ).fstab_list()

            return fstab
        else:
            ioc_fstab.IOCFstab(
                uuid,
                action,
                source,
                destination,
                fstype,
                options,
                dump,
                _pass,
                index=index
            )

    def get(
        self, prop, recursive=False, plugin=False, pool=False, start_jail=False
    ):
        """Get a jail property"""
        if start_jail and not plugin:
            ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message':
                        '--force (-f) is only applicable with --plugin (-P)!'
                },
                _callback=self.callback,
                silent=self.silent)

        if pool:
            return self.pool

        if not recursive:
            if self.jail == "default":
                try:
                    return ioc_json.IOCJson().json_get_value(prop,
                                                             default=True)
                except KeyError:
                    ioc_common.logit(
                        {
                            "level": "EXCEPTION",
                            "message": f"{prop} is not a valid property!"
                        },
                        _callback=self.callback,
                        silent=self.silent)

            uuid, path = self.__check_jail_existence__()
            status, jid = self.list("jid", uuid=uuid)

            state = "up" if status else "down"

            if prop == "state":
                return state
            elif plugin:
                if not status and not start_jail:
                    if not ioc_common.INTERACTIVE:
                        ioc_common.logit(
                            {
                                "level": "EXCEPTION",
                                "message": f'{self.jail} is not running!'
                                           ' Please supply start_jail=True or'
                                           ' start the jail'
                            },
                            _callback=self.callback,
                            silent=self.silent)
                    else:
                        ioc_common.logit(
                            {
                                "level": "EXCEPTION",
                                "message": f'{self.jail} is not running!'
                                           ' Please supply --force (-f) or'
                                           ' start the jail'
                            },
                            _callback=self.callback,
                            silent=self.silent)

                try:
                    _prop = prop.split(".")
                    props = ioc_json.IOCJson(path).json_plugin_get_value(
                        _prop
                    )
                except ioc_exceptions.CommandNeedsRoot as err:
                    ioc_common.logit(
                        {
                            'level': 'EXCEPTION',
                            'message': err.message
                        },
                        _callback=self.callback,
                        silent=False)

                if isinstance(props, dict):
                    return json.dumps(props, indent=4)
                else:
                    return props
            elif prop == "all":
                _props = {}

                props = ioc_json.IOCJson(path).json_get_value(prop)

                # We want this sorted below, so we add it to the old dict
                props["state"] = state

                for key in sorted(props.keys()):
                    _props[key] = props[key]

                return _props
            else:
                try:
                    return ioc_json.IOCJson(path).json_get_value(prop)
                except KeyError:
                    ioc_common.logit(
                        {
                            "level": "EXCEPTION",
                            "message": f"{prop} is not a valid property!"
                        },
                        _callback=self.callback,
                        silent=self.silent)
        else:
            jail_list = []

            for uuid, path in self.jails.items():
                try:
                    status, jid = self.list("jid", uuid=uuid)
                    state = "up" if status else "down"

                    if prop == "state":
                        jail_list.append({uuid: state})
                    elif prop == "all":
                        _props = {}
                        try:
                            props = ioc_json.IOCJson(path).json_get_value(prop)
                        except (Exception, SystemExit):
                            # Jail is corrupt, we want all the keys to exist.
                            # So we will take the defaults and let the user
                            # know that they are not correct.
                            def_props = ioc_json.IOCJson().json_get_value(
                                'all',
                                default=True
                            )
                            jail_list.append({
                                uuid: {
                                    **{x: 'N/A' for x in def_props},
                                    'host_hostuuid': uuid,
                                    'state': 'CORRUPT',
                                    'release': 'N/A',
                                    'jid': None,
                                }
                            })

                            continue

                        # We want this sorted below, so we add it to the old
                        # dict
                        props.update({
                            'state': state,
                            'jid': jid,
                        })

                        for key in sorted(props.keys()):
                            _props[key] = props[key]

                        jail_list.append({uuid: _props})
                    else:
                        jail_list.append({
                            uuid:
                            ioc_json.IOCJson(path).json_get_value(prop)
                        })
                except KeyError:
                    ioc_common.logit(
                        {
                            "level": "EXCEPTION",
                            "message": f"{prop} is not a valid property!"
                        },
                        _callback=self.callback,
                        silent=self.silent)

            sort = ioc_common.ioc_sort("get", "key")
            jail_list.sort(key=sort)

            return jail_list

    def import_(self, compression_algo='zip', path=None):
        """Imports a jail"""
        ioc_image.IOCImage().import_jail(
            self.jail, compression_algo=compression_algo, path=path
        )

    def list(
        self, lst_type, header=False, long=False, sort='name', uuid=None,
        plugin=False, quick=False, **kwargs
    ):
        """Returns a list of lst_type"""

        if lst_type == "jid":
            return ioc_list.IOCList(**kwargs).list_get_jid(uuid)

        return ioc_list.IOCList(
            lst_type,
            header,
            long,
            sort,
            plugin=plugin,
            quick=quick,
            silent=self.silent,
            **kwargs
        ).list_datasets()

    def rename(self, new_name):
        uuid, old_mountpoint = self.__check_jail_existence__()

        _template = False
        _folders = ["jails", "templates"]

        if old_mountpoint.startswith(f"{self.iocroot}/templates/"):
            _template = True
            _folders = _folders[::-1]

        new_mountpoint = f"{self.iocroot}/{_folders[0]}/{new_name}"

        if ioc_common.match_to_dir(self.iocroot, new_name,
                                   old_uuid=old_mountpoint):

            ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": f"Jail: {new_name} already exists!"
                },
                _callback=self.callback,
                silent=self.silent)

        path = f"{self.pool}/iocage/{_folders[0]}/{uuid}"
        new_path = f"{self.pool}/iocage/{_folders[0]}/{new_name}"

        _silent = self.silent
        self.silent = True

        self.stop()

        self.silent = _silent

        # Can't rename when the child is in a non-global zone
        for str_dataset in self.get("jail_zfs_dataset").split():
            data_dataset = Dataset(f'{self.pool}/{str_dataset.strip()}')
            if data_dataset.exists:
                # We only do this when it exists ( keeping old behavior )
                data_dataset.set_property('jailed', 'off')

        for release_snap in SnapshotListableResource().release_snapshots:
            if uuid == release_snap.name:
                rel_ds = release_snap.dataset.name
                su.check_call([
                    'zfs', 'rename', '-r', f'{rel_ds}@{uuid}', f'@{new_name}'
                ])

        dataset = Dataset(path)
        dataset.rename(new_path, {'force_unmount': True})

        self.jail = new_name

        self.silent = True
        self.set(f"host_hostuuid={new_name}", rename=True)

        if self.get("host_hostname") == uuid:
            self.set(f"host_hostname={new_name}")

        zfs_dataset = self.get("jail_zfs_dataset")
        if f"iocage/jails/{uuid}" in zfs_dataset:
            zfs_dataset = zfs_dataset.replace(f"iocage/jails/{uuid}",
                                              f"iocage/jails/{new_name}")
            self.set(f"jail_zfs_dataset={zfs_dataset}")

        self.silent = _silent

        # Templates are readonly
        if _template:
            # All self.set's set this back to on, this must be last
            dataset.set_property('readonly', 'off')

        # Adjust mountpoints in fstab
        jail_fstab = f"{new_mountpoint}/fstab"

        try:
            with open(jail_fstab, "r") as fstab:
                with ioc_common.open_atomic(jail_fstab, "w") as _fstab:
                    for line in fstab.readlines():
                        _fstab.write(line.replace(
                            f"{self.iocroot}/jails/{uuid}/",
                            f"{self.iocroot}/jails/{new_name}/"))
        except OSError:
            pass

        if _template:
            for jail, path in self.jails.items():
                # Stale list and isn't relevant for our loop anyways
                if jail == uuid:
                    continue

                _json = ioc_json.IOCJson(path, silent=True)

                try:
                    source_template = _json.json_get_value('source_template')
                except KeyError:
                    continue

                if source_template == uuid:
                    _json.json_set_value(f'source_template={new_name}')

            dataset.set_property('readonly', 'on')

        ioc_common.logit(
            {
                "level": "INFO",
                "message": f"Jail: {uuid} renamed to {new_name}"
            },
            _callback=self.callback,
            silent=self.silent)

    def restart(self, soft=False):
        if self._all:
            if not soft:
                self.__jail_order__("stop")
                # This gets unset each time.
                self._all = True

                self.__jail_order__("start")
            else:
                for j in self.jails:
                    self.jail = j
                    self.__soft_restart__()
        else:
            if not soft:
                # __rc__ will set this to false for each, we want to preserve
                # it
                _rc = self.rc
                self.stop()

                self.rc = _rc
                self.start()
            else:
                self.__soft_restart__()

    def rollback(self, name):
        """Rolls back a jail and all datasets to the supplied snapshot"""
        uuid, path = self.__check_jail_existence__()
        conf = ioc_json.IOCJson(path, silent=self.silent).json_get_value('all')
        status, _ = self.list("jid", uuid=uuid)

        if status:
            ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": f"Please stop {uuid} before trying to"
                    " rollback!"
                },
                _callback=self.callback,
                silent=self.silent)

        if ioc_common.check_truthy(conf['template']):
            target = f"{self.pool}/iocage/templates/{uuid}"
        else:
            target = f"{self.pool}/iocage/jails/{uuid}"

        dataset = Dataset(target)
        if not dataset.exists:
            ioc_common.logit(
                {'level': 'EXCEPTION', 'message': f'{target} does not exist'},
                _callback=self.callback, silent=self.silent
            )
        snap = Snapshot(f'{dataset.name}@{name}')
        if not snap.exists:
            ioc_common.logit(
                {'level': 'EXCEPTION', 'message': f'{snap} does not exist'},
                _callback=self.callback, silent=self.silent
            )

        for ds in dataset.get_dependents(depth=None):
            if ds.properties['type'] == 'filesystem':
                Snapshot(f'{ds.name}@{name}').rollback(
                    {'destroy_latest': True}
                )

        # datasets is actually the parent.
        snap.rollback({'destroy_latest': True})

        ioc_common.logit(
            {
                "level": "INFO",
                "message": f"Rolled back to: {target}"
            },
            _callback=self.callback,
            silent=self.silent)

    def set(self, prop, plugin=False, rename=False):
        """Sets a property for a jail or plugin"""
        # The cli check prevents users changing unwanted properties. We do
        # want to change a protected property with rename, so we disable that.
        cli = False if rename else True

        try:
            key, value = prop.split("=", 1)
        except ValueError:
            ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": f"{prop} is missing a value!"
                },
                _callback=self.callback,
                silent=self.silent)

        if key == "ip4_addr" or key == "ip6_addr":
            # We don't want spaces here
            value = value.replace(" ", "")

        if self.jail == "default":
            ioc_json.IOCJson().check_default_config()
            default = True
        else:
            default = False

        if default:
            ioc_json.IOCJson(self.iocroot).json_set_value(prop, default=True)
            return

        uuid, path = self.__check_jail_existence__()
        iocjson = ioc_json.IOCJson(
            path,
            cli=cli,
            callback=self.callback,
            silent=self.silent)

        if plugin:
            _prop = prop.split(".")
            iocjson.json_plugin_set_value(_prop)

            return

        if "template" in key:
            if prop in ioc_common.construct_truthy(
                'template'
            ) and path.startswith(
                f'{self.iocroot}/templates/'
            ):
                ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": f"{uuid} is already a template!"
                    },
                    _callback=self.callback,
                    silent=self.silent)

            elif prop in ioc_common.construct_truthy(
                'template', inverse=True
            ) and path.startswith(
                f'{self.iocroot}/jails/'
            ):
                ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": f"{uuid} is already a jail!"
                    },
                    _callback=self.callback,
                    silent=self.silent)

        try:
            # We use this to test if it's a valid property at all.
            _prop = prop.partition("=")[0]
            self.get(_prop)

            # The actual setting of the property.
            iocjson.json_set_value(prop)
        except KeyError:
            _prop = prop.partition("=")[0]
            ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": f"{_prop} is not a valid property!"
                },
                _callback=self.callback,
                silent=self.silent)

        if key == "ip6_addr":
            rtsold_enable = "YES" if "accept_rtadv" in value else "NO"
            ioc_common.set_rcconf(path, "rtsold_enable", rtsold_enable)

    def snap_list(self, long=True, _sort="created"):
        """Gathers a list of snapshots and returns it"""
        uuid, path = self.__check_jail_existence__()
        conf = ioc_json.IOCJson(path, silent=self.silent).json_get_value('all')
        snap_list = []
        snap_list_temp = []
        snap_list_root = []

        if ioc_common.check_truthy(conf['template']):
            full_path = f"{self.pool}/iocage/templates/{uuid}"
        else:
            full_path = f"{self.pool}/iocage/jails/{uuid}"

        dataset = Dataset(full_path)

        for snap in dataset.snapshots_recursive():
            snap_name = snap.name if not long else snap.resource_name
            root_snap_name = snap.resource_name.rsplit("@")[0].split("/")[-1]
            root = False

            if root_snap_name == "root":
                if not long:
                    snap_name += "/root"

                root = True
            elif root_snap_name != uuid:
                # basejail datasets.

                continue

            creation = snap.properties["creation"]
            used = snap.properties["used"]
            referenced = snap.properties["referenced"]

            snap_list_temp.append([snap_name, creation, referenced, used]) \
                if not root else snap_list_root.append([snap_name, creation,
                                                        referenced, used])

        for parent in snap_list_temp:
            # We want the /root snapshots immediately after the parent ones
            name = parent[0]

            if long:
                name, snap_name = parent[0].split("@")
                name = f"{name}/root@{snap_name}"

            for root in snap_list_root:
                _name = root[0]

                # Long has this already, the short comparison will fail.
                root_comparison = name if long else f"{name}/root"

                if root_comparison == _name:
                    snap_list.append(parent)
                    snap_list.append(root)

        sort = ioc_common.ioc_sort("snaplist", _sort, data=snap_list)
        snap_list.sort(key=sort)

        return snap_list

    def snapshot(self, name):
        """Will create a snapshot for the given jail"""
        date = datetime.datetime.utcnow().strftime("%F_%T")
        uuid, path = self.__check_jail_existence__()

        # If they don't supply a snapshot name, we will use the date.

        if not name:
            name = date

        # Looks like foo/iocage/jails/df0ef69a-57b6-4480-b1f8-88f7b6febbdf@BAR
        conf = ioc_json.IOCJson(path, silent=self.silent).json_get_value('all')

        if ioc_common.check_truthy(conf['template']):
            target = f"{self.pool}/iocage/templates/{uuid}"
        else:
            target = f"{self.pool}/iocage/jails/{uuid}"

        snap = Snapshot(f'{target}@{name}')
        if snap.exists:
            ioc_common.logit(
                {
                    'level': 'EXCEPTION', 'force_raise': True,
                    'message': 'Snapshot already exists'
                },
                _callback=self.callback, silent=self.silent,
                exception=ioc_exceptions.Exists
            )

        snap.create_snapshot({'recursive': True})

        if not self.silent:
            ioc_common.logit({
                "level": "INFO",
                "message": f"Snapshot: {target}@{name} created."
            })

    def __soft_restart__(self):
        """
        Executes a soft reboot by keeping the jail network stack intact,
        but executing the rc scripts.
        """
        uuid, path = self.__check_jail_existence__()
        status, jid = self.list("jid", uuid=uuid)
        conf = ioc_json.IOCJson(path, silent=self.silent).json_get_value('all')

        # These need to be a list.
        exec_start = conf["exec_start"].split()
        exec_stop = conf["exec_stop"].split()
        exec_fib = conf["exec_fib"]

        if status:
            ioc_common.logit(
                {
                    "level": "INFO",
                    "message": f"Soft restarting {uuid} ({self.jail})"
                },
                _callback=self.callback,
                silent=self.silent)

            stop_cmd = [
                "setfib", exec_fib, "jexec", f"ioc-{uuid.replace('.', '_')}"
            ] + exec_stop
            su.Popen(stop_cmd, stdout=su.PIPE, stderr=su.PIPE).communicate()

            su.Popen(["pkill", "-j", jid]).communicate()
            start_cmd = [
                "setfib", exec_fib, "jexec", f"ioc-{uuid.replace('.', '_')}"
            ] + exec_start
            su.Popen(start_cmd, stdout=su.PIPE, stderr=su.PIPE).communicate()
            ioc_json.IOCJson(path, silent=True).json_set_value(
                f"last_started={datetime.datetime.utcnow().strftime('%F %T')}")
        else:
            ioc_common.logit(
                {
                    "level": "ERROR",
                    "message": f"{self.jail} is not running!"
                },
                _callback=self.callback,
                silent=self.silent)

    def start(self, jail=None, ignore_exception=False, used_ports=None):
        """Checks jails type and existence, then starts the jail"""
        if self.rc or self._all:
            if not jail:
                self.__jail_order__("start", ignore_exception=ignore_exception)
        else:
            uuid, path = self.__check_jail_existence__()
            conf = ioc_json.IOCJson(path, silent=self.silent).json_get_value(
                'all')
            release = conf["release"]

            if release != "EMPTY":
                release = float(release.rsplit("-", 1)[0].rsplit("-", 1)[0])
                ioc_common.check_release_newer(release, major_only=True)

            err, msg = self.__check_jail_type__(conf["type"], uuid)
            depends = conf["depends"].split()

            if not err:
                for depend in depends:
                    if depend != "none":
                        try:
                            self.jail = depend
                            _is_depend = self.is_depend
                            self.is_depend = True
                            self.start(depend)
                        except ioc_exceptions.JailRunning:
                            pass
                        finally:
                            self.is_depend = _is_depend

                ioc_start.IOCStart(
                    uuid,
                    path,
                    silent=self.silent,
                    callback=self.callback,
                    is_depend=self.is_depend,
                    suppress_exception=ignore_exception,
                    used_ports=used_ports,
                )

                return False, None
            else:
                if jail:
                    return err, msg
                else:
                    ioc_common.logit(
                        {
                            'level': 'ERROR',
                            'message': msg
                        },
                        _callback=self.callback, silent=self.silent
                    )
                    exit(1)

    def stop(self, jail=None, force=False, ignore_exception=False):
        """Stops the jail."""

        if self.rc or self._all:
            if not jail:
                self.__jail_order__("stop", ignore_exception=ignore_exception)
        else:
            uuid, path = self.__check_jail_existence__()
            ioc_stop.IOCStop(
                uuid, path, silent=self.silent,
                force=force, suppress_exception=ignore_exception
            )

    def update_all(self, pkgs=False):
        """Runs update for all jails"""
        self._all = False
        for jail in self.jails:
            self.jail = jail
            self.update(pkgs)

    def update(self, pkgs=False):
        """Updates a jail to the latest patchset."""
        if self._all:
            self.update_all(pkgs)
            return

        uuid, path = self.__check_jail_existence__()
        conf = ioc_json.IOCJson(
            path, silent=self.silent, stop=True).json_get_value('all')
        freebsd_version = ioc_common.checkoutput(["freebsd-version"])
        status, jid = self.list("jid", uuid=uuid)
        started = False
        _release = conf["release"].rsplit("-", 1)[0]
        release = _release if "-RELEASE" in _release else conf["release"]
        _silent = self.silent
        jail_type = conf["type"]
        updateable = True if jail_type in (
            "jail", "clonejail", "pluginv2") else False

        if updateable:
            date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.snapshot(
                f'ioc_update_{conf["release"]}_{date}'
            )

            if not status:
                self.silent = True
                self.start()
                status, jid = self.list("jid", uuid=uuid)
                started = True
                self.silent = _silent
        elif conf["type"] == "basejail":
            ioc_common.logit(
                {
                    "level":
                    "EXCEPTION",
                    "message":
                    "Please run \"iocage migrate\" before trying"
                    f" to update {uuid}"
                })
        elif conf["type"] == "template":
            ioc_common.logit(
                {
                    "level":
                    "EXCEPTION",
                    "message":
                    "Please convert back to a jail before trying"
                    f" to update {uuid}"
                })
        else:
            ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": f"{conf['type']} is not a supported jail type."
                })

        if "HBSD" in freebsd_version:
            su.Popen(["hbsd-update", "-j", jid]).communicate()

            if started:
                self.silent = True
                self.stop()
                self.silent = _silent
        else:
            if pkgs and not (jail_type in ('plugin', 'pluginv2')):
                # Let's update pkg repos first
                ioc_common.logit({
                    'level': 'INFO',
                    'message': 'Updating pkgs...'
                })
                pkg_update = su.run(
                    ['pkg-static', '-j', jid, 'update', '-q', '-f'],
                    stdout=su.PIPE, stderr=su.STDOUT
                )
                if pkg_update.returncode:
                    ioc_common.logit({
                        'level': 'EXCEPTION',
                        'message': 'Failed to update pkg repositories.'
                    })
                else:
                    ioc_common.logit({
                        'level': 'INFO',
                        'message': 'Updated pkg repositories successfully.'
                    })
                # This will run pkg upgrade now
                ioc_create.IOCCreate(
                    self.jail, '', 0, pkglist=[],
                    silent=True, callback=self.callback
                ).create_install_packages(self.jail, path, repo='')

                ioc_common.logit({
                    'level': 'INFO',
                    'message': 'Upgraded pkgs successfully.'
                })

            if jail_type == "pluginv2" or jail_type == "plugin":
                # TODO: Warn about erasing all pkgs
                ioc_common.logit({
                    'level': 'INFO',
                    'message': 'Updating plugin...'
                })
                ioc_plugin.IOCPlugin(
                    jail=uuid,
                    plugin=conf['plugin_name'],
                    git_repository=conf['plugin_repository'],
                    callback=self.callback
                ).update(jid)
                ioc_common.logit({
                    'level': 'INFO',
                    'message': 'Updated plugin successfully.'
                })

            # Jail updates should always happen
            ioc_common.logit({
                'level': 'INFO',
                'message': 'Updating jail...'
            })

            is_basejail = ioc_common.check_truthy(conf['basejail'])
            params = [] if is_basejail else [True, uuid]
            try:
                ioc_fetch.IOCFetch(
                    release,
                    callback=self.callback
                ).fetch_update(*params)
            finally:
                if not started and jail_type == 'pluginv2':
                    silent = self.silent
                    self.silent = True
                    self.restart()
                    self.silent = silent

            ioc_common.logit({
                'level': 'INFO',
                'message': 'Updated jail successfully.'
            })

            if started:
                self.silent = True
                self.stop()
                self.silent = _silent

            message = f"\n{uuid} updates have been applied successfully."
            ioc_common.logit(
                {
                    "level": "INFO",
                    "message": message
                },
                _callback=self.callback,
                silent=self.silent)

    def upgrade_all(self, release):
        """Runs upgrade for all jails"""
        self._all = False
        for jail in self.jails:
            self.jail = jail
            self.upgrade(release)

    def upgrade(self, release):
        if self._all:
            self.upgrade_all(release)
            return

        if release is not None:
            _release = release.rsplit("-", 1)[0].rsplit("-", 1)[0]
            ioc_common.check_release_newer(_release, major_only=True)

        uuid, path = self.__check_jail_existence__()
        root_path = f"{path}/root"
        status, jid = self.list("jid", uuid=uuid)
        conf = ioc_json.IOCJson(path).json_get_value('all')

        if release is None and conf["type"] != "pluginv2":
            ioc_common.logit({
                "level": "EXCEPTION",
                "message": "Target RELEASE is required to upgrade."
            },
                _callback=self.callback)

        jail_release = conf["release"]

        if conf["type"] != "pluginv2":
            if release in jail_release:
                ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message":
                        f"Jail: {uuid} is already at version {release}!"
                    },
                    _callback=self.callback)

        started = False
        basejail = False
        plugin = False

        if conf["release"] == "EMPTY":
            ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": "Upgrading is not supported for empty jails."
                },
                _callback=self.callback)

        if conf["type"] == "jail":
            if not status:
                ioc_start.IOCStart(uuid, path, silent=True)
                started = True

            if ioc_common.check_truthy(conf['basejail']):
                new_release = ioc_upgrade.IOCUpgrade(
                    release,
                    root_path,
                    callback=self.callback
                ).upgrade_basejail()
                basejail = True
            else:
                new_release = ioc_upgrade.IOCUpgrade(
                    release,
                    root_path,
                    callback=self.callback
                ).upgrade_jail()
        elif conf["type"] == "basejail":
            ioc_common.logit(
                {
                    "level":
                    "EXCEPTION",
                    "message":
                    "Please run \"iocage migrate\" before trying"
                    f" to upgrade {uuid}"
                },
                _callback=self.callback)
        elif conf["type"] == "template":
            ioc_common.logit(
                {
                    "level":
                    "EXCEPTION",
                    "message":
                    "Please convert back to a jail before trying"
                    f" to upgrade {uuid}"
                },
                _callback=self.callback)
        elif conf["type"] == "pluginv2":
            if not status:
                ioc_start.IOCStart(uuid, path, silent=True)
                started = True

            status, jid = self.list('jid', uuid=uuid)
            new_release = ioc_plugin.IOCPlugin(
                jail=uuid,
                plugin=conf['plugin_name'],
                git_repository=conf['plugin_repository'],
                callback=self.callback
            ).upgrade(jid)
            plugin = True
        else:
            ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": f"{conf['type']} is not a supported jail type."
                },
                _callback=self.callback)

        if started:
            _silent = self.silent
            self.silent = True
            self.stop()
            self.silent = _silent

        if basejail:
            _date = datetime.datetime.utcnow().strftime("%F")
            msg = f"""\
\n{uuid} successfully upgraded from {jail_release} to {new_release}!
Please reboot the jail and inspect.
Remove the snapshot: ioc_upgrade_{_date} if everything is OK
"""
        elif plugin:
            msg = f"\n{uuid} successfully upgraded!"
        else:
            msg = f"\n{uuid} successfully upgraded from" \
                f" {jail_release} to {new_release}!"

        ioc_common.logit(
            {
                'level': 'INFO',
                'message': msg
            },
            _callback=self.callback
        )

    def debug(self, directory):
        if directory is None:
            directory = f'{self.iocroot}/debug'

        ioc_debug.IOCDebug(directory).run_debug()

    def snap_remove(self, snapshot):
        """Removes user supplied snapshot from jail"""
        uuid, path = self.__check_jail_existence__()
        conf = ioc_json.IOCJson(path, silent=self.silent).json_get_value('all')

        if ioc_common.check_truthy(conf['template']):
            target = f'{self.pool}/iocage/templates/{uuid}@{snapshot}'
        else:
            target = f'{self.pool}/iocage/jails/{uuid}@{snapshot}'

        # Let's verify target exists and then destroy it, else log it
        snapshot = Snapshot(target)

        if not snapshot:
            ioc_common.logit({
                'level': 'EXCEPTION',
                'message': f'Snapshot: {target} not found!'
            })
        else:
            snapshot.destroy(recursive=True)

            ioc_common.logit(
                {
                    'level': 'INFO',
                    'message': f'Snapshot: {target} destroyed'
                },
                _callback=self.callback, silent=self.silent
            )
