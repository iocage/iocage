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
"""iocage destroy module."""
import json
import os
import subprocess as su

import iocage_lib.ioc_json
import iocage_lib.ioc_stop
import libzfs

from pathlib import Path


class IOCDestroy(iocage_lib.ioc_json.IOCZFS):
    """
    Destroy a jail's datasets and then if they have a RELEASE snapshot,
    destroy that as well.
    """
    def __init__(self, callback=None):
        super().__init__()
        self.pool = iocage_lib.ioc_json.IOCJson().json_get_value('pool')
        self.iocroot = iocage_lib.ioc_json.IOCJson(
            self.pool).json_get_value('iocroot')
        self.callback = callback
        self.path = None
        self.j_conf = None

    def __stop_jails__(self, datasets, path=None, root=False, clean=False):
        if clean:
            jids, _ = su.Popen(["jls", "-n", "name", "jid",
                                "--libxo=json"], stdout=su.PIPE).communicate()
            jids = json.loads(jids)["jail-information"]["jail"]

            for j in jids:
                name = j["name"]
                jid = j["jid"]

                if "ioc-" in name:
                    cmd = ["jail"]
                    jail_conf_file = Path(f"/var/run/jail.{name}.conf")

                    # The is_file checks here are part of the iocage upgrade
                    # path. Users may not have a jail_conf_file yet.
                    if jail_conf_file.is_file():
                        cmd.extend(["-f", f"{jail_conf_file}"])

                    cmd.extend(["-r", jid])

                    su.Popen(cmd, stdout=su.PIPE, stderr=su.PIPE).communicate()

                    # Don't let a failure to unlink the jail conf stop the
                    # destruction process.
                    if jail_conf_file.is_file():
                        try:
                            jail_conf_file.unlink()
                        except OSError:
                            pass

        for dataset in datasets:
            if 'jails' not in dataset:
                continue

            if self.zfs_get_property(dataset, 'type') != 'filesystem':
                continue

            mountpoint = self.zfs_get_property(dataset, 'mountpoint')
            if mountpoint == 'legacy':
                continue

            # This is just to setup a replacement.
            path = path.replace('templates', 'jails')

            try:
                uuid = dataset.partition(path)[2]
                if not uuid:
                    # jails dataset
                    # This will trigger a false IndexError if we don't continue
                    continue
                if uuid.endswith('/root/root'):
                    # They named their jail root...
                    uuid = 'root'
                elif uuid.endswith('/root'):
                    uuid = uuid.rsplit('/root', 1)[0]
            except IndexError:
                # A RELEASE dataset
                return

            # We want the real path now.
            _path = mountpoint.replace('/root', '', 1)

            if (dataset.endswith(uuid) or root) and _path is not None:
                with iocage_lib.ioc_exceptions.ignore_exceptions(
                        BaseException):
                    # Can be missing/corrupt/whatever configuration
                    # Since it's being nuked anyways, we don't care.
                    iocage_lib.ioc_stop.IOCStop(
                        uuid, _path, silent=True, suppress_exception=True
                    )

    def __destroy_leftovers__(self, dataset, clean=False):
        """Removes parent datasets and logs."""
        uuid = dataset.rsplit('/root', 1)[0].rsplit('/')[-1]

        if self.path is not None and self.path.endswith('/root'):
            umount_path = self.path.rsplit('/root', 1)[0]
        else:
            umount_path = self.path

        if self.path == '-' or self.zfs_get_property(
            dataset, 'type'
        ) == 'snapshot':
            # This is either not mounted or doesn't exist anymore,
            # we don't care either way.
            self.path = None

        if self.path is not None:
            try:
                os.remove(f'{self.iocroot}/log/{uuid}-console.log')
            except FileNotFoundError:
                pass

            # Dangling mounts are bad...mmkay?
            for command in [
                ['umount', '-afF', f'{umount_path}/fstab'],
                ['umount', '-f', f'{umount_path}/root/dev/fd'],
                ['umount', '-f', f'{umount_path}/root/dev'],
                ['umount', '-f', f'{umount_path}/root/proc'],
                ['umount', '-f', f'{umount_path}/root/compat/linux/proc']
            ]:
                su.run(command, stderr=su.PIPE)

        if self.j_conf is not None:
            try:
                release = self.j_conf['cloned_release']
            except KeyError:
                # Thick jails
                release = self.j_conf['release']

            release_snap = self.zfs_get_snapshot(
                f'{self.pool}/iocage/releases/{release}/root@{uuid}'
            )

            if release_snap.exists:
                release_snap.delete()
            else:
                try:
                    temp = self.j_conf['source_template']
                    temp_snap = self.zfs_get_snapshot(
                        f'{self.pool}/iocage/templates/{temp}@{uuid}'
                    )

                    if temp_snap.exists:
                        temp_snap.delete()
                except KeyError:
                    # Not all jails have this, using slow way of finding this
                    for dataset in self.iocroot_datasets:
                        if 'templates' in dataset:
                            temp_snap = self.zfs_get_snapshot(
                                f'{dataset}@{uuid}'
                            )

                            if temp_snap.exists:
                                temp_snap.delete()
                                break

    def __destroy_dataset__(self, dataset):
        """Destroys the given datasets and snapshots."""
        self.zfs_destroy_dataset(dataset, recursive=True, force=True)

        if dataset.endswith('jails'):
            # We need to make sure we remove the snapshots from the RELEASES
            # We are purposely not using -R as those will hit templates
            # and we are not using IOCSnapshot for perfomance
            for dataset in self.release_snapshots:
                su.run(
                    [
                        'zfs',
                        'destroy',
                        '-r',
                        f'{self.pool}/iocage/releases@{dataset}'
                    ],
                    stdout=su.PIPE, stderr=su.PIPE
                )
        if 'templates' in dataset:
            if dataset.endswith('/root/root'):
                # They named their jail root...
                uuid = 'root'
            else:
                uuid = dataset.rsplit('/', 1)[1]

            jail_datasets = self.zfs_get_dataset_and_dependents(
                f'{self.pool}/iocage/jails'
            )
            for jail in jail_datasets:
                with iocage_lib.ioc_exceptions.ignore_exceptions(
                        BaseException):
                    j_conf = iocage_lib.ioc_json.IOCJson(
                        self.path, suppress_log=True
                    ).json_get_value('all')

                    source_template = j_conf['source_template']

                    if source_template == uuid:
                        self.__destroy_parse_datasets__(
                            f'{self.pool}/iocage/jails/{jail}',
                            clean=True
                        )

    def __destroy_parse_datasets__(self, path, clean=False, stop=True):
        """
        Parses the datasets before calling __destroy_dataset__ with each
        entry.
        """
        try:
            datasets = self.zfs_get_dataset_and_dependents(path)
        except (Exception, SystemExit):
            # Dataset can't be found, we don't care
            return

        single = True if len(datasets) == 1 else False

        if single:
            # Is actually a single dataset.
            self.__destroy_dataset__(datasets[0])
        else:
            datasets.reverse()

            if "templates" in path or "release" in path:
                # This will tell __stop_jails__ to actually try stopping on
                # a /root
                root = True
            else:
                # Otherwise we only stop when the uuid is the last entry in
                # the jails path.
                root = False

            if stop:
                try:
                    self.__stop_jails__(datasets, path, root, clean=clean)
                except (RuntimeError, FileNotFoundError, SystemExit):
                    # If a bad or missing configuration for a jail, this will
                    # get in the way.
                    pass

            for dataset in datasets:
                try:
                    self.path = self.zfs_get_property(dataset, 'mountpoint')

                    try:
                        self.j_conf = iocage_lib.ioc_json.IOCJson(
                            self.path, suppress_log=True
                        ).json_get_value('all')
                    except BaseException:
                        # Isn't a jail, iocage will throw a variety of
                        # exceptions or SystemExit
                        pass

                    self.__destroy_dataset__(dataset)
                    self.__destroy_leftovers__(dataset, clean=clean)
                except libzfs.ZFSException as err:
                    # This is either not mounted or doesn't exist anymore,
                    # we don't care either way.

                    if err.code == libzfs.Error.NOENT:
                        continue
                    else:
                        raise

    def destroy_jail(self, path, clean=False):
        """
        A convenience wrapper to call __stop_jails__ and
         __destroy_parse_datasets__
        """
        dataset_type, uuid = path.rsplit("/")[-2:]

        if clean:
            self.__destroy_parse_datasets__(path, clean=clean)

            return

        try:
            iocage_lib.ioc_stop.IOCStop(uuid, path, silent=True)
        except (FileNotFoundError, RuntimeError, libzfs.ZFSException,
                SystemExit):
            # Broad exception as we don't care why this failed. iocage
            # may have been killed before configuration could be made,
            # it's meant to be nuked.
            pass

        try:
            self.__destroy_parse_datasets__(
                f"{self.pool}/iocage/{dataset_type}/{uuid}")
        except (libzfs.ZFSException, SystemExit):
            # The dataset doesn't exist, we don't care :)
            pass
