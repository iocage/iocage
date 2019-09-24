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
"""This collects debug about all the iocage jails."""
import itertools
import os
import subprocess as su

import iocage_lib.ioc_json as ioc_json
import iocage_lib.ioc_list as ioc_list

from iocage_lib.dataset import Dataset
from iocage_lib.pools import PoolListableResource


class IOCDebug(object):
    """
    Collects the following debug for a system + jails/templates:
        Host side
        ----------
        zfs list
        mount
        df -h

        Jail side
        ----------
        iocage get all
        /etc/hosts
        /etc/rc.conf
        /etc/nsswitch.conf
        ifconfig -a
        netstat -nr
        /etc/resolv.conf
    """

    def __init__(self, path, silent=False, callback=None):
        self.pool = ioc_json.IOCJson(' ').json_get_value('pool')
        self.path = path
        self.callback = callback
        self.silent = silent

    def run_debug(self):
        os.makedirs(self.path, exist_ok=True)
        self.run_host_debug()

        jails = Dataset(
            os.path.join(self.pool, 'iocage/jails')
        ).get_dependents()
        templates = Dataset(
            os.path.join(self.pool, 'iocage/templates')
        ).get_dependents()

        for jail in jails:
            jail_path = jail.path
            jail = jail.name.rsplit('/', 1)[-1]

            self.run_jail_debug(jail, jail_path)

        for template in templates:
            template_path = template.path
            template = template.name.rsplit('/', 1)[-1]

            self.run_jail_debug(template, template_path)

    def run_host_debug(self):
        host_path = f'{self.path}/host'

        zfs_datasets = (
            z.name for z in itertools.chain(*(
                p.datasets for p in PoolListableResource()
            ))
        )
        mounted_filesystems = self.__execute_debug__('/sbin/mount')
        df = self.__execute_debug__(['df', '-h'])
        netstat = self.__execute_debug__(['netstat', '-nr'])

        self.__write_debug__(zfs_datasets, host_path, 'ZFS', method='w')
        self.__write_debug__(mounted_filesystems, host_path, '\nMOUNT')
        self.__write_debug__(df, host_path, '\nDF -h')
        self.__write_debug__(netstat, host_path, '\nNETSTAT -nr')

    def run_jail_debug(self, name, path):
        jail_debug_path = f'{self.path}/{name}'
        jail_path = f'{path}/root'

        all_props = self.__get_jail_props__(name, path)
        fstab = self.__execute_debug__(['cat', f'{path}/fstab'], jail=name)
        hosts = self.__execute_debug__(['cat', f'{jail_path}/etc/hosts'],
                                       jail=name)
        rc = self.__execute_debug__(['cat', f'{jail_path}/etc/rc.conf'],
                                    jail=name)
        nsswitch = self.__execute_debug__(
            ['cat', f'{jail_path}/etc/nsswitch.conf'], jail=name
        )

        if all_props['state'] == 'up':
            ifconfig = self.__execute_debug__(['ifconfig', '-a'], jail=name,
                                              jexec=True)
            netstat = self.__execute_debug__(['netstat', '-nr'], jail=name,
                                             jexec=True)
        else:
            ifconfig = netstat = [f'{name} not running -- cannot run command']

        resolv = self.__execute_debug__(
            ['cat', f'{jail_path}/etc/resolv.conf'], jail=name
        )

        if all_props['state'] != 'CORRUPT':
            self.__write_debug__(all_props, jail_debug_path, 'PROPS',
                                 json=True, method='w')
        else:
            lines = [line.rstrip() for line in open(f'{path}/config.json')]
            self.__write_debug__(lines, jail_debug_path, 'PROPS - CORRUPT',
                                 method='w')

        self.__write_debug__(fstab, jail_debug_path, '\nFSTAB')
        self.__write_debug__(hosts, jail_debug_path, '\n/ETC/HOSTS')
        self.__write_debug__(rc, jail_debug_path, '\n/ETC/RC.CONF')
        self.__write_debug__(nsswitch, jail_debug_path, '\n/ETC/NSSWITCH.CONF')
        self.__write_debug__(ifconfig, jail_debug_path, '\nIFCONFIG -a')
        self.__write_debug__(netstat, jail_debug_path, '\nNETSTAT -nr')
        self.__write_debug__(resolv, jail_debug_path, '\n/ETC/RESOLV.CONF')

    def __execute_debug__(self, command, jail=None, jexec=False):
        if jail is not None and jexec:
            jail_cmd = ['jexec', f'ioc-{jail.replace(".", "_")}']
            command = jail_cmd + command

        cmd_stdout = su.run(command, stdout=su.PIPE, stderr=su.STDOUT)
        collection = (line.decode() for line in cmd_stdout.stdout.splitlines())

        return collection

    def __write_debug__(self, data, path, title, json=False, method='a+'):
        title_sep = '-' * 10

        with open(f'{path}.txt', method) as f:
            f.write(title)
            f.write(f'\n{title_sep}\n')

            if json:
                for key, val in data.items():
                    f.write(f'{key} = {val}\n')
            else:
                for line in data:
                    f.write(f'{line}\n')

    def __get_jail_props__(self, name, path):
        """Avoids a circular dep with iocage_lib.ioc"""
        _props = {}
        status, jid = ioc_list.IOCList().list_get_jid(name)
        state = 'up' if status else 'down'

        try:
            props = ioc_json.IOCJson(path).json_get_value('all')
        except (Exception, SystemExit):
            # Jail is corrupt, we want all the keys to exist.
            _props['state'] = 'CORRUPT'

            return _props

        # We want this sorted below, so we add it to the old dict
        props['state'] = state

        for key in sorted(props.keys()):
            _props[key] = props[key]

        return _props
