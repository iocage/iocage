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
"""Convert, load or write JSON."""
import collections
import datetime
import fileinput
import ipaddress
import json
import logging
import os
import re
import shutil
import subprocess as su
import sys

import iocage_lib.ioc_common
import iocage_lib.ioc_create
import iocage_lib.ioc_exec
import iocage_lib.ioc_list
import iocage_lib.ioc_stop
import iocage_lib.ioc_exceptions as ioc_exceptions
import libzfs
import netifaces
import random
import pathlib


class JailRuntimeConfiguration(object):
    def __init__(self, jail_name, data=None):
        # If data is provided, we make sure that this object reflects
        # what data holds and not what the conf file already has etc
        self.name = f'ioc-{jail_name}'
        for k in ('data', 'read_data'):
            setattr(self, k, {})

        normalized_data = self.normalize_data(data)
        if normalized_data:
            self.data = normalized_data
        else:
            self.__read_file()
            self.data = self.read_data.copy()

    @property
    def path(self):
        return f'/var/run/jail.{self.name}.conf'

    def set(self, key, value=None):
        if isinstance(value, str):
            value = value.strip()

        self.data[str(key).strip()] = value

    def remove(self, key):
        # Should we care about raising an exception ?
        self.data.pop(key, None)

    def __read_file(self):
        self.read_data = {}

        if not os.path.exists(self.path):
            return

        with open(self.path, 'r') as f:
            content = list(
                filter(bool, map(str.strip, f.readlines()))
            )[1: -1]

        # Let's treat ip4.addr and ip6.addr differently keeping compatibility
        # with current jail.conf files we have introduced
        ip4 = []
        ip6 = []
        for data in content:
            if '=' in data:
                k, v = data.split('=', 1)
                k = k.strip()
                v = v.replace(';', '').strip()

                if 'ip4.addr' in k:
                    ip4.append(v)
                elif 'ip6.addr' in k:
                    ip6.append(v)
                else:
                    self.read_data[k] = v
            else:
                # None is special for self.data value as it indicates that
                # the key is a boolean one, we will write a value of empty
                # string as a key,value pair and it will NOT be treated as
                # a boolean value
                self.read_data[data.replace(';', '').strip()] = None

        if ip4:
            self.read_data['ip4.addr'] = ','.join(ip4)
        if ip6:
            self.read_data['ip6.addr'] = ','.join(ip6)

    def sync_changes(self):
        # We are going to write out the changes which are present in self.data
        self.__read_file()
        if len(
            set(self.data.items()) ^ set((self.read_data or {}).items())
        ) > 0:
            self.__write_file()

    def normalize_data(self, data):
        normalized_data = {}
        if data:
            assert isinstance(data, list)
        else:
            return

        for line in data:
            if '=' in line:
                k, v = line.split('=', 1)
                k = k.strip()
                v = v.strip()
                if k == 'name':
                    continue
                if k in ('ip4.addr', 'ip6.addr'):
                    v = ','.join(map(str.strip, v.split(',')))
                normalized_data[k] = v
            else:
                # This is a boolean value
                normalized_data[line] = None
        return normalized_data

    def __write_file(self):
        write_data = []
        for key, value in self.data.items():
            if key in ('ip4.addr', 'ip6.addr'):
                for ips in value.split(','):
                    write_data.append(f'{key} += "{ips.strip()}";')
            elif value is None:
                write_data.append(f'{key};')
            else:
                write_data.append(f'{key} = "{value}";')

        config_params = '\n\t'.join(write_data)
        with open(self.path, 'w') as f:
            f.write(
                f'{self.name} {{\n\t{config_params}\n}}\n'
            )


class IOCCpuset(object):

    def __init__(self, name):
        self.jail_name = f'ioc-{name}'

    def set_cpuset(self, value=None):
        if not value:
            value = 'all'

        failed = False
        try:
            iocage_lib.ioc_exec.SilentExec(
                ['cpuset', '-l', value, '-j', self.jail_name],
                None, unjailed=True, decode=True
            )
        except iocage_lib.ioc_exceptions.CommandFailed:
            failed = True
        finally:
            return failed

    @staticmethod
    def retrieve_cpu_sets():
        cpu_sets = -2
        try:
            output = iocage_lib.ioc_exec.SilentExec(
                ['cpuset', '-g', '-s', '0'],
                None, unjailed=True, decode=True
            )
        except iocage_lib.ioc_exceptions.CommandFailed:
            pass
        else:
            result = re.findall(
                r'.*mask:.*(\d+)$',
                output.stdout.split('\n')[0]
            )
            if result:
                cpu_sets = int(result[0])
        finally:
            return cpu_sets

    @staticmethod
    def validate_cpuset_prop(value, raise_error=True):
        failed = False
        cpu_sets = IOCCpuset.retrieve_cpu_sets() + 1
        cpu_set_value_err = False

        if not any(
            cond for cond in (
                re.findall(
                    r'^(\d+(,\d+)*)$',
                    value
                ),
                value in ('off', 'all'),
                re.findall(
                    r'^(\d+-\d+)$',
                    value
                )
            )
        ):
            failed = True
        elif not any(
            cond for cond in (
                re.findall(
                    fr'^(?!.*(\b\d+\b).*\b\1\b)'
                    fr'((?:{"|".join(map(str, range(cpu_sets)))})'
                    fr'(,(?:{"|".join(map(str, range(cpu_sets)))}))*)?$',
                    value
                ),
                value in ('off', 'all'),
                re.findall(
                    fr'^(?:{"|".join(map(str, range(cpu_sets - 1)))})-'
                    fr'(?:{"|".join(map(str, range(cpu_sets)))})$',
                    value
                ) and int(value.split('-')[0]) < int(value.split('-')[1])
            )
        ):
            cpu_set_value_err = True

        if (failed or cpu_set_value_err) and raise_error:
            message = 'Please specify a valid format for cpuset ' \
                      'value.\nFollowing 4 formats are supported:\n' \
                      '1) comma delimited string i.e 0,1,2,3\n' \
                      '2) a range of values i.e 0-2\n' \
                      '3) "all" - all would mean using all cores\n' \
                      '4) off'
            if cpu_set_value_err:
                message = 'Please make sure the provided cpus fall in the ' \
                          'correct range of cpus.\nFor this system it is: ' \
                          f'{",".join(map(str, range(cpu_sets)))}'
            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': message
                }
            )
        else:
            return failed | cpu_set_value_err


class IOCRCTL(object):

    types = {
        'cputime', 'datasize', 'stacksize', 'coredumpsize',
        'memoryuse', 'memorylocked', 'maxproc', 'openfiles',
        'vmemoryuse', 'pseudoterminals', 'swapuse', 'nthr',
        'msgqqueued', 'msgqsize', 'nmsgq', 'nsem', 'nsemop',
        'nshm', 'shmsize', 'wallclock', 'pcpu', 'readbps',
        'writebps', 'readiops', 'writeiops'
    }

    def __init__(self, name):
        self.jail_name = f'ioc-{name}'

    def set_rctl_rules(self, props):
        # We expect props to be a list of tuples or a tuple
        if not isinstance(props, list):
            props = [props]

        failed = set()
        for key, value in props:
            try:
                iocage_lib.ioc_exec.SilentExec(
                    [
                        'rctl', '-a',
                        f'jail:{self.jail_name}:{key}:{value}'
                    ],
                    None, unjailed=True, decode=True
                )
            except ioc_exceptions.CommandFailed:
                failed.add(key)

        return failed

    def remove_rctl_rules(self, props=None):
        if not props:
            props = ['']

        failed = set()
        for prop in props:
            try:
                iocage_lib.ioc_exec.SilentExec(
                    ['rctl', '-r', f'jail:{self.jail_name}:{prop}'],
                    None, unjailed=True, decode=True
                )
            except ioc_exceptions.CommandFailed:
                failed.add(prop if prop else 'ALL')

        return failed

    def rctl_rules_exist(self, prop=None):
        rctl_enabled = False
        try:
            output = iocage_lib.ioc_exec.SilentExec(
                ['rctl'],
                None, unjailed=True, decode=True
            )
        except iocage_lib.ioc_exceptions.CommandFailed:
            pass
        else:
            if f'jail:{self.jail_name}{"" if not prop else f":{prop}"}' \
                    in output.stdout:
                rctl_enabled = True
        finally:
            return rctl_enabled

    @staticmethod
    def validate_rctl_tunable():
        rctl_enable = False
        try:
            output = iocage_lib.ioc_exec.SilentExec(
                ['sysctl', 'kern.racct.enable'],
                None, unjailed=True, decode=True
            )
        except ioc_exceptions.CommandFailed:
            pass
        else:
            if re.findall(r'.*:.*1', output.stdout):
                rctl_enable = True
        finally:
            if not rctl_enable:
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'EXCEPTION',
                        'message': 'Please set kern.racct.enable -> 1 '
                                   'to set rctl rules'
                    }
                )

    @staticmethod
    def validate_rctl_props(prop, value):
        if prop in IOCRCTL.types and value != 'off':
            # prop can have the following values
            # off
            # action=amount

            IOCRCTL.validate_rctl_tunable()

            if not re.findall(
                r'(?:deny|log|devctl|sig\w*|throttle)=\d+(?:b|k|m|g|t|p|)$',
                value
            ):
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'EXCEPTION',
                        'message': 'Please supply a valid value for rctl '
                        f'property {prop} following format '
                        '"action=amount" or "off" where valid '
                        'actions are "deny|log|devctl|sig*|throttle"'
                    }
                )
            else:
                if re.findall(
                    r'(?:deny|log|devctl|sig\w*|throttle)=\d+(?:b|k|m|g|t|p)$',
                    value
                ) and prop in (
                    'cputime', 'maxproc', 'openfiles', 'pseudoterminals',
                    'nthr', 'msgqqueued', 'nmsgq', 'nsem', 'nsemop', 'nshm',
                    'wallclock', 'pcpu'
                ):
                    iocage_lib.ioc_common.logit(
                        {
                            'level': 'EXCEPTION',
                            'message': 'b, k, m, g, t, p suffixes are not '
                                       f'allowed with {prop}'
                        }
                    )
                action = value.split('=')[0]
                if action == 'deny' and prop in (
                    'cputime', 'wallclock', 'readbps', 'writebps',
                    'readiops', 'writeiops'
                ):
                    iocage_lib.ioc_common.logit(
                        {
                            'level': 'EXCEPTION',
                            'message': 'Deny action is not supported with '
                            f'prop {prop}'
                        }
                    )

                if action == 'throttle' and prop not in (
                    'readbps', 'writebps', 'readiops', 'writeiops'
                ):
                    iocage_lib.ioc_common.logit(
                        {
                            'level': 'EXCEPTION',
                            'message': 'Throttle action is only supported with'
                            ' properties '
                            '"readbps, writebps, readiops, writeiops"'
                        }
                    )

                if prop == 'pcpu' and int(value.split('=')[1]) > 100:
                    iocage_lib.ioc_common.logit(
                        {
                            'level': 'EXCEPTION',
                            'message': 'pcpu property requires a valid '
                                       'percentage'
                        }
                    )


