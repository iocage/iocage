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
import string
import subprocess as su
import sys

import iocage_lib.ioc_common
import iocage_lib.ioc_create
import iocage_lib.ioc_exec
import iocage_lib.ioc_fstab
import iocage_lib.ioc_list
import iocage_lib.ioc_stop
import iocage_lib.ioc_exceptions as ioc_exceptions
import netifaces
import random
import pathlib

from iocage_lib.dataset import Dataset
from iocage_lib.pools import PoolListableResource, Pool
from iocage_lib.snapshot import Snapshot


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
                v = v.replace(';', '').strip().strip('"')

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
                f'"{self.name}" {{\n\t{config_params}\n}}\n'
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
                value, flags=re.IGNORECASE
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
                    value, flags=re.IGNORECASE
                ) and prop in (
                    'cputime', 'maxproc', 'openfiles', 'pseudoterminals',
                    'nthr', 'msgqqueued', 'nmsgq', 'nsem', 'nsemop', 'nshm',
                    'wallclock', 'pcpu'
                ):
                    iocage_lib.ioc_common.logit(
                        {
                            'level': 'EXCEPTION',
                            'message': f'suffix {value[-1]} is not allowed '
                            f'with {prop}'
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


class IOCConfiguration:
    def __init__(self, location, checking_datasets, silent, callback):
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
        version = '28'

        return version

    def get_pool_and_iocroot(self):
        """For internal getting of pool and iocroot."""
        def get_pool():
            # This function does following (keeping old behavior):
            # 1) Ensures multiple activated pools aren't present
            # 2) Activates first pool it finds until activate command has been
            #  issued already ( keeping old behavior )
            # 3) Only activate if pool is not freenas-boot/boot-pool and
            # iocage skip is false
            old = False
            matches = []
            zpools = [pool for pool in PoolListableResource() if not pool.root_dataset.locked]
            for pool in zpools:
                if pool.active:
                    matches.append(pool)
                elif pool.properties.get('comment') == 'iocage':
                    matches.append(pool)
                    old = True

            if len(matches) == 1:
                if old:
                    matches[0].activate_pool()

                return matches[0].name

            elif len(matches) > 1:
                iocage_lib.ioc_common.logit(
                    {
                        "level": "ERROR",
                        "message": "Pools:"
                    },
                    _callback=self.callback,
                    silent=self.silent)

                pools = '\n'.join([str(p) for p in matches])
                raise RuntimeError(f'{pools}\nYou have {len(matches)} pools'
                                   f'marked active for iocage usage.\n '
                                   f'Run \"iocage  activate ZPOOL\" '
                                   f'on the preferred pool.\n')
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

                    if zpool in (Pool('freenas-boot'), Pool('boot-pool')):
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

                    zpool.activate_pool()

                    return zpool.name

        pool = get_pool()

        def get_iocroot():
            loc = Dataset(os.path.join(pool, 'iocage'))

            if not loc.exists:
                # It's okay, ioc check would create datasets
                return ''
            elif loc.mounted:
                return loc.path
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
            if len(mac_prefix) != 6 or not set(mac_prefix).issubset(string.hexdigits):
                # We do this because in certain cases ( very likely due to netifaces not properly
                # retrieving values ) mac_prefix can be `lo0` which results in an error
                # as we consider this to be a valid mac prefix below and just try to replace bits
                # which in this case don't exist resulting in an unintended exception
                raise ValueError()

        except (KeyError, ValueError):
            # They don't have a default gateway, opting for generation of mac
            mac = random.randint(0x00, 0xfffff)

            mac_prefix = f'{mac:06x}'

        # Reason for this change is that the first bit in the first byte of
        # mac address dictates unicast/multicast address. In case of
        # multicast address, bridge does not learn from such addresses.
        # So we make sure that we have it unset and the second bit indicates
        # that this mac is being used in a local network which we set it
        # always.
        if not IOCConfiguration.validate_mac_prefix(mac_prefix):
            # First and second bits in the first byte will be at
            # 7th and 6th indexes respectively as networks are
            # MSB-LTR ordered
            binary = list(format(int(mac_prefix, 16), '024b'))
            binary[6] = '1'
            binary[7] = '0'
            mac_prefix = format(int(''.join(binary), 2), '06x')

        return mac_prefix

    @staticmethod
    def validate_mac_prefix(mac_prefix):
        valid = len(mac_prefix) == 6
        if valid:
            binary = format(int(mac_prefix, 16), '024b')
            valid = binary[7] == '0' and binary[6] == '1'
        return valid

    def json_write(self, data, _file="/config.json", defaults=False):
        """Write a JSON file at the location given with supplied data."""
        # Templates need to be set r/w and then back to r/o
        try:
            template = iocage_lib.ioc_common.check_truthy(
                data['template']
            ) and not defaults
            jail_dataset = Dataset(self.location).name if template else None
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

        if conf.get('type') in ('plugin', 'pluginv2'):
            official_repo = 'https://github.com/freenas/iocage-ix-plugins.git'
            if conf.get('plugin_repository', 'none') == 'none':
                conf['plugin_repository'] = official_repo

            if conf.get('plugin_name', 'none') == 'none':
                jail_path = os.path.join(
                    self.iocroot, 'jails', conf.get('host_hostuuid')
                )

                json_files = [
                    f for f in os.listdir(jail_path)
                    if f != 'config.json' and f.endswith('.json')
                ]

                if len(json_files) == 1:
                    # It should be 1 only but if it isn't, this is unexpected
                    # and we can't anticipate which file to use in this case
                    try:
                        with open(
                            os.path.join(jail_path, json_files[0]), 'r'
                        ) as f:
                            plugin_data = json.loads(f.read())
                    except json.JSONDecodeError:
                        pass
                    else:
                        if plugin_data.get('name'):
                            # If the json file has a name entry, we assume
                            # that the json file in question is the plugin
                            # manifest and we use the json file's name
                            # as the plugin name. Motivation is that most
                            # if not all have same plugin entries as their
                            # manifest names, however some plugins like plex
                            # have a different plugin name in their manifest,
                            # a short one which causes issues if the user
                            # tries to upgrade.
                            conf['plugin_name'] = json_files[0].rsplit(
                                '.json', 1
                            )[0]

            # This is our last resort - if above strategy didn't work,
            # let's use host_hostuuid in this case
            if conf.get('host_hostuuid') and conf.get(
                'plugin_name', 'none'
            ) == 'none':
                conf['plugin_name'] = conf['host_hostuuid'].rsplit('_', 1)[0]

            if conf['plugin_name'] in (
                'channels-dvr', 'dnsmasq', 'homebridge', 'irssi', 'madsonic',
                'openvpn', 'quasselcore', 'rtorrent-flood', 'sickchill',
                'unificontroller', 'unificontroller-lts', 'weechat', 'xmrig',
                'radarr', 'sonarr', 'backuppc', 'clamav', 'couchpotato', 'emby',
                'jenkins', 'jenkins-lts', 'mineos', 'transmission', 'tautulli',
                'qbittorrent', 'zoneminder',
            ) and conf['plugin_repository'] in official_repo:
                conf['plugin_repository'] = \
                    'https://github.com/ix-plugin-hub/iocage-plugin-index.git'

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

        # Version 24 key
        if not conf.get('plugin_name'):
            conf['plugin_name'] = 'none'

        # Version 25 key
        if not conf.get('plugin_repository'):
            conf['plugin_repository'] = 'none'

        # Version 26 keys
        # Migrate defaultrouter and defaultrouter6 default 'none' to 'auto'
        for option in ('defaultrouter', 'defaultrouter6'):
            if conf.get(option) == 'none':
                conf[option] = 'auto'

        # Version 27 key
        if not conf.get('min_dyn_devfs_ruleset'):
            conf['min_dyn_devfs_ruleset'] = '1000'

        # Version 28 keys
        for x in range(0, 4):
            if not conf.get(f"vnet{x}_mtu"):
                conf[f"vnet{x}_mtu"] = 'auto'
        if not conf.get("vnet_default_mtu"):
            conf["vnet_default_mtu"] = '1500'

        if not default:
            conf.update(jail_conf)

        return conf, True

    def backup_iocage_jail_conf(self, location):
        if os.path.exists(location):
            dest = location.rsplit('/', 1)[-1].replace('.json', '')
            shutil.copy(
                location, os.path.join(
                    location.rsplit('/', 1)[0], f'{dest}_backup.json'
                )
            )

    def check_jail_config(self, conf):
        """
        Checks the jails configuration and migrates anything needed
        """
        release = conf.get('release', None)
        template = conf.get('template', 0)
        host_hostuuid = conf.get('host_hostuuid', None)
        renamed = False

        if release is None or host_hostuuid is None:
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

        if iocage_lib.ioc_common.check_truthy(template):
            freebsd_version_path = \
                f'{self.iocroot}/templates/{conf["host_hostuuid"]}/root'
        else:
            freebsd_version_path = f'{self.iocroot}/jails/{host_hostuuid}/root'

        freebsd_version = pathlib.Path(
            f'{freebsd_version_path}/bin/freebsd-version'
        )

        if not freebsd_version.is_file() and conf.get('basejail'):
            # It is possible the basejail hasn't started yet. I believe
            # the best case here is to parse fstab entries and determine
            # which release is being used and check it for freebsd-version
            fstab = iocage_lib.ioc_fstab.IOCFstab(host_hostuuid, 'list')
            fstab.__validate_fstab__([l[1] for l in fstab.fstab], 'all')
            for index, fstab_entry in fstab.fstab_list():
                if fstab_entry[1].rstrip('/') == os.path.join(
                    freebsd_version_path, 'bin'
                ):
                    freebsd_version = pathlib.Path(
                        os.path.join(fstab_entry[0], 'freebsd-version')
                    )
                    freebsd_version_path = fstab_entry[0].rstrip('/').rsplit(
                        '/', 1
                    )[0]

        if not freebsd_version.is_file():
            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': 'freebsd-version could not be found at'
                    f' {freebsd_version}'
                }
            )

        if release[:4].endswith('-'):
            # 9.3-RELEASE and under don't actually have this binary.
            release = conf['release']
        elif release == 'EMPTY':
            pass
        else:
            try:
                release = iocage_lib.ioc_common.get_jail_freebsd_version(
                    freebsd_version_path, release
                )
            except Exception as e:
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'EXCEPTION',
                        'message': 'Exception:'
                        f" '{e.__class__.__name__}:{str(e)}' occurred\n"
                        f"Loading {host_hostuuid}'s "
                        "configuration failed"
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

    @staticmethod
    def retrieve_default_props():
        try:
            with open('/etc/hostid', 'r') as _file:
                hostid = _file.read().strip()
        except Exception:
            hostid = None
        return {
            'CONFIG_VERSION': IOCConfiguration.get_version(),
            'interfaces': 'vnet0:bridge0',
            'host_domainname': 'none',
            'exec_fib': '0',
            'ip4_addr': 'none',
            'ip4_saddrsel': '1',
            'ip4': 'new',
            'ip6_addr': 'none',
            'ip6_saddrsel': '1',
            'ip6': 'new',
            'defaultrouter': 'auto',
            'defaultrouter6': 'auto',
            'resolver': '/etc/resolv.conf',
            'mac_prefix': IOCConfiguration.get_mac_prefix(),
            'vnet0_mac': 'none',
            'vnet1_mac': 'none',
            'vnet2_mac': 'none',
            'vnet3_mac': 'none',
            'vnet_default_interface': 'auto',
            'devfs_ruleset': str(iocage_lib.ioc_common.IOCAGE_DEVFS_RULESET),
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
            'nat_forwards': 'none',
            'plugin_name': 'none',
            'plugin_repository': 'none',
            'min_dyn_devfs_ruleset': '1000',
            'vnet0_mtu': 'auto',
            'vnet1_mtu': 'auto',
            'vnet2_mtu': 'auto',
            'vnet3_mtu': 'auto',
            'vnet_default_mtu': '1500',
        }

    def check_default_config(self):
        """This sets up the default configuration for jails."""
        default_json_location = f'{self.iocroot}/defaults.json'
        write = True  # Write the defaults file
        fix_write = False

        default_props = self.retrieve_default_props()

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
                self.backup_iocage_jail_conf(default_json_location)
                self.json_write(default_props, default_json_location,
                                defaults=True)

        return default_props