class IOCSnapshot(object):
    # FIXME: Please move me to another file and let's see how we can build
    # our hierarchy for the whole ZFS related section
    # TODO: Update this object via some fashion(after delete, so forth)
    def __init__(self, snap_id):
        self.data = None
        self.snap_id = snap_id

        self.attr_list = [
            'name', 'used', 'available', 'referred', 'mountpoint'
        ]
        for attr in self.attr_list:
            setattr(self, attr, None)

        self.normalize_data()

    @property
    def exists(self):
        return bool(self.data is not None and self.data)

    @property
    def raw_data(self):
        with ioc_exceptions.ignore_exceptions(su.CalledProcessError):
            return su.run(
                ['zfs', 'list', '-Ht', 'snapshot', self.snap_id or self.name],
                stdout=su.PIPE, stderr=su.PIPE
            ).stdout.decode()

    def normalize_data(self):
        # Expected format
        # ['NAME', 'USED', 'AVAIL', 'REFER', 'MOUNTPOINT']
        if not self.data:
            self.data = self.raw_data

        self.__dict__.update({
            k: v for k, v in zip(self.attr_list, self.data.split())
        })

    def delete(self, recursive=True):
        with ioc_exceptions.ignore_exceptions(
            su.CalledProcessError
        ):
            return su.run(
                ['zfs', 'destroy', '-r' if recursive else '', '-f', self.name],
                stdout=su.PIPE, stderr=su.PIPE
            ).returncode == 0

    def __eq__(self, other):
        return self.name == other.name

    def __bool__(self):
        return self.exists is True

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return self.name


class IOCZFS(object):
    # TODO: We should use a context manager for libzfs
    def __init__(self, callback=None):
        self.zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")
        self.callback = callback

    @property
    def iocroot_path(self):
        # For now we assume iocroot is set, however moving on we need to think
        # how best to structure this
        # We should give thought to how we handle
        for pool in self.pools:
            if self.zfs_get_property(
                pool, 'org.freebsd.ioc:active'
            ) == 'yes':
                return self.zfs_get_property(
                    os.path.join(pool, 'iocage'),
                    'mountpoint'
                )

    @property
    def pools(self):
        # Returns list of pools. In case of failure, an empty list
        with ioc_exceptions.ignore_exceptions(
            su.CalledProcessError
        ):
            pools = su.run(
                [
                    'zpool', 'list', '-H',
                ],
                stdout=su.PIPE, stderr=su.PIPE
            ).stdout.decode().split('\n')
            return [p.split()[0] for p in pools if p]

        return []

    @property
    def iocroot_datasets(self):
        return self.zfs_get_dataset_and_dependents(self.iocroot_path)
        # Returns a list of all datasets

    @property
    def release_snapshots(self):
        # Returns all jail snapshots on each RELEASE dataset
        rel_dir = pathlib.Path(f'{self.iocroot_path}/releases')
        snaps = {}

        # Quicker than asking zfs and parsing
        for snap in rel_dir.glob('**/root/.zfs/snapshot/*'):
            snaps[snap.name] = str(snap).rsplit('/.zfs', 1)[0]

        return snaps

    def _zfs_get_properties(self, identifier):
        p_dict = {}

        props = su.run(
            [
                'zfs',
                'get',
                '-pHo',
                'property, value',
                'all',
                identifier
            ], stdout=su.PIPE, stderr=su.PIPE
        ).stdout.decode().splitlines()

        for prop in props:
            try:
                p, v = prop.split()
            except ValueError:
                p, v = prop.strip(), '-'

            p_dict[p] = v

        return p_dict

    def zfs_get_property(self, identifier, key):
        with ioc_exceptions.ignore_exceptions(Exception):
            if key == 'mountpoint':
                mountpoint = su.run(
                    [
                        'zfs',
                        'get',
                        '-pHo',
                        'value',
                        key,
                        identifier
                    ], stdout=su.PIPE, stderr=su.PIPE
                ).stdout.decode().rstrip()

                return mountpoint

            return self._zfs_get_properties(identifier)[key]

        return '-'

    def zfs_set_property(self, identifier, key, value):
        su.run(
            [
                'zfs', 'set', f'{key}={value}', identifier
            ], stdout=su.PIPE, stderr=su.PIPE
        )

    def zfs_get_dataset_name(self, name):
        with ioc_exceptions.ignore_exceptions(su.CalledProcessError):
            return su.run(
                ['zfs', 'get', '-pHo', 'name', 'mountpoint', name],
                stdout=su.PIPE, stderr=su.PIPE
            ).stdout.decode().rstrip()

    def zfs_get_snapshot(self, snap_id):
        # Let's return snapshot object from which additional information
        # can be derived wrt snap_id in question
        # Snap_id expected value - vol/iocage/jails/jail1@snaptest
        return IOCSnapshot(snap_id)

    def zfs_destroy_dataset(self, identifier, recursive=False, force=False):
        cmd = ['zfs', 'destroy']

        if recursive:
            cmd += ['-r']

        if force:
            cmd += ['-Rf']

        try:
            su.run(
                cmd + [identifier], check=True, stdout=su.PIPE, stderr=su.PIPE
            )
        except su.CalledProcessError as e:
            if force:
                return

            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': f'Destroying {identifier} failed!\n'
                               f'Reason: {e.stderr.decode()}'
                },
                _callback=self.callback,
                exception=ioc_exceptions.CommandFailed
            )

    def zfs_get_dataset_and_dependents(self, identifier):
        try:
            datasets = list(su.run(
                ['zfs', 'list', '-rHo', 'name', identifier],
                check=True, stdout=su.PIPE, stderr=su.PIPE
            ).stdout.decode().split())
        except su.CalledProcessError as e:
            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': 'Getting dataset and dependents for '
                               f'{identifier} failed!\n'
                               f'Reason: {e.stderr.decode()}'
                },
                _callback=self.callback,
                exception=ioc_exceptions.CommandFailed
            )

        return datasets


class Resource(IOCZFS):
    # TODO: Let's also rethink how best we should handle this in the future
    def __init__(self, name):
        super().__init__()
        self.name = name

    def __bool__(self):
        return self.exists

    def __hash__(self):
        return hash(self.path)

    def __repr__(self):
        return str(self.name)

    def __str__(self):
        return str(self.name)

    def __eq__(self, other):
        return other.path == self.path

    @property
    def path(self):
        raise NotImplementedError

    @property
    def exists(self):
        return os.path.exists(self.path)


class Release(Resource):
    def __init__(self, name):
        # We can expect the name to be either a full path or just the name of
        # the release, let's normalize it
        # a name can't contain "/". If it's a path, we can make a split and
        # use the last name
        super().__init__(name if '/' not in name else name.rsplit('/', 1)[1])

    @property
    def path(self):
        return os.path.join(
            self.iocroot_path, 'releases', self.name
        )


class IOCConfiguration(IOCZFS):
    def __init__(self, location, checking_datasets, silent, callback):
        super().__init__(callback)
        self.location = location
        self.silent = silent
        self.callback = callback
        self.json_version = self.get_version()
        self.mac_prefix = self.get_mac_prefix()
        self.pool, self.iocroot = self.get_pool_and_iocroot()

        if not checking_datasets:
            self.default_config = self.check_default_config()

    @staticmethod
    def get_version():
        """Sets the iocage configuration version."""
        version = '23'

        return version

    def get_pool_and_iocroot(self):
        """For internal getting of pool and iocroot."""
        def get_pool():
            old = False
            zpools = list(map(lambda x: x.name, list(self.zfs.pools)))

            match = 0

            for pool in zpools:
                prop_ioc_active = self.zfs_get_property(
                    pool, "org.freebsd.ioc:active")
                prop_comment = self.zfs_get_property(pool, "comment")

                if prop_ioc_active == "yes":
                    _dataset = pool
                    match += 1
                elif prop_comment == "iocage":
                    _dataset = pool
                    match += 1
                    old = True

            if match == 1:
                if old:
                    self.activate_pool(_dataset)

                return _dataset

            elif match >= 2:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "ERROR",
                        "message": "Pools:"
                    },
                    _callback=self.callback,
                    silent=self.silent)

                for zpool in zpools:
                    iocage_lib.ioc_common.logit(
                        {
                            "level": "ERROR",
                            "message": f"  {zpool}"
                        },
                        _callback=self.callback,
                        silent=self.silent)
                raise RuntimeError(f"You have {match} pools marked active"
                                   " for iocage usage.\n Run \"iocage"
                                   f" activate ZPOOL\" on the preferred"
                                   " pool.\n")
            else:
                if len(sys.argv) >= 2 and "activate" in sys.argv[1:]:
                    pass
                else:
                    # We use the first zpool the user has, they are free to
                    # change it.
                    try:
                        zpool = zpools[0]
                    except IndexError:
                        iocage_lib.ioc_common.logit(
                            {
                                'level': 'EXCEPTION',
                                'message': 'No zpools found! Please create one'
                                ' before using iocage.'
                            },
                            _callback=self.callback,
                            silent=self.silent,
                            exception=ioc_exceptions.PoolNotActivated)

                    if os.geteuid() != 0:
                        iocage_lib.ioc_common.logit(
                            {
                                'level': 'EXCEPTION',
                                'message': 'Run as root to automatically'
                                ' activate the first zpool!'
                            },
                            _callback=self.callback,
                            silent=self.silent,
                            exception=ioc_exceptions.PoolNotActivated)

                    iocage_skip = os.environ.get("IOCAGE_SKIP", "FALSE")
                    if iocage_skip == "TRUE":
                        iocage_lib.ioc_common.logit(
                            {
                                'level': 'EXCEPTION',
                                'message': 'IOCAGE_SKIP is TRUE or an RC'
                                ' operation, not activating a pool.\nPlease'
                                ' manually issue iocage activate POOL'
                            },
                            _callback=self.callback,
                            silent=self.silent,
                            exception=ioc_exceptions.PoolNotActivated)

                    if zpool == "freenas-boot":
                        try:
                            zpool = zpools[1]
                        except IndexError:
                            iocage_lib.ioc_common.logit(
                                {
                                    'level': 'EXCEPTION',
                                    'message': 'Please specify a pool to'
                                    ' activate with iocage activate POOL'
                                },
                                _callback=self.callback,
                                silent=self.silent,
                                exception=ioc_exceptions.PoolNotActivated)

                    iocage_lib.ioc_common.logit(
                        {
                            "level":
                            "INFO",
                            "message":
                            f"Setting up zpool [{zpool}] for"
                            " iocage usage\nIf you wish to change"
                            " please use \"iocage activate\""
                        },
                        _callback=self.callback,
                        silent=self.silent)

                    self.zfs_set_property(zpool, "org.freebsd.ioc:active",
                                          "yes")

                    return zpool

        pool = get_pool()

        def get_iocroot():
            try:
                loc = f"{pool}/iocage"
                mount = self.zfs_get_property(loc, "mountpoint")
            except Exception:
                raise RuntimeError(f"{pool} not found!")

            if mount != "none":
                return mount
            else:
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'EXCEPTION',
                        'message': f'Please set a mountpoint on {loc}'
                    },
                    _callback=self.callback,
                    silent=self.silent)

        return pool, get_iocroot()

    @staticmethod
    def get_mac_prefix():
        try:
            default_gw = netifaces.gateways()['default'][netifaces.AF_INET][1]
            default_mac = netifaces.ifaddresses(default_gw)[netifaces.AF_LINK]

            # Use the hosts prefix to start generation from.
            # Helps avoid clashes with other systems in the network
            mac_prefix = default_mac[0]['addr'].replace(':', '')[:6]

            return mac_prefix
        except KeyError:
            # They don't have a default gateway, opting for generation of mac
            mac = random.randint(0x00, 0xfffff)

            return f'{mac:06x}'

    def json_write(self, data, _file="/config.json", defaults=False):
        """Write a JSON file at the location given with supplied data."""
        # Templates need to be set r/w and then back to r/o
        try:
            template = iocage_lib.ioc_common.check_truthy(data['template'])
            jail_dataset = self.zfs.get_dataset_by_path(self.location).name \
                if template else None
        except KeyError:
            # Not a template, it would exist in the configuration otherwise
            template = False

        # _file is a full path when creating defaults
        write_location = f'{self.location}{_file}' if not defaults else _file

        if template:
            try:
                su.check_call(['zfs', 'set', 'readonly=off', jail_dataset])
            except su.CalledProcessError:
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'EXCEPTION',
                        'message': 'Setting template to read/write failed!'
                    },
                    _callback=self.callback,
                    exception=ioc_exceptions.CommandFailed
                )

        try:
            with iocage_lib.ioc_common.open_atomic(write_location, 'w') as out:
                json.dump(data, out, sort_keys=True, indent=4,
                          ensure_ascii=False)
        except Exception:
            raise FileNotFoundError(write_location)

        if template:
            try:
                su.check_call(['zfs', 'set', 'readonly=on', jail_dataset])
            except su.CalledProcessError:
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'EXCEPTION',
                        'message': 'Setting template to readonly failed!'
                    },
                    _callback=self.callback,
                    exception=ioc_exceptions.CommandFailed
                )

    def fix_properties(self, conf):
        """
        Takes a conf file and makes sure any property that has a bad value
        that was previously allowed is fixed to the correct equivalent, but
        aren't a CONFIG_VERSION bump

        Returns a bool if it updated anything and it needs writing
        """
        original_conf = conf.copy()

        if conf.get('ip4') == 'none':
            conf['ip4'] = 'disable'

        if conf.get('ip6') == 'none':
            conf['ip6'] = 'disable'

        for p, v in conf.items():
            # We want these to rest on disk as 1/0
            if p in self.truthy_props:
                conf[p] = 1 if iocage_lib.ioc_common.check_truthy(v) else 0

        return True if original_conf != conf else False

    def check_config(self, conf, default=False):
        """
        Takes JSON as input and checks to see what is missing and adds the
        new keys to the defaults with their default values if missing.
        """
        iocage_conf_version = self.json_version
        current_conf_version = conf.get('CONFIG_VERSION', None)
        thickconfig = conf.get('CONFIG_TYPE', 'THIN')

        if current_conf_version == iocage_conf_version:
            return conf, False

        # New style thin configuration jails won't have this. Only their
        # defaults will
        if current_conf_version is None and thickconfig != 'THICK':
            return conf, False

        if os.geteuid() != 0:
            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': 'You need to be root to convert the'
                               ' configurations to the new format!',
                    'force_raise': True
                },
                _callback=self.callback,
                silent=self.silent,
                exception=ioc_exceptions.CommandNeedsRoot)

        if not default:
            jail_conf = self.check_jail_config(conf)

        conf['CONFIG_VERSION'] = iocage_conf_version

        # Version 2 keys
        if not conf.get('sysvmsg'):
            conf['sysvmsg'] = 'new'
        if not conf.get('sysvsem'):
            conf['sysvsem'] = 'new'
        if not conf.get('sysvshm'):
            conf['sysvshm'] = 'new'

        # Version 4 keys
        if not conf.get('basejail'):
            conf['basejail'] = 0

        # Version 5 keys
        if not conf.get('comment'):
            conf['comment'] = 'none'

        # Version 6 keys
        if not conf.get('host_time'):
            conf['host_time'] = 1

        # Version 7 keys
        if not conf.get('depends'):
            conf['depends'] = 'none'

        # Version 9 keys
        if not conf.get('dhcp'):
            conf['dhcp'] = 0
        if not conf.get('bpf'):
            conf['bpf'] = 0

        # Version 10 keys
        if not conf.get('vnet_interfaces'):
            conf['vnet_interfaces'] = 'none'

        # Version 11 keys
        if not conf.get('hostid_strict_check'):
            conf['hostid_strict_check'] = 0

        # Version 12 keys
        if not conf.get('allow_mlock'):
            conf['allow_mlock'] = 0

        # Version 13 keys
        if not conf.get('vnet_default_interface'):
            conf['vnet_default_interface'] = 'auto'
        else:
            # Catch all users migrating from old prop value of none, which
            # meant auto
            if current_conf_version in ('12', '13') \
                    and conf['vnet_default_interface'] == 'none':
                conf['vnet_default_interface'] = 'auto'

        # Version 14 keys
        if not conf.get('allow_tun'):
            conf['allow_tun'] = 0

        # Version 15 keys
        if not conf.get('allow_mount_fusefs'):
            conf['allow_mount_fusefs'] = 0

        # Version 16 keys
        if not conf.get('rtsold'):
            conf['rtsold'] = 0

        # Version 17 keys
        if not conf.get('allow_vmm'):
            conf['allow_vmm'] = 0

        # Version 18 keys
        if not conf.get('ip_hostname'):
            conf['ip_hostname'] = 0

        # Version 19 keys
        # RCTL Support added
        conf.update(
            {k: 'off' for k in IOCRCTL.types if not conf.get(k)}
        )

        # Version 20 keys
        if not conf.get('exec_created'):
            conf['exec_created'] = '/usr/bin/true'

        # Version 21 keys
        if not conf.get('assign_localhost'):
            conf['assign_localhost'] = 0

        # Version 22 keys
        if not conf.get('localhost_ip'):
            conf['localhost_ip'] = 'none'

        # Version 23 keys
        if not conf.get('nat'):
            conf['nat'] = 0
        if not conf.get('nat_prefix'):
            conf['nat_prefix'] = '172.16'
        if not conf.get('nat_interface'):
            conf['nat_interface'] = 'none'
        if not conf.get('nat_backend'):
            conf['nat_backend'] = 'ipfw'
        if not conf.get('nat_forwards'):
            conf['nat_forwards'] = 'none'

        if not default:
            conf.update(jail_conf)

        return conf, True

    def check_jail_config(self, conf):
        """
        Checks the jails configuration and migrates anything needed
        """
        release = conf.get('release', None)
        template = conf.get('template', 0)
        renamed = False

        if release is None:
            err_name = self.location.rsplit('/', 1)[-1]
            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': f'{err_name} has a corrupt configuration,'
                               ' please destroy the jail.'
                },
                _callback=self.callback,
                silent=self.silent)

        release = release.rsplit('-p', 1)[0]
        cloned_release = conf.get('cloned_release', 'LEGACY_JAIL')

        freebsd_version = pathlib.Path(
            f'{self.iocroot}/releases/{release}/root/bin/freebsd-version'
        )
        if not freebsd_version.is_file():
            try:
                if iocage_lib.ioc_common.check_truthy(template):
                    freebsd_version = pathlib.Path(
                        f'{self.iocroot}/templates/'
                        f"{conf['host_hostuuid']}/root/bin/freebsd-version"
                    )
                else:
                    temp_uuid = self.location.rsplit('/', 1)[-1]
                    freebsd_version = pathlib.Path(
                        f'{self.iocroot}/jails/{temp_uuid}/root/bin/'
                        'freebsd-version'
                    )
                if not freebsd_version.is_file():
                    iocage_lib.ioc_common.logit(
                        {
                            'level': 'EXCEPTION',
                            'message': 'freebsd-version could not be found at'
                            f' {freebsd_version}'
                        }
                    )
            except KeyError:
                # At this point it should be a real misconfigured jail
                uuid = self.location.rsplit('/', 1)[-1]
                raise RuntimeError('Configuration is missing!'
                                   f' Please destroy {uuid} and recreate'
                                   ' it.')

        if release[:4].endswith('-'):
            # 9.3-RELEASE and under don't actually have this binary.
            release = conf['release']
        elif release == 'EMPTY':
            pass
        else:
            try:
                with open(
                    freebsd_version, mode='r', encoding='utf-8'
                ) as r:
                    for line in r:
                        if line.startswith('USERLAND_VERSION'):
                            release = line.rstrip().partition('=')[2]
                            release = release.strip("'\"")
            except Exception as e:
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'EXCEPTION',
                        'message': 'Exception:'
                        f" '{e.__class__.__name__}:{str(e)}' occured\n"
                        f"Loading {uuid}'s configuration failed"
                    }
                )

            cloned_release = conf['release']

        # Set all Version 3 keys
        conf['release'] = release
        conf['cloned_release'] = cloned_release

        # Version 8 migration from uuid to tag named dataset
        try:
            tag = conf['tag']
            uuid = conf['host_hostuuid']

            try:
                state = iocage_lib.ioc_common.checkoutput(
                    ['jls', '-j', f'ioc-{uuid.replace(".", "_")}'],
                    stderr=su.PIPE).split()[5]
            except su.CalledProcessError:
                state = False

            if tag != uuid:
                if not self.force:
                    iocage_lib.ioc_common.logit(
                        {
                            'level': 'EXCEPTION',
                            'message':
                            'A renaming operation is required to continue.\n'
                            f'Please run iocage -f {sys.argv[-1]} as root.'
                        },
                        _callback=self.callback,
                        silent=self.silent)

                conf, rtrn, date = self.json_migrate_uuid_to_tag(
                    uuid, tag, state, conf)

                conf['jail_zfs_dataset'] = f'iocage/jails/{tag}/data'

                if not date:
                    # The jail's tag was not a date, so it was renamed. Fix
                    # fstab

                    for line in fileinput.input(
                            f'{self.iocroot}/jails/{tag}/fstab', inplace=1):
                        print(line.replace(uuid, tag).rstrip())

                    renamed = True

                if rtrn:
                    # They want to stop the jail, not attempt to migrate before

                    return conf

        except KeyError:
            # New jail creation
            pass

        try:
            if not renamed:
                self.json_write(conf)
        except FileNotFoundError:
            # Dataset was renamed.
            self.location = f'{self.iocroot}/jails/{tag}'

            self.json_write(conf)
            messages = collections.OrderedDict(
                [('1-NOTICE', '*' * 80),
                 ('2-WARNING', f'Jail: {uuid} was renamed to {tag}'),
                 ('3-NOTICE', f'{"*" * 80}\n'),
                 ('4-EXCEPTION', 'Please issue your command again.')]
            )

            for level, msg in messages.items():
                level = level.partition('-')[2]

                iocage_lib.ioc_common.logit(
                    {
                        'level': level,
                        'message': msg
                    },
                    _callback=self.callback,
                    silent=self.silent)

        # The above doesn't get triggered with legacy short UUIDs
        if renamed:
            self.location = f'{self.iocroot}/jails/{tag}'

            self.json_write(conf)

            messages = collections.OrderedDict(
                [('1-NOTICE', '*' * 80),
                 ('2-WARNING', f'Jail: {uuid} was renamed to {tag}'),
                 ('3-NOTICE', f'{"*" * 80}\n'),
                 ('4-EXCEPTION', 'Please issue your command again.')]
            )

            for level, msg in messages.items():
                level = level.partition('-')[2]

                iocage_lib.ioc_common.logit(
                    {
                        'level': level,
                        'message': msg
                    },
                    _callback=self.callback,
                    silent=self.silent)
        return conf

    def check_default_config(self):
        """This sets up the default configuration for jails."""
        default_json_location = f'{self.iocroot}/defaults.json'
        write = True  # Write the defaults file
        fix_write = False

        try:
            with open('/etc/hostid', 'r') as _file:
                hostid = _file.read().strip()
        except Exception:
            hostid = None

        default_props = {
            'CONFIG_VERSION': self.json_version,
            'interfaces': 'vnet0:bridge0',
            'host_domainname': 'none',
            'exec_fib': '0',
            'ip4_addr': 'none',
            'ip4_saddrsel': '1',
            'ip4': 'new',
            'ip6_addr': 'none',
            'ip6_saddrsel': '1',
            'ip6': 'new',
            'defaultrouter': 'none',
            'defaultrouter6': 'none',
            'resolver': '/etc/resolv.conf',
            'mac_prefix': self.mac_prefix,
            'vnet0_mac': 'none',
            'vnet1_mac': 'none',
            'vnet2_mac': 'none',
            'vnet3_mac': 'none',
            'vnet_default_interface': 'auto',
            'devfs_ruleset': '4',
            'exec_start': '/bin/sh /etc/rc',
            'exec_stop': '/bin/sh /etc/rc.shutdown',
            'exec_prestart': '/usr/bin/true',
            'exec_poststart': '/usr/bin/true',
            'exec_prestop': '/usr/bin/true',
            'exec_poststop': '/usr/bin/true',
            'exec_created': '/usr/bin/true',
            'exec_clean': 1,
            'exec_timeout': '60',
            'stop_timeout': '30',
            'exec_jail_user': 'root',
            'exec_system_jail_user': '0',
            'exec_system_user': 'root',
            'mount_devfs': 1,
            'mount_fdescfs': 1,
            'enforce_statfs': '2',
            'children_max': '0',
            'login_flags': '-f root',
            'securelevel': '2',
            'sysvmsg': 'new',
            'sysvsem': 'new',
            'sysvshm': 'new',
            'allow_set_hostname': 1,
            'allow_sysvipc': 0,
            'allow_raw_sockets': 0,
            'allow_chflags': 0,
            'allow_mlock': 0,
            'allow_mount': 0,
            'allow_mount_devfs': 0,
            'allow_mount_fusefs': 0,
            'allow_mount_nullfs': 0,
            'allow_mount_procfs': 0,
            'allow_mount_tmpfs': 0,
            'allow_mount_zfs': 0,
            'allow_quotas': 0,
            'allow_socket_af': 0,
            'allow_tun': 0,
            'allow_vmm': 0,
            'cpuset': 'off',
            'rlimits': 'off',
            'memoryuse': 'off',
            'memorylocked': 'off',
            'vmemoryuse': 'off',
            'maxproc': 'off',
            'cputime': 'off',
            'pcpu': 'off',
            'datasize': 'off',
            'stacksize': 'off',
            'coredumpsize': 'off',
            'openfiles': 'off',
            'pseudoterminals': 'off',
            'swapuse': 'off',
            'nthr': 'off',
            'msgqqueued': 'off',
            'msgqsize': 'off',
            'nmsgq': 'off',
            'nsem': 'off',
            'nsemop': 'off',
            'nshm': 'off',
            'shmsize': 'off',
            'wallclock': 'off',
            'readbps': 'off',
            'writebps': 'off',
            'readiops': 'off',
            'writeiops': 'off',
            'type': 'jail',
            'bpf': 0,
            'dhcp': 0,
            'boot': 0,
            'notes': 'none',
            'owner': 'root',
            'priority': '99',
            'last_started': 'none',
            'template': 0,
            'hostid': hostid,
            'hostid_strict_check': 0,
            'jail_zfs': 0,
            'jail_zfs_mountpoint': 'none',
            'mount_procfs': 0,
            'mount_linprocfs': 0,
            'count': '1',
            'vnet': 0,
            'basejail': 0,
            'comment': 'none',
            'host_time': 1,
            'sync_state': 'none',
            'sync_target': 'none',
            'sync_tgt_zpool': 'none',
            'compression': 'lz4',
            'origin': 'readonly',
            'quota': 'none',
            'mountpoint': 'readonly',
            'compressratio': 'readonly',
            'available': 'readonly',
            'used': 'readonly',
            'dedup': 'off',
            'reservation': 'none',
            'depends': 'none',
            'vnet_interfaces': 'none',
            'rtsold': 0,
            'ip_hostname': 0,
            'assign_localhost': 0,
            'localhost_ip': 'none',
            'nat': 0,
            'nat_prefix': '172.16',
            'nat_interface': 'none',
            'nat_backend': 'ipfw',
            'nat_forwards': 'none'
        }

        try:
            with open(default_json_location, 'r') as default_json:
                default_props = json.load(default_json)
                default_props, write = self.check_config(
                    default_props, default=True)
                fix_write = self.fix_properties(default_props)
        except FileNotFoundError:
            iocage_lib.ioc_common.logit(
                {
                    'level': 'NOTICE',
                    'message': 'Default configuration missing, creating one'
                },
                _callback=self.callback,
                silent=False)
        except json.decoder.JSONDecodeError:
            iocage_lib.ioc_common.logit(
                {
                    'level': 'ERROR',
                    'message': f'{default_json_location} corrupted'
                    ' (delete to recreate), using memory values.'
                },
                _callback=self.callback,
                silent=False)
            write = False
        except ioc_exceptions.CommandNeedsRoot as err:
            iocage_lib.ioc_common.logit(
                {
                    'level': 'ERROR',
                    'message': err.message
                },
                _callback=self.callback,
                silent=False)
            write = False
        finally:
            # They may have had new keys added to their default
            # configuration, or it never existed.
            if write or fix_write:
                self.json_write(default_props, default_json_location,
                                defaults=True)

        return default_props