class IOCJson(IOCConfiguration):

    """
    Migrates old iocage configurations(UCL and ZFS Props) to the new JSON
    format, will set and get properties.
    """

    truthy_props = [
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

    default_only_props = [
        'nat_prefix',
        'nat_interface',
        'nat_backend',
    ]

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

        props = Dataset(dataset).properties

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
            ds = Dataset(os.path.join(dataset, 'root/data'))
            if ds.exists:
                ds.set_property('jailed', 'off')
                ds.rename(
                    os.path.join(dataset, 'data'), {'force_unmount': True}
                )
                ds.set_property(jail_zfs_prop, f'iocage/jails/{uuid}/data')
                ds.set_property('jailed', 'on')

        key_and_value["jail_zfs_dataset"] = f"iocage/jails/{uuid}/data"

        self.json_write(key_and_value)

    def json_load(self):
        """Load the JSON at the location given. Returns a JSON object."""
        jail_type, jail_uuid = self.location.rsplit("/", 2)[-2:]
        full_uuid = jail_uuid  # Saves jail_uuid for legacy ZFS migration
        legacy_short = False

        jail_dataset = Dataset(
            os.path.join(self.pool, 'iocage', jail_type, jail_uuid)
        )
        if not jail_dataset.exists:
            if os.path.isfile(os.path.join(self.location, 'config')):
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'EXCEPTION',
                        'message': 'iocage_legacy develop had a broken '
                                   'hack88 implementation.\nPlease '
                                   f'manually rename {jail_uuid} or '
                                   'destroy it with zfs.'
                    },
                    _callback=self.callback,
                    silent=self.silent)
            else:
                raise ioc_exceptions.JailMissingConfiguration(
                    f'{jail_type.rstrip("s").capitalize()}:'
                    f' {jail_uuid} has a missing configuration, please'
                    ' check that the dataset is mounted.'
                )

        skip = False

        if not jail_dataset.mounted:
            jail_dataset.mount()

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

                            jail_hostname = Dataset(
                                full_dataset
                            ).properties.get(
                                'org.freebsd.iocage:host_hostname', '-'
                            )

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
                            full_dataset_data = Dataset(f"{full_dataset}/data")
                            full_dataset_data.set_property('jailed', 'off')

                            full_dataset_obj = Dataset(full_dataset)

                            # We don't want to change a real hostname.
                            if jail_hostname == full_uuid:
                                full_dataset_obj.set_property(
                                    host_prop, short_uuid
                                )

                            full_dataset_obj.set_property(
                                uuid_prop, short_uuid
                            )
                            full_dataset_data.set_property(
                                jail_zfs_prop, os.path.join(
                                    'iocage/jails', short_uuid, 'data'
                                )
                            )
                            full_dataset_obj.rename(
                                short_dataset, {'force_unmount': True}
                            )
                            Dataset(
                                os.path.join(short_dataset, 'data')
                            ).set_property('jailed', 'on')

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
        if conf[1] and conf[0].get('host_hostuuid'):
            self.backup_iocage_jail_conf(
                os.path.join(self.location, 'config.json'),
            )

        return conf

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

                    ds = Dataset(_path)
                    if ds.exists:
                        origin = ds.properties.get('origin', '-')
                    else:
                        # Preserving old behavior
                        origin = None

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
                    jail_zfs_dataset = os.path.join(
                        self.pool, conf['jail_zfs_dataset']
                    )
                    jail_zfs_dataset_obj = Dataset(jail_zfs_dataset)
                    if jail_zfs_dataset_obj.exists:
                        jail_zfs_dataset_obj.set_property('jailed', 'off')

                    new_location_ds = Dataset(old_location)
                    new_location_ds.rename(
                        new_location, {'force_unmount': True}
                    )

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

                    new_location_ds.set_property('readonly', 'on')

                    return
                else:
                    if not _import:
                        ds = Dataset(new_location)
                        ds.rename(old_location, {'force_unmount': True})
                        conf["type"] = "jail"
                        self.location = old_location.lstrip(self.pool).replace(
                            "/iocage", self.iocroot)
                        ds.set_property('readonly', 'off')

                        self.json_check_prop(key, value, conf, default)
                        self.json_write(conf)

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
            'nat_forwards': ('string', ),
            'plugin_name': ('string', ),
            'plugin_repository': ('string', ),
            'min_dyn_devfs_ruleset': ('string', ),
            "vnet0_mtu": ("string", ),
            "vnet1_mtu": ("string", ),
            "vnet2_mtu": ("string", ),
            "vnet3_mtu": ("string", ),
            "vnet_default_mtu": ("string", ),
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

        if key in self.default_only_props:
            if not default:
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'EXCEPTION',
                        'message': f'{key} can only be changed for defaults!'
                    },
                    _callback=self.callback,
                    silent=self.silent)

            active_nat_jails = iocage_lib.ioc_common.get_jails_with_config(
                lambda j: (j['state'] == 'up' and j['nat'])
            )
            active_jails_msg = '\n'.join(
                f'   - {jail}' for jail in active_nat_jails
            )
            if active_nat_jails:
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'EXCEPTION',
                        'message': f'{key} cannot be changed with active '
                        'NAT jails. Please stop the following active jails.\n'
                        f'{active_jails_msg}'
                    }
                )

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

            Dataset(
                os.path.join(self.pool, 'iocage', _type, uuid)
            ).set_property(key, value)

            return value, conf

        elif key in props.keys():
            # Either it contains what we expect, or it's a string.

            if props[key] == truth_variations:
                if key in ('nat', 'bpf'):
                    other_key = 'nat' if key == 'bpf' else 'bpf'
                    if (
                        iocage_lib.ioc_common.check_truthy(value) and
                        iocage_lib.ioc_common.check_truthy(conf.get(other_key))
                    ):
                        iocage_lib.ioc_common.logit(
                            {
                                'level': 'EXCEPTION',
                                'message': f'{other_key} should be disabled '
                                f'when {key} is being enabled.'
                            }
                        )

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
                            if key == 'ip4_addr':
                                IOCJson.validate_ip4_addr(ip)
                            else:
                                IOCJson.validate_ip6_addr(ip)
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
                            r'^(tcp|udp|tcp\/udp)\(\d{1,5}((:|-?)(\d{1,5}))\)'
                        )
                        for fwd in value.split(','):
                            # We assume TCP for simpler inputs
                            fwd = f'tcp({fwd})' if fwd.isdigit() else fwd
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
                elif key in ('devfs_ruleset', 'min_dyn_devfs_ruleset'):
                    try:
                        intval = int(value)
                        if intval < 0:
                            raise ValueError()
                        conf[key] = str(intval)
                    except ValueError:
                        iocage_lib.ioc_common.logit(
                            {
                                'level': 'EXCEPTION',
                                'message': f'Invalid {key} value: {value}'
                            },
                            _callback=self.callback,
                            silent=self.silent,
                            exception=ioc_exceptions.ValidationFailed
                        )
                elif key == 'mac_prefix':
                    # Invalid letters - 0,1,3,4,5,7,8,9,B,C,D,F
                    # Valid letters - 2,6,A,E
                    if not self.validate_mac_prefix(value):
                        iocage_lib.ioc_common.logit(
                            {
                                'level': 'EXCEPTION',
                                'message': 'Invalid mac_prefix. Must match '
                                           '`?X????` where ? can be any '
                                           'valid hex digit (0-9, A-F) and '
                                           'X is one of 2, 6, A or E.'
                            },
                            _callback=self.callback,
                            silent=self.silent
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
        _path = Dataset(f"{self.pool}/iocage/jails/{uuid}").path

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
                        output = iocage_lib.ioc_common.consume_and_log(
                            _exec,
                            log=False
                        )
                        return (output['stdout'][0]).rstrip("\n") if output['stdout'] else ''
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
        _path = Dataset(f"{self.pool}/iocage/jails/{uuid}").path
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

                    # Can't rename when the child is
                    # in a non-global zone
                    jail_parent_ds = f"{self.pool}/iocage/jails/{uuid}"
                    jail_parent_data_obj = Dataset(
                        os.path.join(jail_parent_ds, 'data')
                    )
                    if jail_parent_data_obj.exists:
                        jail_parent_data_obj.set_property('jailed', 'off')

                    jail = Dataset(jail_parent_ds)
                    snap = Snapshot(f'{jail_parent_ds}@{tag}')
                    if snap.exists:
                        iocage_lib.ioc_common.logit(
                            {
                                'level': 'EXCEPTION',
                                'message': f'Snapshot {snap.resource_name}'
                                           'already exists'
                            },
                            _callback=self.callback, silent=self.silent
                        )
                    jail.create_snapshot(
                        f'{jail_parent_ds}@{tag}', {'recursive': True}
                    )

                    for snap in jail.snapshots_recursive():
                        snap_name = snap.name

                        # We only want our snapshot for this, the rest will
                        # follow

                        if snap_name == tag:
                            new_dataset = snap.resource_name.replace(
                                uuid, tag
                            ).split('@')[0]
                            snap.clone(new_dataset)

                    # Datasets are not mounted upon creation
                    new_jail_parent_ds = f"{self.pool}/iocage/jails/{tag}"
                    new_jail = Dataset(new_jail_parent_ds)
                    if not new_jail.mounted:
                        new_jail.mount()
                    new_jail.promote()

                    for new_ds in new_jail.get_dependents(depth=None):
                        if not new_ds.mounted:
                            new_ds.mount()
                        new_ds.promote()

                    # Easier.
                    su.check_call([
                        "zfs", "rename", "-r", f"{self.pool}/iocage@{uuid}",
                        f"@{tag}"
                    ])

                    new_jail_parent_ds_obj = Dataset(
                        os.path.join(new_jail_parent_ds, 'data')
                    )
                    if new_jail_parent_ds_obj.exists:
                        new_jail_parent_ds_obj.set_property('jailed', 'on')

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

                    jail.destroy(recursive=True, force=True)

                    try:
                        shutil.rmtree(f"{self.iocroot}/jails/{uuid}")
                    except Exception:
                        # Sometimes it becomes a directory when legacy short
                        # UUIDs are involved
                        pass

                    # Cleanup our snapshot from the cloning process

                    for snap in new_jail.snapshots_recursive():
                        snap_name = snap.name

                        if snap_name == tag:
                            snap.destroy()

                except Exception:
                    # A template, already renamed to a TAG
                    pass

        conf["host_hostuuid"] = tag

        if conf["host_hostname"] == uuid:
            # They may have set their own, we don't want to trample it.
            conf["host_hostname"] = tag

        return (conf, False, True)

    @staticmethod
    def validate_ip4_addr(ip):
        # PTP configurations have two addresses.  Otherwise there will be 1.
        parts = ip.split(" ")
        if len(parts) > 2:
            raise ValueError("Unrecognized IP4 address format")
        if len(parts) == 2:
            ipaddress.IPv4Address(parts[1])
        ipaddress.IPv4Network(parts[0], strict=False)

    @staticmethod
    def validate_ip6_addr(ip):
        # PTP configurations have two addresses.  Otherwise there will be 1.
        parts = ip.split(" ")
        if len(parts) > 2:
            raise ValueError("Unrecognized IP6 address format")
        if len(parts) == 2:
            ipaddress.IPv6Address(parts[1])
        ipaddress.IPv6Network(parts[0], strict=False)