class IOCJson(IOCConfiguration):

    """
    Migrates old iocage configurations(UCL and ZFS Props) to the new JSON
    format, will set and get properties.
    """

    def __init__(self,
                 location="",
                 silent=False,
                 cli=False,
                 stop=False,
                 checking_datasets=False,
                 suppress_log=False,
                 callback=None):
        self.lgr = logging.getLogger('ioc_json')
        self.cli = cli
        self.stop = stop
        self.suppress_log = suppress_log
        self.truthy_props = [
            'bpf',
            'template',
            'host_time',
            'basejail',
            'dhcp',
            'vnet',
            'rtsold',
            'jail_zfs',
            'hostid_strict_check',
            'boot',
            'exec_clean',
            'mount_linprocfs',
            'mount_procfs',
            'allow_vmm',
            'allow_tun',
            'allow_socket_af',
            'allow_quotas',
            'allow_mount_zfs',
            'allow_mount_tmpfs',
            'allow_mount_procfs',
            'allow_mount_nullfs',
            'allow_mount_fusefs',
            'allow_mount_devfs',
            'allow_mount',
            'allow_mlock',
            'allow_chflags',
            'allow_raw_sockets',
            'allow_sysvipc',
            'allow_set_hostname',
            'mount_fdescfs',
            'mount_devfs',
            'ip6_saddrsel',
            'ip4_saddrsel',
            'ip_hostname',
            'assign_localhost',
            'nat'
        ]
        super().__init__(location, checking_datasets, silent, callback)

        try:
            force_env = os.environ["IOCAGE_FORCE"]
        except KeyError:
            # FreeNAS or an API user, due to the sheer web of calls to this
            # module we are assuming they are OK with any renaming operations

            force_env = "TRUE"

        self.force = True if force_env == "TRUE" else False

    def get_full_config(self):
        d_conf = self.default_config
        conf, write = self.json_load()
        fix_write = self.fix_properties(conf)

        if write or fix_write:
            self.json_write(conf)

        state, _ = iocage_lib.ioc_list.IOCList().list_get_jid(
            conf['host_hostuuid'])

        if state:
            ruleset = su.check_output(
                [
                    'jls', '-j',
                    f'ioc-{conf["host_hostuuid"].replace(".", "_")}',
                    'devfs_ruleset'
                ]
            ).decode().rstrip()

            conf['devfs_ruleset'] = ruleset

        d_conf.update(conf)

        for p, v in d_conf.items():
            # We want to make sure these are ints
            if p in self.truthy_props:
                d_conf[p] = iocage_lib.ioc_common.check_truthy(v)

        return d_conf

    def json_convert_from_ucl(self):
        """Convert to JSON. Accepts a location to the ucl configuration."""

        if os.geteuid() != 0:
            raise RuntimeError("You need to be root to convert the"
                               " configurations to the new format!")

        with open(self.location + "/config", "r") as conf:
            lines = conf.readlines()

        key_and_value = {}

        for line in lines:
            line = line.partition("=")
            key = line[0].rstrip()
            value = line[2].replace(";", "").replace('"', '').strip()

            key_and_value[key] = value

        self.json_write(key_and_value)

    def json_convert_from_zfs(self, uuid, skip=False):
        """Convert to JSON. Accepts a jail UUID"""
        dataset = f"{self.pool}/iocage/jails/{uuid}"
        jail_zfs_prop = "org.freebsd.iocage:jail_zfs_dataset"

        if os.geteuid() != 0:
            raise RuntimeError("You need to be root to convert the"
                               " configurations to the new format!")

        props = self.zfs.get_dataset(dataset).properties

        # Filter the props we want to convert.
        prop_prefix = "org.freebsd.iocage"

        key_and_value = {"host_domainname": "none"}

        for key, prop in props.items():

            if not key.startswith(prop_prefix):
                continue

            key = key.partition(":")[2]
            value = prop.value

            if key == "type":
                if value == "basejail":
                    # These were just clones on master.
                    value = "jail"
                    key_and_value["basejail"] = 1
            elif key == "hostname":
                hostname = props[f'{prop_prefix}:host_hostname']

                if value != hostname:
                    # This is safe to replace at this point.
                    # The user changed the wrong hostname key, we will move
                    # it to the right one now.

                    if hostname == uuid:
                        key_and_value["host_hostname"] = prop.value

                continue

            key_and_value[key] = value

        if not skip:
            # Set jailed=off and move the jailed dataset.
            try:
                self.zfs_set_property(f"{dataset}/root/data", "jailed", "off")
                self.zfs.get_dataset(f"{dataset}/root/data").rename(
                    f"{dataset}/data", False, True)
                self.zfs_set_property(f"{dataset}/data", jail_zfs_prop,
                                      f"iocage/jails/{uuid}/data")
                self.zfs_set_property(f"{dataset}/data", "jailed", "on")
            except libzfs.ZFSException:
                # The jailed dataset doesn't exist, which is OK.
                pass

        key_and_value["jail_zfs_dataset"] = f"iocage/jails/{uuid}/data"

        self.json_write(key_and_value)

    def json_load(self):
        """Load the JSON at the location given. Returns a JSON object."""
        jail_type, jail_uuid = self.location.rsplit("/", 2)[-2:]
        full_uuid = jail_uuid  # Saves jail_uuid for legacy ZFS migration
        legacy_short = False

        try:
            jail_dataset = self.zfs.get_dataset(
                f"{self.pool}/iocage/{jail_type}/{jail_uuid}")
        except libzfs.ZFSException as err:
            if err.code == libzfs.Error.NOENT:
                if os.path.isfile(self.location + "/config"):
                    iocage_lib.ioc_common.logit(
                        {
                            "level": "EXCEPTION",
                            "message": "iocage_legacy develop had a broken"
                            " hack88 implementation.\nPlease manually rename"
                            f" {jail_uuid} or destroy it with zfs."
                        },
                        _callback=self.callback,
                        silent=self.silent)

                    jail_dataset = self.zfs_get_property(
                        self.location, 'mountpoint'
                    )
                    full_uuid = jail_dataset.rsplit('/')[-1]
                    legacy_short = True

                else:
                    raise ioc_exceptions.JailMissingConfiguration(
                        f'{jail_type.rstrip("s").capitalize()}:'
                        f' {jail_uuid} has a missing configuration, please'
                        ' check that the dataset is mounted.'
                    )
            else:
                raise()

        skip = False

        if jail_dataset.mountpoint is None:
            try:
                jail_dataset.mount_recursive()
            except libzfs.ZFSException as err:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": err
                    },
                    _callback=self.callback,
                    silent=self.silent)

        try:
            with open(self.location + "/config.json", "r") as conf:
                conf = json.load(conf)
        except json.decoder.JSONDecodeError:
            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': f'{jail_uuid} has a corrupt configuration,'
                    ' please fix this jail or destroy and recreate it.'
                },
                _callback=self.callback,
                silent=self.silent,
                exception=ioc_exceptions.JailCorruptConfiguration)
        except FileNotFoundError:
            try:
                # If this is a legacy jail, it will be missing this file but
                # not this key.
                jail_dataset.properties["org.freebsd.iocage:host_hostuuid"]
            except KeyError:
                if os.path.isfile(f"{self.location}/config"):
                    # iocage legacy develop jail, not missing configuration
                    pass
                else:
                    iocage_lib.ioc_common.logit(
                        {
                            'level': 'EXCEPTION',
                            'message': f'{jail_uuid} is missing it\'s'
                            ' configuration, please destroy this jail and'
                            ' recreate it.',
                            'suppress_log': self.suppress_log
                        },
                        _callback=self.callback,
                        silent=self.silent,
                        exception=ioc_exceptions.JailMissingConfiguration)

            if not self.force:
                iocage_lib.ioc_common.logit(
                    {
                        "level":
                        "EXCEPTION",
                        "message":
                        "A renaming operation is required to continue.\n"
                        f"Please run iocage -f {sys.argv[-1]} as root."
                    },
                    _callback=self.callback,
                    silent=self.silent)

            if os.path.isfile(self.location + "/config"):
                self.json_convert_from_ucl()

                with open(self.location + "/config.json", "r") as conf:
                    conf = json.load(conf)
            else:
                try:
                    dataset = self.location.split("/")

                    for d in dataset:
                        if len(d) == 36:
                            uuid = d
                        elif len(d) == 8:
                            # Hack88 migration to a perm short UUID.
                            short_uuid = full_uuid[:8]
                            full_dataset = \
                                f"{self.pool}/iocage/jails/{full_uuid}"
                            short_dataset = \
                                f"{self.pool}/iocage/jails/{short_uuid}"

                            jail_hostname = self.zfs_get_property(
                                full_dataset,
                                'org.freebsd.iocage:host_hostname')

                            self.json_convert_from_zfs(full_uuid)
                            with open(self.location + "/config.json",
                                      "r") as conf:
                                conf = json.load(conf)

                            iocage_lib.ioc_common.logit(
                                {
                                    "level":
                                    "INFO",
                                    "message":
                                    "hack88 is no longer supported."
                                    f"\n{full_dataset} is being "
                                    f"converted to {short_dataset}"
                                    f" permanently."
                                },
                                _callback=self.callback,
                                silent=self.silent)

                            status, _ = iocage_lib.ioc_list.IOCList(
                            ).list_get_jid(full_uuid)

                            if status:
                                iocage_lib.ioc_common.logit(
                                    {
                                        "level":
                                        "INFO",
                                        "message":
                                        "Stopping jail to migrate UUIDs."
                                    },
                                    _callback=self.callback,
                                    silent=self.silent)
                                iocage_lib.ioc_stop.IOCStop(
                                    full_uuid,
                                    self.location,
                                    silent=True)

                            jail_zfs_prop = \
                                "org.freebsd.iocage:jail_zfs_dataset"
                            uuid_prop = "org.freebsd.iocage:host_hostuuid"
                            host_prop = "org.freebsd.iocage:host_hostname"

                            # Set jailed=off and move the jailed dataset.
                            self.zfs_set_property(f"{full_dataset}/data",
                                                  'jailed', 'off')

                            # We don't want to change a real hostname.

                            if jail_hostname == full_uuid:
                                self.zfs_set_property(full_dataset, host_prop,
                                                      short_uuid)

                            self.zfs_set_property(full_dataset, uuid_prop,
                                                  short_uuid)
                            self.zfs_set_property(f"{full_dataset}/data",
                                                  jail_zfs_prop,
                                                  f"iocage/jails/"
                                                  f"{short_uuid}/data")

                            self.zfs.get_dataset(full_dataset).rename(
                                short_dataset, False, True)
                            self.zfs_set_property(f"{short_dataset}/data",
                                                  "jailed", "on")

                            uuid = short_uuid
                            self.location = \
                                f"{self.iocroot}/jails/{short_uuid}"
                            skip = True

                    if uuid is None:
                        iocage_lib.ioc_common.logit(
                            {
                                "level": "EXCEPTION",
                                "message": "Configuration could not be loaded,"
                                " is the jail dataset mounted?"
                            },
                            _callback=self.callback,
                            silent=self.silent)

                    self.json_convert_from_zfs(uuid, skip=skip)
                    with open(self.location + "/config.json", "r") as conf:
                        conf = json.load(conf)

                    if legacy_short:
                        messages = collections.OrderedDict(
                            [("1-NOTICE", "*" * 80),
                             ("2-WARNING",
                              f"Jail: {full_uuid} was renamed to {uuid}"),
                             ("3-NOTICE",
                              f"{'*' * 80}\n"),
                             ("4-EXCEPTION",
                              "Please issue your command again.")])

                        for level, msg in messages.items():
                            level = level.partition("-")[2]

                            iocage_lib.ioc_common.logit(
                                {
                                    "level": level,
                                    "message": msg
                                },
                                _callback=self.callback,
                                silent=self.silent)
                except su.CalledProcessError:
                    # At this point it should be a real misconfigured jail
                    raise RuntimeError("Configuration is missing!"
                                       f" Please destroy {uuid} and recreate"
                                       " it.")

        conf = self.check_config(conf)

        return conf

    def activate_pool(self, pool):
        if os.geteuid() != 0:
            raise RuntimeError("Run as root to migrate old pool"
                               " activation property!")

        self.zfs_set_property(pool, "org.freebsd.ioc:active", "yes")
        self.zfs_set_property(pool, "comment", "-")

    def json_get_value(self, prop, default=False):
        """Returns a string with the specified prop's value."""
        if default:
            conf = self.default_config

            if prop == "all":
                return conf

            return conf[prop]

        if prop == "pool":
            return self.pool
        elif prop == "iocroot":
            return self.iocroot
        elif prop == "all":
            return self.get_full_config()
        else:
            conf, write = self.json_load()
            state, _ = iocage_lib.ioc_list.IOCList().list_get_jid(
                conf['host_hostuuid'])

            if prop == "last_started" and conf[prop] == "none":
                return "never"
            elif prop == 'devfs_ruleset' and state:
                ruleset = su.check_output(
                    [
                        'jls', '-j', f'ioc-{conf["host_hostuuid"]}',
                        'devfs_ruleset'
                    ]
                ).decode().rstrip()

                return ruleset
            else:
                try:
                    return conf[prop]
                except KeyError:
                    return self.default_config[prop]

    def json_set_value(self, prop, _import=False, default=False):
        """Set a property for the specified jail."""
        key, _, value = prop.partition("=")

        if not default:
            conf, write = self.json_load()
            uuid = conf["host_hostuuid"]
            status, jid = iocage_lib.ioc_list.IOCList().list_get_jid(uuid)
            # Convert truthy to int
            if key in self.truthy_props:
                conf[key] = iocage_lib.ioc_common.check_truthy(value)
            else:
                conf[key] = value
            sysctls_cmd = ["sysctl", "-d", "security.jail.param"]
            jail_param_regex = re.compile("security.jail.param.")
            sysctls_list = su.Popen(
                sysctls_cmd,
                stdout=su.PIPE).communicate()[0].decode("utf-8").split()
            jail_params = [
                p.replace("security.jail.param.", "").replace(":", "")

                for p in sysctls_list if re.match(jail_param_regex, p)
            ]
            single_period = [
                "allow_raw_sockets", "allow_socket_af", "allow_set_hostname"
            ]

            if key == "template":
                old_location = f"{self.pool}/iocage/jails/{uuid}"
                new_location = f"{self.pool}/iocage/templates/{uuid}"

                if status:
                    iocage_lib.ioc_common.logit(
                        {
                            "level": "EXCEPTION",
                            "message":
                            f"{uuid} is running.\nPlease stop it first!"
                        },
                        _callback=self.callback,
                        silent=self.silent)

                jails = iocage_lib.ioc_list.IOCList("uuid").list_datasets()

                for j in jails:
                    _uuid = jails[j]
                    _path = f"{jails[j]}/root"
                    t_old_path = f"{old_location}/root@{_uuid}"
                    t_path = f"{new_location}/root@{_uuid}"

                    if _uuid == uuid:
                        continue

                    origin = self.zfs_get_property(_path, 'origin')

                    if origin == t_old_path or origin == t_path:
                        _status, _ = iocage_lib.ioc_list.IOCList(
                        ).list_get_jid(_uuid)

                        if _status:
                            iocage_lib.ioc_common.logit(
                                {
                                    "level":
                                    "EXCEPTION",
                                    "message":
                                    f"{uuid} is running.\n"
                                    "Please stop it first!"
                                },
                                _callback=self.callback,
                                silent=self.silent)

                if iocage_lib.ioc_common.check_truthy(value):
                    try:
                        jail_zfs_dataset = f"{self.pool}/" \
                            f"{conf['jail_zfs_dataset']}"
                        self.zfs_set_property(jail_zfs_dataset, "jailed",
                                              "off")
                    except libzfs.ZFSException as err:
                        # The dataset doesn't exist, that's OK

                        if err.code == libzfs.Error.NOENT:
                            pass
                        else:
                            iocage_lib.ioc_common.logit(
                                {
                                    "level": "EXCEPTION",
                                    "message": err
                                },
                                _callback=self.callback)

                    try:
                        self.zfs.get_dataset(old_location).rename(
                            new_location, False, True)
                    except libzfs.ZFSException as err:
                        # cannot rename
                        iocage_lib.ioc_common.logit(
                            {
                                "level": "EXCEPTION",
                                "message": f"Cannot rename zfs dataset: {err}"
                            },
                            _callback=self.callback)

                    conf["type"] = "template"

                    self.location = new_location.lstrip(self.pool).replace(
                        "/iocage", self.iocroot)

                    iocage_lib.ioc_common.logit(
                        {
                            "level": "INFO",
                            "message": f"{uuid} converted to a template."
                        },
                        _callback=self.callback,
                        silent=self.silent)

                    # Writing these now since the dataset will be readonly
                    self.json_check_prop(key, value, conf, default)
                    self.json_write(conf)

                    self.zfs_set_property(new_location, "readonly", "on")

                    return
                elif not iocage_lib.ioc_common.check_truthy(value):
                    if not _import:
                        self.zfs.get_dataset(new_location).rename(
                            old_location, False, True)
                        conf["type"] = "jail"
                        self.location = old_location.lstrip(self.pool).replace(
                            "/iocage", self.iocroot)
                        self.zfs_set_property(old_location, "readonly", "off")

                        iocage_lib.ioc_common.logit(
                            {
                                "level": "INFO",
                                "message": f"{uuid} converted to a jail."
                            },
                            _callback=self.callback,
                            silent=self.silent)

                    return

            if key[:8] == "jail_zfs" or key == 'dhcp':
                if status:
                    iocage_lib.ioc_common.logit(
                        {
                            "level": "EXCEPTION",
                            "message":
                            f"{uuid} is running.\nPlease stop it first!"
                        },
                        _callback=self.callback,
                        silent=self.silent)
            if write:
                self.json_write(conf)
        else:
            conf = self.default_config

        if not default:
            full_conf = self.get_full_config()
            value, conf = self.json_check_prop(key, value, conf)
            old_value = full_conf[key] if key not in self.truthy_props else \
                iocage_lib.ioc_common.check_truthy(full_conf[key])
            display_value = value if key not in self.truthy_props else \
                iocage_lib.ioc_common.check_truthy(value)
            self.json_write(conf)

            iocage_lib.ioc_common.logit(
                {
                    "level": "INFO",
                    "message": f'{key}: {old_value} -> {display_value}'
                },
                _callback=self.callback,
                silent=self.silent)

            # We can attempt to set a property in realtime to jail.

            if status:
                if key in single_period:
                    key = key.replace("_", ".", 1)
                else:
                    key = key.replace("_", ".")

                if key == 'cpuset':
                    iocage_lib.ioc_common.logit(
                        {
                            'level': 'INFO',
                            'message': 'cpuset changes '
                                       'require a jail restart'
                        },
                        _callback=self.callback,
                        silent=self.silent
                    )

                # Let's set a rctl rule for the prop if applicable
                if key in IOCRCTL.types:
                    rctl_jail = IOCRCTL(conf['host_hostuuid'])
                    rctl_jail.validate_rctl_tunable()

                    if value != 'off':
                        failed = rctl_jail.set_rctl_rules(
                            (key, value)
                        )
                        if failed:
                            msg = f'Failed to set RCTL rule for {key}'
                        else:
                            msg = f'Successfully set RCTL rule for {key}'

                        iocage_lib.ioc_common.logit(
                            {
                                'level': 'INFO',
                                'message': msg
                            },
                            _callback=self.callback,
                            silent=self.silent
                        )
                    else:
                        if rctl_jail.rctl_rules_exist(key):
                            failed = rctl_jail.remove_rctl_rules([key])
                            if failed:
                                msg = f'Failed to remove RCTL ' \
                                    f'rule for {key}'
                            else:
                                msg = 'Successfully removed RCTL ' \
                                    f'rule for {key}'

                            iocage_lib.ioc_common.logit(
                                {
                                    'level': 'INFO',
                                    'message': msg
                                },
                                _callback=self.callback,
                                silent=self.silent
                            )

                if key in jail_params:
                    if full_conf['vnet'] and (
                        key == "ip4.addr" or key == "ip6.addr"
                    ):
                        return

                    try:
                        ip = True if key == "ip4.addr" or key == "ip6.addr" \
                            else False

                        if ip and value.lower() == "none":
                            return

                        if key == "vnet":
                            # We can't switch vnet dynamically
                            iocage_lib.ioc_common.logit(
                                {
                                    'level': 'INFO',
                                    'message': 'vnet changes require a jail'
                                               ' restart'
                                },
                                _callback=self.callback,
                                silent=self.silent)

                            return

                        iocage_lib.ioc_common.checkoutput(
                            ["jail", "-m", f"jid={jid}", f"{key}={value}"],
                            stderr=su.STDOUT)
                    except su.CalledProcessError as err:
                        raise RuntimeError(
                            f"{err.output.decode('utf-8').rstrip()}")
        else:
            if key in conf:
                value, conf = self.json_check_prop(
                    key, value, conf, default=True
                )
                conf[key] = value
                self.json_write(conf, "/defaults.json")

                iocage_lib.ioc_common.logit(
                    {
                        'level': 'INFO',
                        'message': f'Default Property: {key} has been updated '
                                   f'to {value}'
                    },
                    _callback=self.callback,
                    silent=self.silent)
            else:
                msg = f'{key} is not a valid property for default!'
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'EXCEPTION',
                        'message': msg
                    },
                    _callback=self.callback,
                    silent=self.silent)

    def json_check_prop(self, key, value, conf, default=False):
        """
        Checks if the property matches known good values, if it's the
        CLI, deny setting any properties not in this list.
        """
        truth_variations = (
            '0', '1', 'off', 'on', 'no', 'yes', 'false', 'true'
        )

        props = {
            # Network properties
            "interfaces": (":", ","),
            "host_domainname": ("string", ),
            "host_hostname": ("string", ),
            "exec_fib": ("string", ),
            "ip4_addr": ("string", ),
            "ip4_saddrsel": truth_variations,
            "ip4": ("new", "inherit", "disable"),
            "ip6_addr": ("string", ),
            "ip6_saddrsel": truth_variations,
            "ip6": ("new", "inherit", "disable"),
            "defaultrouter": ("string", ),
            "defaultrouter6": ("string", ),
            "resolver": ("string", ),
            "mac_prefix": ("string", ),
            "vnet0_mac": ("string", ),
            "vnet1_mac": ("string", ),
            "vnet2_mac": ("string", ),
            "vnet3_mac": ("string", ),
            # Jail Properties
            "devfs_ruleset": ("string", ),
            "exec_start": ("string", ),
            "exec_stop": ("string", ),
            "exec_prestart": ("string", ),
            "exec_poststart": ("string", ),
            "exec_prestop": ("string", ),
            "exec_poststop": ("string", ),
            "exec_clean": truth_variations,
            "exec_created": ("string", ),
            "exec_timeout": ("string", ),
            "stop_timeout": ("string", ),
            "exec_jail_user": ("string", ),
            "exec_system_jail_user": ("string", ),
            "exec_system_user": ("string", ),
            "mount_devfs": truth_variations,
            "mount_fdescfs": truth_variations,
            "enforce_statfs": ("0", "1", "2"),
            "children_max": ("string", ),
            "login_flags": ("string", ),
            "securelevel": ("string", ),
            "sysvmsg": ("new", "inherit", "disable"),
            "sysvsem": ("new", "inherit", "disable"),
            "sysvshm": ("new", "inherit", "disable"),
            "allow_set_hostname": truth_variations,
            "allow_sysvipc": truth_variations,
            "allow_raw_sockets": truth_variations,
            "allow_chflags": truth_variations,
            "allow_mlock": truth_variations,
            "allow_mount": truth_variations,
            "allow_mount_devfs": truth_variations,
            "allow_mount_fusefs": truth_variations,
            "allow_mount_nullfs": truth_variations,
            "allow_mount_procfs": truth_variations,
            "allow_mount_tmpfs": truth_variations,
            "allow_mount_zfs": truth_variations,
            "allow_quotas": truth_variations,
            "allow_socket_af": truth_variations,
            "allow_vmm": truth_variations,
            "vnet_interfaces": ("string", ),
            # RCTL limits
            "cpuset": ('string',),
            "rlimits": ("off", "on"),
            "memoryuse": ('string',),
            "memorylocked": ('string',),
            "vmemoryuse": ('string',),
            "maxproc": ('string',),
            "cputime": ('string',),
            "pcpu": ('string',),
            "datasize": ('string',),
            "stacksize": ('string',),
            "coredumpsize": ('string',),
            "openfiles": ('string',),
            "pseudoterminals": ('string',),
            "swapuse": ('string',),
            "nthr": ('string',),
            "msgqqueued": ('string',),
            "msgqsize": ('string',),
            "nmsgq": ('string',),
            "nsem": ('string',),
            "nsemop": ('string',),
            "nshm": ('string',),
            "shmsize": ('string',),
            "wallclock": ('string',),
            "readbps": ('string',),
            "writebps": ('string',),
            "readiops": ('string',),
            "writeiops": ('string',),
            # Custom properties
            "bpf": truth_variations,
            "dhcp": truth_variations,
            "boot": truth_variations,
            "notes": ("string", ),
            "owner": ("string", ),
            "priority": str(tuple(range(1, 100))),
            "hostid": ("string", ),
            "hostid_strict_check": truth_variations,
            "jail_zfs": truth_variations,
            "jail_zfs_dataset": ("string", ),
            "jail_zfs_mountpoint": ("string", ),
            "mount_procfs": truth_variations,
            "mount_linprocfs": truth_variations,
            "vnet": truth_variations,
            "vnet_default_interface": ("string",),
            "template": truth_variations,
            "comment": ("string", ),
            "host_time": truth_variations,
            "depends": ("string", ),
            "allow_tun": truth_variations,
            'rtsold': truth_variations,
            'ip_hostname': truth_variations,
            'assign_localhost': truth_variations,
            'localhost_ip': ('string', ),
            'nat': truth_variations,
            'nat_prefix': ('string', ),
            'nat_interface': ('string', ),
            'nat_backend': ('pf', 'ipfw'),
            'nat_forwards': ('string', )
        }

        zfs_props = {
            # ZFS Props
            "compression": "lz4",
            "origin": "readonly",
            "quota": "none",
            "mountpoint": "readonly",
            "compressratio": "readonly",
            "available": "readonly",
            "used": "readonly",
            "dedup": "off",
            "reservation": "none",
        }

        if key in (
            'nat_prefix', 'nat_interface', 'nat_backend'
        ) and not default:
            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': f'{key} can only be changed for defaults!'
                },
                _callback=self.callback,
                silent=self.silent)

        if key in zfs_props.keys():
            if iocage_lib.ioc_common.check_truthy(
                conf.get('template', '0')
            ):
                _type = "templates"
            else:
                _type = "jails"

            uuid = conf["host_hostuuid"]

            if key == "quota":
                if value != "none" and not \
                        value.upper().endswith(("M", "G", "T")):
                    err = f"{value} should have a suffix ending in" \
                        " M, G, or T."
                    iocage_lib.ioc_common.logit(
                        {
                            "level": "EXCEPTION",
                            "message": err
                        },
                        _callback=self.callback,
                        silent=self.silent)

            self.zfs_set_property(f"{self.pool}/iocage/{_type}/{uuid}", key,
                                  value)

            return value, conf

        elif key in props.keys():
            # Either it contains what we expect, or it's a string.

            for k in props[key]:
                if k in value.lower():
                    return value, conf

            if props[key][0] == 'string':
                if key in (
                    'ip4_addr', 'ip6_addr'
                ) and (
                    value != 'none' and 'DHCP' not in value.upper() and
                    'accept_rtadv' not in value.lower()
                ):
                    # There are three possible formats here
                    # 1 - interface|ip/subnet
                    # 2 - interface|ip
                    # 3 - ip
                    # 4 - interface|DHCP
                    # 5 - interface|accept_rtadv
                    # All the while of course assuming that we can
                    # have more then one ip
                    if key == 'ip4_addr':
                        ip_check = ipaddress.IPv4Network
                    else:
                        ip_check = ipaddress.IPv6Network

                    final_value = []
                    for ip_str in value.split(','):
                        if '|' in ip_str:
                            interface, ip = map(
                                str.strip,
                                ip_str.split('|')
                            )
                        else:
                            interface, ip = None, ip_str
                        if interface == '':
                            iocage_lib.ioc_common.logit(
                                {
                                    'level': 'EXCEPTION',
                                    'message': 'Please provide a valid '
                                               'interface'
                                },
                                _callback=self.callback,
                                silent=self.silent
                            )
                        elif interface == 'DEFAULT':
                            # When starting the jail, if interface is not
                            # present, we add default interface automatically
                            interface = None

                        # Let's validate the ip address now
                        try:
                            ip_check(ip, strict=False)
                        except ValueError as e:
                            iocage_lib.ioc_common.logit(
                                {
                                    'level': 'EXCEPTION',
                                    'message': 'Please provide a valid '
                                    f'ip: {e}'
                                },
                                _callback=self.callback,
                                silent=self.silent
                            )
                        else:
                            if interface is not None:
                                iface = f'{interface}|'
                            else:
                                iface = ''
                            final_value.append(f'{iface}{ip}')

                    conf[key] = ','.join(final_value)
                elif key in [f'vnet{i}_mac' for i in range(0, 4)]:
                    if value and value != 'none':
                        value = value.replace(',', ' ')
                        rx = \
                            "[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$"
                        if (
                            any(
                                not re.match(
                                    rx,
                                    v.lower()
                                ) for v in value.split()
                            ) or len(
                                value.split()
                            ) != 2 or any(
                                value.split().count(v) > 1 for v in
                                value.split()
                            )
                        ):
                            iocage_lib.ioc_common.logit(
                                {
                                    'level': 'EXCEPTION',
                                    'message':
                                    'Please enter two valid and different '
                                    'space/comma-delimited MAC addresses for '
                                    f'{key}.'
                                },
                                _callback=self.callback,
                                silent=self.silent
                            )
                    elif not value:
                        # Let's standardise the value to none in case
                        # vnetX_mac is not provided
                        value = 'none'
                elif key == 'vnet_default_interface' and value not in (
                        'none', 'auto'):
                    if value not in netifaces.interfaces():
                        iocage_lib.ioc_common.logit(
                            {
                                'level': 'EXCEPTION',
                                'message':
                                'Please provide a valid NIC to be used '
                                'with vnet'
                            },
                            _callback=self.callback,
                            silent=self.silent
                        )
                elif key in IOCRCTL.types:
                    IOCRCTL.validate_rctl_props(key, value)
                elif key == 'cpuset':
                    IOCCpuset.validate_cpuset_prop(value)
                elif key == 'localhost_ip':
                    if value != 'none':
                        try:
                            ipaddress.IPv4Address(value)
                        except ipaddress.AddressValueError as e:
                            iocage_lib.ioc_common.logit(
                                {
                                    'level': 'EXCEPTION',
                                    'message': f'Invalid IPv4 address: {e}'
                                },
                                _callback=self.callback,
                                silent=self.silent
                            )
                elif key == 'nat_forwards':
                    new_value = []

                    if value != 'none':
                        regex = re.compile(
                            r'(^tcp|^udp|^tcp\/udp)\(\d{1,5}((:|-?)'
                            r'(\d{1,5}))\)'
                        )
                        for fwd in value.split(','):
                            # We assume TCP for simpler inputs
                            fwd = f'tcp({fwd})'
                            new_value.append(fwd)

                            match = regex.match(fwd)
                            if not match or len(fwd) != match.span()[1]:
                                iocage_lib.ioc_common.logit(
                                    {
                                        'level': 'EXCEPTION',
                                        'message': f'Invalid nat_forwards'
                                                   f' value: {value}'
                                    },
                                    _callback=self.callback,
                                    silent=self.silent,
                                    exception=ioc_exceptions.ValidationFailed
                                )

                        if new_value:
                            value = ','.join(new_value)
                            conf[key] = value
                elif key == 'nat_prefix':
                    if value != 'none':
                        try:
                            ip = ipaddress.IPv4Address(f'{value}.0.0')

                            if not ip.is_private:
                                iocage_lib.ioc_common.logit(
                                    {
                                        'level': 'EXCEPTION',
                                        'message': f'Invalid nat_prefix value:'
                                                   f' {value}\n'
                                                   'Must be a private range'
                                    },
                                    _callback=self.callback,
                                    silent=self.silent,
                                    exception=ioc_exceptions.ValidationFailed
                                )
                        except ipaddress.AddressValueError:
                            iocage_lib.ioc_common.logit(
                                {
                                    'level': 'EXCEPTION',
                                    'message': f'Invalid nat_prefix value:'
                                               f' {value}\n'
                                               'Supply the first two octets'
                                               ' only (XXX.XXX)'
                                },
                                _callback=self.callback,
                                silent=self.silent,
                                exception=ioc_exceptions.ValidationFailed
                            )

                return value, conf
            else:
                err = f"{value} is not a valid value for {key}.\n"

                if key not in ("interfaces", "memoryuse"):
                    msg = f"Value must be {' or '.join(props[key])}"

                elif key == "interfaces":
                    msg = "Interfaces must be specified as a pair.\n" \
                          "EXAMPLE: vnet0:bridge0, vnet1:bridge1"
                elif key == "memoryuse":
                    msg = "memoryuse requires at minimum a pair.\nEXAMPLE: " \
                          "8g:log"

                msg = err + msg
                iocage_lib.ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": msg
                    },
                    _callback=self.callback,
                    silent=self.silent)
        else:
            if self.cli:
                msg = f"{key} cannot be changed by the user."
            else:
                if key not in conf.keys():
                    msg = f"{key} is not a valid property!"
                else:
                    return value, conf

            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": msg
                },
                _callback=self.callback,
                silent=self.silent)

    def json_plugin_load(self):
        try:
            with open(f"{self.location}/plugin/settings.json", "r") as \
                    settings:
                settings = json.load(settings)
        except FileNotFoundError:
            msg = f"No settings.json exists in {self.location}/plugin!"

            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": msg
                },
                _callback=self.callback,
                silent=self.silent)

        return settings

    def json_plugin_get_value(self, prop):

        if os.geteuid() != 0:
            raise ioc_exceptions.CommandNeedsRoot("You need to be root to"
                                                  " read a plugin property")

        conf, write = self.json_load()
        uuid = conf["host_hostuuid"]
        _path = self.zfs_get_property(f"{self.pool}/iocage/jails/{uuid}",
                                      "mountpoint")

        # Plugin variables
        settings = self.json_plugin_load()
        serviceget = settings["serviceget"]
        prop_error = ".".join(prop)

        if "options" in prop:
            _prop = prop[1:]
        else:
            _prop = prop

        prop_cmd = f"{serviceget},{','.join(_prop)}".split(",")
        try:
            if prop[0] != "all":
                if len(_prop) > 1:
                    return iocage_lib.ioc_common.get_nested_key(settings, prop)
                else:
                    with iocage_lib.ioc_exec.IOCExec(
                        prop_cmd,
                        _path,
                        uuid=uuid,
                        plugin=True
                    ) as _exec:
                        prop_out = iocage_lib.ioc_common.consume_and_log(
                            _exec,
                            log=False
                        )
                        return prop_out[0]
            else:
                return settings
        except KeyError:
            msg = f"Key: \"{prop_error}\" does not exist!"

            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": msg
                },
                _callback=self.callback,
                silent=self.silent)

        if write:
            self.json_write(conf)

    def json_plugin_set_value(self, prop):
        conf, write = self.json_load()
        uuid = conf["host_hostuuid"]
        _path = self.zfs_get_property(f"{self.pool}/iocage/jails/{uuid}",
                                      "mountpoint")
        status, _ = iocage_lib.ioc_list.IOCList().list_get_jid(uuid)

        # Plugin variables
        settings = self.json_plugin_load()
        serviceset = settings["serviceset"]
        servicerestart = settings["servicerestart"].split()
        keys, _, value = ".".join(prop).partition("=")
        prop = keys.split(".")
        restart = False
        readonly = False

        if "options" in prop:
            prop = keys.split(".")[1:]

        prop_cmd = f"{serviceset},{','.join(prop)},{value}".split(",")
        setting = settings["options"]

        try:
            while prop:
                current = prop[0]
                key = current
                prop.remove(current)

                if not prop:
                    if setting[current]:
                        try:
                            restart = setting[current]["requirerestart"]
                            readonly = setting[current]["readonly"]
                        except KeyError:
                            pass
                else:
                    setting = setting[current]

            if readonly:
                iocage_lib.ioc_common.logit({
                    "level": "ERROR",
                    "message": "This key is readonly!"
                })

                return True

            if status:
                # IOCExec will not show this if it doesn't start the jail.
                iocage_lib.ioc_common.logit(
                    {
                        "level": "INFO",
                        "message": "Command output:"
                    },
                    _callback=self.callback,
                    silent=self.silent)
            with iocage_lib.ioc_exec.IOCExec(
                prop_cmd, _path, uuid=uuid
            ) as _exec:
                iocage_lib.ioc_common.consume_and_log(
                    _exec,
                    callback=self.callback
                )

            if restart:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "INFO",
                        "message": "\n-- Restarting service --"
                    },
                    _callback=self.callback,
                    silent=self.silent)
                iocage_lib.ioc_common.logit(
                    {
                        "level": "INFO",
                        "message": "Command output:"
                    },
                    _callback=self.callback,
                    silent=self.silent)
                with iocage_lib.ioc_exec.IOCExec(
                    servicerestart,
                    _path,
                    uuid=uuid
                ) as _exec:
                    iocage_lib.ioc_common.consume_and_log(
                        _exec,
                        callback=self.callback
                    )

            iocage_lib.ioc_common.logit(
                {
                    "level": "INFO",
                    "message": f"\nKey: {keys} has been updated to {value}"
                },
                _callback=self.callback,
                silent=self.silent)
        except KeyError:
            iocage_lib.ioc_common.logit(
                {
                    "level": "EXCEPTION",
                    "message": f"Key: \"{key}\" does not exist!"
                },
                _callback=self.callback,
                silent=self.silent)

        if write:
            self.json_write(conf)

    def json_migrate_uuid_to_tag(self, uuid, tag, state, conf):
        """This will migrate an old uuid + tag jail to a tag only one"""

        date_fmt = "%Y-%m-%d@%H:%M:%S:%f"
        date_fmt_legacy = "%Y-%m-%d@%H:%M:%S"

        # We don't want to rename datasets to a bunch of dates.
        try:
            datetime.datetime.strptime(tag, date_fmt)

            # For writing later
            tag = uuid
        except ValueError:
            try:
                # This may fail the first time with legacy jails,
                # making sure one more time that it's not a legacy jail
                datetime.datetime.strptime(tag, date_fmt_legacy)

                # For writing later
                tag = uuid
            except ValueError:
                try:
                    if self.stop and state:
                        # This will allow the user to actually stop
                        # the running jails before migration.

                        return (conf, True, False)

                    if state:
                        iocage_lib.ioc_common.logit(
                            {
                                "level":
                                "EXCEPTION",
                                "message":
                                f"{uuid} ({tag}) is running,"
                                " all jails must be stopped"
                                " before iocage will"
                                " continue migration"
                            },
                            _callback=self.callback,
                            silent=self.silent)

                    try:
                        # Can't rename when the child is
                        # in a non-global zone
                        jail_parent_ds = f"{self.pool}/iocage/jails/{uuid}"
                        data_dataset = self.zfs.get_dataset(
                            f"{jail_parent_ds}/data")
                        dependents = data_dataset.dependents

                        self.zfs_set_property(f"{jail_parent_ds}/data",
                                              "jailed", "off")

                        for dep in dependents:
                            if dep.type != "FILESYSTEM":
                                continue

                            d = dep.name
                            self.zfs_set_property(d, "jailed", "off")

                    except libzfs.ZFSException:
                        # No data dataset exists
                        pass

                    jail = self.zfs.get_dataset(jail_parent_ds)

                    try:
                        jail.snapshot(
                            f"{jail_parent_ds}@{tag}", recursive=True)
                    except libzfs.ZFSException as err:
                        if err.code == libzfs.Error.EXISTS:
                            err_msg = \
                                f"Snapshot {jail_parent_ds}@{tag} already" \
                                " exists!"
                            iocage_lib.ioc_common.logit(
                                {
                                    "level": "EXCEPTION",
                                    "message": err_msg
                                },
                                _callback=self.callback,
                                silent=self.silent)
                        else:
                            raise ()

                    for snap in jail.snapshots_recursive:
                        snap_name = snap.name.rsplit("@", 1)[1]

                        # We only want our snapshot for this, the rest will
                        # follow

                        if snap_name == tag:
                            new_dataset = snap.name.replace(uuid,
                                                            tag).split("@")[0]
                            snap.clone(new_dataset)

                    # Datasets are not mounted upon creation
                    new_jail_parent_ds = f"{self.pool}/iocage/jails/{tag}"
                    new_jail = self.zfs.get_dataset(new_jail_parent_ds)
                    new_jail.mount()
                    new_jail.promote()

                    for new_ds in new_jail.children_recursive:
                        new_ds.mount()
                        new_ds.promote()

                    # Easier.
                    su.check_call([
                        "zfs", "rename", "-r", f"{self.pool}/iocage@{uuid}",
                        f"@{tag}"
                    ])

                    try:
                        # The childern will also inherit this
                        self.zfs_set_property(f"{new_jail_parent_ds}/data",
                                              "jailed", "on")
                    except libzfs.ZFSException:
                        # No data dataset exists
                        pass

                    for line in fileinput.input(
                            f"{self.iocroot}/jails/{tag}/root/etc/rc.conf",
                            inplace=1):
                        print(
                            line.replace(f'hostname="{uuid}"',
                                         f'hostname="{tag}"').rstrip())

                    if iocage_lib.ioc_common.check_truthy(conf["basejail"]):
                        for line in fileinput.input(
                                f"{self.iocroot}/jails/{tag}/fstab",
                                inplace=1):
                            print(line.replace(f'{uuid}', f'{tag}').rstrip())

                    # Cleanup old datasets, dependents is like
                    # children_recursive but in reverse, useful for root/*
                    # datasets

                    for old_ds in jail.dependents:
                        if old_ds.type == libzfs.DatasetType.FILESYSTEM:
                            old_ds.umount(force=True)

                        old_ds.delete()

                    jail.umount(force=True)
                    jail.delete()

                    try:
                        shutil.rmtree(f"{self.iocroot}/jails/{uuid}")
                    except Exception:
                        # Sometimes it becomes a directory when legacy short
                        # UUIDs are involved
                        pass

                    # Cleanup our snapshot from the cloning process

                    for snap in new_jail.snapshots_recursive:
                        snap_name = snap.name.rsplit("@", 1)[1]

                        if snap_name == tag:
                            s = self.zfs.get_snapshot(snap.name)
                            s.delete()

                except libzfs.ZFSException:
                    # A template, already renamed to a TAG
                    pass

        conf["host_hostuuid"] = tag

        if conf["host_hostname"] == uuid:
            # They may have set their own, we don't want to trample it.
            conf["host_hostname"] = tag

        return (conf, False, True)
