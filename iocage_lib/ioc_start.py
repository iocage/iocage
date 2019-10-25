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
"""This is responsible for starting jails."""
import datetime
import hashlib
import os
import re
import fcntl
import itertools
import shutil
import json
import subprocess as su
import netifaces
import ipaddress
import logging

import iocage_lib.ioc_common
import iocage_lib.ioc_exec
import iocage_lib.ioc_json
import iocage_lib.ioc_list
import iocage_lib.ioc_stop
import iocage_lib.ioc_exceptions as ioc_exceptions


class IOCStart(object):

    """
    Starts jails, the network stack for the jail and generates a resolv file

    for them. It also finds any scripts the user supplies for exec_*
    """

    def __init__(
        self, uuid, path, silent=False, callback=None, is_depend=False,
        unit_test=False, suppress_exception=False, used_ports=None
    ):
        self.jail_uuid = uuid
        self.uuid = uuid.replace(".", "_")
        self.path = path
        self.callback = callback
        self.silent = silent
        self.is_depend = is_depend
        self.unit_test = unit_test
        self.ip4_addr = 'none'
        self.ip6_addr = 'none'
        self.defaultrouter = 'auto'
        self.defaultrouter6 = 'auto'
        self.log = logging.getLogger('iocage')
        self.used_ports = used_ports or []

        if not self.unit_test:
            self.conf = iocage_lib.ioc_json.IOCJson(path).json_get_value('all')
            self.pool = iocage_lib.ioc_json.IOCJson(" ").json_get_value("pool")
            self.iocroot = iocage_lib.ioc_json.IOCJson(
                self.pool).json_get_value("iocroot")
            self.get = iocage_lib.ioc_json.IOCJson(self.path,
                                                   silent=True).json_get_value
            self.set = iocage_lib.ioc_json.IOCJson(self.path,
                                                   silent=True).json_set_value

            self.exec_fib = self.conf["exec_fib"]
            try:
                self.__start_jail__()
            except (Exception, SystemExit) as e:
                if not suppress_exception:
                    raise e

    def __start_jail__(self):
        """
        Takes a UUID, and the user supplied name of a jail, the path and the
        configuration location. It then supplies the jail utility with that
        information in a format it can parse.

        start_jail also checks if the jail is already running, if the
        user wished for procfs or linprocfs to be mounted, and the user's
        specified data that is meant to populate resolv.conf
        will be copied into the jail.
        """
        status, _ = iocage_lib.ioc_list.IOCList().list_get_jid(self.uuid)
        userland_version = float(os.uname()[2].partition("-")[0])

        # If the jail is not running, let's do this thing.

        if status:
            msg = f"{self.uuid} is already running!"
            iocage_lib.ioc_common.logit({
                "level": "EXCEPTION",
                "message": msg,
                "force_raise": self.is_depend
            }, _callback=self.callback,
                silent=self.silent,
                exception=ioc_exceptions.JailRunning)

        if self.conf['hostid_strict_check']:
            with open("/etc/hostid", "r") as _file:
                hostid = _file.read().strip()
            if self.conf["hostid"] != hostid:
                iocage_lib.ioc_common.logit({
                    "level": "ERROR",
                    "message": f"{self.uuid} hostid is not matching and"
                               " 'hostid_strict_check' is on!"
                               " - Not starting jail"
                }, _callback=self.callback, silent=self.silent)
                return

        mount_procfs = self.conf["mount_procfs"]
        host_domainname = self.conf["host_domainname"]
        host_hostname = self.conf["host_hostname"]
        securelevel = self.conf["securelevel"]
        enforce_statfs = self.conf["enforce_statfs"]
        children_max = self.conf["children_max"]
        allow_set_hostname = self.conf["allow_set_hostname"]
        allow_sysvipc = self.conf["allow_sysvipc"]
        allow_raw_sockets = self.conf["allow_raw_sockets"]
        allow_chflags = self.conf["allow_chflags"]
        allow_mlock = self.conf["allow_mlock"]
        allow_mount = self.conf["allow_mount"]
        allow_mount_devfs = self.conf["allow_mount_devfs"]
        allow_mount_fusefs = self.conf["allow_mount_fusefs"]
        allow_mount_nullfs = self.conf["allow_mount_nullfs"]
        allow_mount_procfs = self.conf["allow_mount_procfs"]
        allow_mount_linprocfs = self.conf["allow_mount_linprocfs"]
        allow_mount_tmpfs = self.conf["allow_mount_tmpfs"]
        allow_mount_zfs = self.conf["allow_mount_zfs"]
        allow_quotas = self.conf["allow_quotas"]
        allow_socket_af = self.conf["allow_socket_af"]
        allow_vmm = self.conf["allow_vmm"]
        exec_prestart = self.conf["exec_prestart"]
        exec_poststart = self.conf["exec_poststart"]
        exec_clean = self.conf["exec_clean"]
        exec_created = self.conf["exec_created"]
        exec_timeout = self.conf["exec_timeout"]
        stop_timeout = self.conf["stop_timeout"]
        mount_devfs = self.conf["mount_devfs"]
        mount_fdescfs = self.conf["mount_fdescfs"]
        sysvmsg = self.conf["sysvmsg"]
        sysvsem = self.conf["sysvsem"]
        sysvshm = self.conf["sysvshm"]
        bpf = self.conf["bpf"]
        dhcp = self.conf["dhcp"]
        rtsold = self.conf['rtsold']
        self.ip4_addr = self.conf['ip4_addr']
        self.ip6_addr = self.conf["ip6_addr"]
        wants_dhcp = True if dhcp or 'DHCP' in self.ip4_addr.upper() else False
        vnet_interfaces = self.conf["vnet_interfaces"]
        nat = self.conf['nat']
        nat_interface = self.conf['nat_interface']
        nat_backend = self.conf['nat_backend']
        nat_forwards = self.conf['nat_forwards']
        ip_hostname = self.conf['ip_hostname']
        prop_missing = False
        prop_missing_msgs = []
        debug_mode = True if os.environ.get(
            'IOCAGE_DEBUG', 'FALSE') == 'TRUE' else False
        assign_localhost = self.conf['assign_localhost']
        localhost_ip = self.conf['localhost_ip']
        self.defaultrouter = self.conf['defaultrouter']
        self.defaultrouter6 = self.conf['defaultrouter6']
        self.host_gateways = iocage_lib.ioc_common.get_host_gateways()

        fstab_list = []
        with open(
                f'{self.iocroot}/jails/{self.jail_uuid}/fstab', 'r'
        ) as _fstab:
            for line in _fstab.readlines():
                line = line.rsplit("#")[0].rstrip()
                fstab_list.append(line)

        iocage_lib.ioc_fstab.IOCFstab(
            self.jail_uuid,
            'list'
        ).__validate_fstab__(fstab_list, 'all')

        if wants_dhcp:
            if not bpf:
                prop_missing_msgs.append(
                    f"{self.uuid}: dhcp requires bpf!"
                )
                prop_missing = True
            elif not self.conf['vnet']:
                # We are already setting a vnet variable below.
                prop_missing_msgs.append(
                    f"{self.uuid}: dhcp requires vnet!"
                )
                prop_missing = True

        if nat and nat_forwards != 'none':
            # If NAT is enabled and nat port forwarding as well,
            # we want to make sure that the current jail's port forwarding
            # does not conflict with other running jail's nat_forwards

            if set(int(v[-1]) for v in self.__parse_nat_fwds__(
                nat_forwards
            )) & set(itertools.chain(
                *iocage_lib.ioc_common.get_jails_with_config(
                    lambda j: (j['state'] == 'up' and j['nat'] and
                               j['nat_forwards'] != 'none'),
                    lambda j: [
                        int(v[-1]) for v in
                        self.__parse_nat_fwds__(
                            j['nat_forwards']
                        )
                    ]
                ).values(), self.used_ports
            )):
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'EXCEPTION',
                        'message': f'Please correct {nat_forwards} port rule '
                        'as another running jail is using one of the '
                        'mentioned ports.'
                    }
                )

        if nat and nat_interface == 'none':
            self.log.debug('Grabbing default route\'s interface')
            nat_interface = self.get_default_interface()
            self.log.debug(f'Interface: {nat_interface}')

            iocage_lib.ioc_common.logit({
                'level': 'WARNING',
                'message': f'{self.uuid}: nat requires nat_interface,'
                           f' using {nat_interface}'
            }, _callback=self.callback,
                silent=self.silent)

        if self.conf['vnet'] and self.defaultrouter == 'auto':
            self.log.debug('Grabbing IPv4 default route')
            self.defaultrouter = self.get_default_gateway('ipv4')
            self.log.debug(f'Default IPv4 Gateway: {self.defaultrouter}')

        if self.conf['vnet'] and self.defaultrouter6 == 'auto':
            self.log.debug('Grabbing IPv6 default route')
            self.defaultrouter6 = self.get_default_gateway('ipv6')
            self.log.debug(f'Default IPv6 Gateway: {self.defaultrouter6}')

        if 'accept_rtadv' in self.ip6_addr and not self.conf['vnet']:
            prop_missing_msgs.append(
                f'{self.uuid}: accept_rtadv requires vnet!'
            )
            prop_missing = True

        if bpf and not self.conf['vnet']:
            prop_missing_msgs.append(f'{self.uuid}: bpf requires vnet!')
            prop_missing = True

        if prop_missing:
            iocage_lib.ioc_common.logit({
                "level": "EXCEPTION",
                "message": '\n'.join(prop_missing_msgs)
            }, _callback=self.callback,
                silent=self.silent)

        self.__check_dhcp_or_accept_rtadv__(ipv4=True, enable=wants_dhcp)

        if rtsold:
            self.__check_rtsold__()

        self.__check_dhcp_or_accept_rtadv__(ipv4=False, enable='accept_rtadv' in self.ip6_addr)

        if mount_procfs:
            su.Popen(
                [
                    'mount', '-t', 'procfs', 'proc', f'{self.path}/root/proc'
                ]
            ).communicate()

        try:
            mount_linprocfs = self.conf["mount_linprocfs"]

            if mount_linprocfs:
                if not os.path.isdir(f"{self.path}/root/compat/linux/proc"):
                    os.makedirs(f"{self.path}/root/compat/linux/proc", 0o755)
                su.Popen(
                    [
                        'mount', '-t', 'linprocfs', 'linproc',
                        f'{self.path}/root/compat/linux/proc'
                    ]
                ).communicate()
        except Exception:
            pass

        if self.conf['jail_zfs']:
            allow_mount = "1"
            enforce_statfs = enforce_statfs if enforce_statfs != "2" \
                else "1"
            allow_mount_zfs = "1"

            for jdataset in self.conf["jail_zfs_dataset"].split():
                jdataset = jdataset.strip()

                try:
                    su.check_call(["zfs", "get", "-H", "creation",
                                   f"{self.pool}/{jdataset}"],
                                  stdout=su.PIPE, stderr=su.PIPE)
                except su.CalledProcessError:
                    iocage_lib.ioc_common.checkoutput(
                        ["zfs", "create", "-o",
                         "compression=lz4", "-o",
                         "mountpoint=none",
                         f"{self.pool}/{jdataset}"],
                        stderr=su.STDOUT)

                try:
                    iocage_lib.ioc_common.checkoutput(
                        ["zfs", "set", "jailed=on",
                         f"{self.pool}/{jdataset}"],
                        stderr=su.STDOUT)
                except su.CalledProcessError as err:
                    raise RuntimeError(
                        f"{err.output.decode('utf-8').rstrip()}")

        # FreeBSD 9.3 and under do not support this.

        if userland_version <= 9.3:
            tmpfs = ""
            fdescfs = ""
        else:
            tmpfs = f"allow.mount.tmpfs={allow_mount_tmpfs}"
            fdescfs = f"mount.fdescfs={mount_fdescfs}"

        # FreeBSD 10.3 and under do not support this.

        if userland_version <= 10.3:
            _sysvmsg = ""
            _sysvsem = ""
            _sysvshm = ""
        else:
            _sysvmsg = f"sysvmsg={sysvmsg}"
            _sysvsem = f"sysvsem={sysvsem}"
            _sysvshm = f"sysvshm={sysvshm}"

        # FreeBSD before 12.0 does not support this.

        if userland_version < 12.0:
            _allow_mlock = ''
            _allow_mount_fusefs = ''
            _allow_vmm = ''
            _exec_created = ''
        else:
            _allow_mlock = f"allow.mlock={allow_mlock}"
            _allow_mount_fusefs = f"allow.mount.fusefs={allow_mount_fusefs}"
            _allow_vmm = f"allow.vmm={allow_vmm}"
            _exec_created = f'exec.created={exec_created}'

        if nat:
            self.log.debug(f'Checking NAT backend: {nat_backend}')
            self.__check_nat__(backend=nat_backend)

            if not self.conf['vnet']:
                self.log.debug('VNET is False')
                self.log.debug(
                    f'Generating IP from nat_prefix: {self.conf["nat_prefix"]}'
                )
                ip4_addr, _ = iocage_lib.ioc_common.gen_nat_ip(
                    self.conf['nat_prefix']
                )
                self.ip4_addr = f'{nat_interface}|{ip4_addr}'
                # Make this reality for list
                self.set(f'ip4_addr={self.ip4_addr}')
                self.log.debug(f'Received ip4_addr: {self.ip4_addr}')
            else:
                self.log.debug('VNET is True')
                self.log.debug(
                    f'Generating default_router and IP from nat_prefix:'
                    f' {self.conf["nat_prefix"]}'
                )
                self.defaultrouter, ip4_addr = \
                    iocage_lib.ioc_common.gen_nat_ip(
                        self.conf['nat_prefix']
                    )
                self.ip4_addr = f'vnet0|{ip4_addr}/30'
                # Make this reality for list
                self.set(f'ip4_addr={self.ip4_addr}')
                nat = self.defaultrouter
                # Make this reality for list
                self.set(f'defaultrouter={self.defaultrouter}')
                self.log.debug(f'Received default_router: {nat}')
                self.log.debug(f'Received ip4_addr: {self.ip4_addr}')

        if not self.conf['vnet']:
            ip4_saddrsel = self.conf['ip4_saddrsel']
            ip4 = self.conf['ip4']
            ip6_saddrsel = self.conf['ip6_saddrsel']
            ip6 = self.conf['ip6']
            net = []

            if assign_localhost:
                # Make sure this exists, jail(8) will tear it down if we don't
                # manually do this.
                if localhost_ip == 'none':
                    localhost_ip = iocage_lib.ioc_common.gen_unused_lo_ip()
                    self.set(f'localhost_ip={localhost_ip}')

                with open(
                        f'{self.path}/root/etc/hosts', 'r'
                ) as _etc_hosts:
                    with iocage_lib.ioc_common.open_atomic(
                            f'{self.path}/root/etc/hosts', 'w') as etc_hosts:
                        # open_atomic will empty the file, we need these still.
                        for line in _etc_hosts.readlines():
                            if line.startswith('127.0.0.1'):
                                line = line.replace('127.0.0.1', localhost_ip)

                            etc_hosts.write(line)

                if self.check_aliases(localhost_ip, '4') != localhost_ip:
                    su.run(['ifconfig', 'lo0', 'alias', f'{localhost_ip}/32'])
                else:
                    active_jail_ips = json.loads(su.run(
                        ['jls', '-n', 'ip4.addr', '--libxo=json'],
                        stdout=su.PIPE, stderr=su.PIPE
                    ).stdout)['jail-information']['jail']
                    active_jail_ips = [
                        ip.get('ip4.addr') for ip in active_jail_ips
                    ]

                    if localhost_ip in active_jail_ips:
                        iocage_lib.ioc_common.logit({
                            "level": "WARNING",
                            "message": f'  {self.uuid} is reusing a localhost'
                                       ' address, failure may occur!'
                        },
                            _callback=self.callback,
                            silent=self.silent)

                if self.ip4_addr == 'none':
                    self.ip4_addr = localhost_ip
                else:
                    self.ip4_addr += f',{localhost_ip}'

            if self.ip4_addr != 'none':
                self.ip4_addr = self.check_aliases(self.ip4_addr, '4')

                net.append(f'ip4.addr={self.ip4_addr}')

            if self.ip6_addr != 'none':
                self.ip6_addr = self.check_aliases(self.ip6_addr, '6')

                net.append(f'ip6.addr={self.ip6_addr}')

            net += [
                f'ip4.saddrsel={ip4_saddrsel}',
                f'ip4={ip4}',
                f'ip6.saddrsel={ip6_saddrsel}',
                f'ip6={ip6}'
            ]

            vnet = False
        else:
            net = ["vnet"]

            if vnet_interfaces != "none":
                for vnet_int in vnet_interfaces.split():
                    net += [f"vnet.interface={vnet_int}"]
            else:
                vnet_interfaces = ""

            vnet = True

        msg = f"* Starting {self.uuid}"
        iocage_lib.ioc_common.logit({
            "level": "INFO",
            "message": msg
        },
            _callback=self.callback,
            silent=self.silent)

        devfs_paths = None
        devfs_includes = None

        manifest_path = os.path.join(self.path, f'{self.conf["plugin_name"]}.json')
        if self.conf['type'] == 'pluginv2' and os.path.isfile(manifest_path):
            with open(manifest_path, 'r') as f:
                devfs_json = json.load(f)
            iocage_lib.ioc_common.validate_plugin_manifest(devfs_json, self.callback, self.silent)
            devfs_paths = devfs_json.get('devfs_ruleset', {}).get('paths')
            devfs_includes = devfs_json.get('devfs_ruleset', {}).get('includes')

        # Generate dynamic devfs ruleset from configured one
        (manual_devfs_config, configured_devfs_ruleset, devfs_ruleset) \
            = iocage_lib.ioc_common.generate_devfs_ruleset(
                self.conf, devfs_paths, devfs_includes)

        if int(devfs_ruleset) < 0:
            iocage_lib.ioc_common.logit({
                "level": "ERROR",
                "message": f"{self.uuid} devfs_ruleset"
                           f" {configured_devfs_ruleset} does not exist!"
                           " - Not starting jail"
            },
                _callback=self.callback,
                silent=self.silent)
            return

        # Manually configured devfs_ruleset doesn't support all iocage features
        if manual_devfs_config:
            if devfs_paths is not None or devfs_includes is not None:
                iocage_lib.ioc_common.logit({
                    "level": "WARNING",
                    "message": f"  {self.uuid} is not using the devfs_ruleset"
                               " of "
                               f"{iocage_lib.ioc_common.IOCAGE_DEVFS_RULESET}"
                               ", devices and includes from plugin not added"
                               ", some features of the plugin may not work."
                },
                    _callback=self.callback,
                    silent=self.silent)

            if wants_dhcp and self.conf['type'] != 'pluginv2':
                iocage_lib.ioc_common.logit({
                    "level": "WARNING",
                    "message": f"  {self.uuid} is not using the devfs_ruleset"
                               " of "
                               f"{iocage_lib.ioc_common.IOCAGE_DEVFS_RULESET}"
                               ", not generating a ruleset for the jail,"
                               " DHCP may not work."
                },
                    _callback=self.callback,
                    silent=self.silent)

        parameters = [
            fdescfs, _allow_mlock, tmpfs,
            _allow_mount_fusefs, _allow_vmm,
            f"allow.set_hostname={allow_set_hostname}",
            f"mount.devfs={mount_devfs}",
            f"allow.raw_sockets={allow_raw_sockets}",
            f"allow.sysvipc={allow_sysvipc}",
            f"allow.quotas={allow_quotas}",
            f"allow.socket_af={allow_socket_af}",
            f"allow.chflags={allow_chflags}",
            f"allow.mount={allow_mount}",
            f"allow.mount.devfs={allow_mount_devfs}",
            f"allow.mount.nullfs={allow_mount_nullfs}",
            f"allow.mount.procfs={allow_mount_procfs}",
            f"allow.mount.linprocfs={allow_mount_linprocfs}",
            f"allow.mount.zfs={allow_mount_zfs}"
        ]

        start_parameters = [
            x for x in net
            + [x for x in parameters if '1' in x]
            + [
                f'name=ioc-{self.uuid}',
                _sysvmsg,
                _sysvsem,
                _sysvshm,
                _exec_created,
                f'host.domainname={host_domainname}',
                f'host.hostname={host_hostname}',
                f'path={self.path}/root',
                f'securelevel={securelevel}',
                f'host.hostuuid={self.uuid}',
                f'devfs_ruleset={devfs_ruleset}',
                f'enforce_statfs={enforce_statfs}',
                f'children.max={children_max}',
                f'exec.clean={exec_clean}',
                f'exec.timeout={exec_timeout}',
                f'stop.timeout={stop_timeout}',
                f'mount.fstab={self.path}/fstab',
                'allow.dying',
                f'exec.consolelog={self.iocroot}/log/ioc-'
                f'{self.uuid}-console.log',
                f'ip_hostname={ip_hostname}' if ip_hostname else '',
                'persist'
            ] if x != '']

        # Write the config out to a file. We'll be starting the jail using this
        # config and it is required for stopping the jail too.
        jail = iocage_lib.ioc_json.JailRuntimeConfiguration(
            self.uuid, start_parameters
        )
        jail.sync_changes()

        start_cmd = ['jail']

        if debug_mode:
            start_cmd.append('-v')

        start_cmd += ['-f', f'/var/run/jail.ioc-{self.uuid}.conf', '-c']

        start_env = {
            **os.environ,
            "IOCAGE_HOSTNAME": f"{host_hostname}",
            "IOCAGE_NAME": f"ioc-{self.uuid}",
        }

        if nat:
            # We pass some environment variables to the shell script
            # for nat based jails currently aiding in doing jail specific
            # tasks in the host environment
            pre_start_env = {
                **os.environ,
                'INTERNAL_DEFAULT_ROUTER': self.defaultrouter,
                'INTERNAL_IP': self.ip4_addr.split(
                    ','
                )[0].split('|')[-1].split('/')[0]
            }
            default_gw_iface = self.host_gateways['ipv4']['interface']
            if default_gw_iface:
                gw_addresses = netifaces.ifaddresses(
                    default_gw_iface
                )[netifaces.AF_INET]
                if gw_addresses:
                    pre_start_env.update({
                        'EXT_HOST': gw_addresses[0]['addr'],
                        'EXT_BCAST': gw_addresses[0]['broadcast'],
                    })

            if vnet:
                pre_start_env[
                    'INTERNAL_BROADCAST_IP'
                ] = ipaddress.IPv4Network(
                    f'{pre_start_env["INTERNAL_IP"]}/30', False
                ).broadcast_address.exploded
            else:
                pre_start_env['INTERNAL_BROADCAST_IP'] = pre_start_env[
                    'INTERNAL_IP'
                ]
        else:
            pre_start_env = None

        prestart_success, prestart_error = iocage_lib.ioc_common.runscript(
            exec_prestart, pre_start_env
        )

        if prestart_error:
            iocage_lib.ioc_stop.IOCStop(
                self.uuid, self.path, force=True, silent=True
            )

            iocage_lib.ioc_common.logit({
                'level': 'EXCEPTION',
                'message': '  + Executing exec_prestart FAILED\n'
                           f'ERROR:\n{prestart_error}\n\nRefusing to '
                           f'start {self.uuid}: exec_prestart failed'
            },
                _callback=self.callback,
                silent=self.silent
            )

        start = su.Popen(
            start_cmd, stderr=su.PIPE,
            stdout=su.PIPE if not debug_mode else None,
            env=start_env
        )

        stdout_data, stderr_data = start.communicate()

        if start.returncode:
            # This is actually fatal.
            msg = "  + Start FAILED"
            iocage_lib.ioc_common.logit({
                "level": "ERROR",
                "message": msg
            },
                _callback=self.callback,
                silent=self.silent)

            iocage_lib.ioc_common.logit({
                "level": "EXCEPTION",
                "message": stderr_data.decode('utf-8')
            }, _callback=self.callback,
                silent=self.silent)
        else:
            iocage_lib.ioc_common.logit({
                "level": "INFO",
                "message": "  + Started OK"
            },
                _callback=self.callback,
                silent=self.silent)

        iocage_lib.ioc_common.logit({
            'level': 'INFO',
            'message': f'  + Using devfs_ruleset: {devfs_ruleset}'
                       + (' (cloned from devfs_ruleset '
                          f'{configured_devfs_ruleset})' if manual_devfs_config
                          else ' (iocage generated default)')
        },
            _callback=self.callback,
            silent=self.silent)

        os_path = f"{self.path}/root/dev/log"

        if not os.path.isfile(os_path) and not os.path.islink(os_path):
            os.symlink("../var/run/log", os_path)

        vnet_err = self.start_network(vnet, nat)

        if not vnet_err and vnet:
            iocage_lib.ioc_common.logit({
                "level": "INFO",
                "message": "  + Configuring VNET OK"
            },
                _callback=self.callback,
                silent=self.silent)

        elif vnet_err and vnet:
            iocage_lib.ioc_common.logit({
                "level": "ERROR",
                "message": "  + Configuring VNET FAILED"
            },
                _callback=self.callback,
                silent=self.silent)

            for v_err in vnet_err:
                iocage_lib.ioc_common.logit({
                    "level": "ERROR",
                    "message": f"  {v_err}"
                },
                    _callback=self.callback,
                    silent=self.silent)

            iocage_lib.ioc_stop.IOCStop(
                self.uuid, self.path, force=True, silent=True
            )

            iocage_lib.ioc_common.logit({
                "level": "EXCEPTION",
                "message": f"\nStopped {self.uuid} due to VNET failure"
            },
                _callback=self.callback)

        if net:
            iocage_lib.ioc_common.logit({
                'level': 'INFO',
                'message': f'  + Using IP options: {" ".join(net)}'
            },
                _callback=self.callback,
                silent=self.silent)

        if self.conf['jail_zfs']:
            for jdataset in self.conf["jail_zfs_dataset"].split():
                jdataset = jdataset.strip()
                children = iocage_lib.ioc_common.checkoutput(
                    ["zfs", "list", "-H", "-r", "-o",
                     "name", "-s", "name",
                     f"{self.pool}/{jdataset}"])

                try:
                    iocage_lib.ioc_common.checkoutput(
                        ["zfs", "jail", "ioc-{}".format(self.uuid),
                         "{}/{}".format(self.pool, jdataset)],
                        stderr=su.STDOUT)
                except su.CalledProcessError as err:
                    raise RuntimeError(
                        f"{err.output.decode('utf-8').rstrip()}")

                for child in children.split():
                    child = child.strip()

                    try:
                        mountpoint = iocage_lib.ioc_common.checkoutput(
                            ["zfs", "get", "-H",
                             "-o",
                             "value", "mountpoint",
                             f"{self.pool}/{jdataset}"]).strip()

                        if mountpoint != "none":
                            iocage_lib.ioc_common.checkoutput(
                                ["setfib", self.exec_fib, "jexec",
                                 f"ioc-{self.uuid}", "zfs",
                                 "mount", child], stderr=su.STDOUT)
                    except su.CalledProcessError as err:
                        msg = err.output.decode('utf-8').rstrip()
                        iocage_lib.ioc_common.logit({
                            "level": "EXCEPTION",
                            "message": msg
                        },
                            _callback=self.callback,
                            silent=self.silent)

        self.start_generate_resolv()
        self.start_copy_localtime()

        if nat:
            self.log.debug(
                f'Adding NAT: Interface - {nat_interface}'
                f' Forwards - {nat_forwards} Backend - {nat_backend}'
            )
            # We use a lock here to ensure that two jails at the same
            # time do not attempt to write nat rules
            with open('/tmp/iocage_nat_lock', 'w') as f:
                # Lock is automatically released when file is closed
                fcntl.flock(f, fcntl.LOCK_EX)
                self.__add_nat__(nat_interface, nat_forwards, nat_backend)

        # This needs to be a list.
        exec_start = self.conf['exec_start'].split()

        with open(
            f'{self.iocroot}/log/{self.uuid}-console.log', 'a'
        ) as f:
            success, error = '', ''
            try:
                output = iocage_lib.ioc_exec.SilentExec(
                    ['setfib', self.exec_fib, 'jexec', f'ioc-{self.uuid}']
                    + exec_start, None, unjailed=True, decode=True
                )
                if self.get('rtsold') or 'accept_rtadv' in self.ip6_addr:
                    # rtsold(8) does not start even with rtsold_enable
                    try:
                        iocage_lib.ioc_exec.SilentExec(
                            [
                                'setfib', self.exec_fib, 'jexec',
                                f'ioc-{self.uuid}', 'service', 'rtsold',
                                'start'
                            ], None, unjailed=True
                        )
                    except ioc_exceptions.CommandFailed:
                        pass
            except ioc_exceptions.CommandFailed as e:

                error = str(e)
                iocage_lib.ioc_stop.IOCStop(
                    self.uuid, self.path, force=True, silent=True
                )

                msg = f'  + Starting services FAILED\nERROR:\n{error}\n\n' \
                    f'Refusing to start {self.uuid}: exec_start failed'
                iocage_lib.ioc_common.logit({
                    'level': 'EXCEPTION',
                    'message': msg
                },
                    _callback=self.callback,
                    silent=self.silent
                )
            else:
                success = output.stdout
                msg = '  + Starting services OK'
                iocage_lib.ioc_common.logit({
                    'level': 'INFO',
                    'message': msg
                },
                    _callback=self.callback,
                    silent=self.silent
                )
            finally:
                f.write(f'{success}\n{error}')

        # Running exec_poststart now
        poststart_success, poststart_error = \
            iocage_lib.ioc_common.runscript(
                exec_poststart
            )

        if poststart_error:

            iocage_lib.ioc_stop.IOCStop(
                self.uuid, self.path, force=True, silent=True
            )

            iocage_lib.ioc_common.logit({
                'level': 'EXCEPTION',
                'message': '  + Executing exec_poststart FAILED\n'
                f'ERROR:\n{poststart_error}\n\nRefusing to '
                f'start {self.uuid}: exec_poststart failed'
            },
                _callback=self.callback,
                silent=self.silent
            )

        else:
            iocage_lib.ioc_common.logit({
                'level': 'INFO',
                'message': '  + Executing poststart OK'
            },
                _callback=self.callback,
                silent=self.silent
            )

        if not vnet_err and vnet and wants_dhcp:
            failed_dhcp = False

            try:
                interface = self.conf['interfaces'].split(',')[0].split(
                    ':')[0]

                if 'vnet' in interface:
                    # Jails default is epairNb
                    interface = f'{interface.replace("vnet", "epair")}b'

                # We'd like to use ifconfig -f inet:cidr here,
                # but only FreeBSD 11.0 and newer support it...
                cmd = ['jexec', f'ioc-{self.uuid}', 'ifconfig',
                       interface, 'inet']
                out = su.check_output(cmd)

                # ...so we extract the ip4 address and mask,
                # and calculate cidr manually
                addr_split = out.splitlines()[2].split()
                self.ip4_addr = addr_split[1].decode()
                hexmask = addr_split[3].decode()
                maskcidr = sum([bin(int(hexmask, 16)).count('1')])

                addr = f'{self.ip4_addr}/{maskcidr}'

                if '0.0.0.0' in addr:
                    failed_dhcp = True

            except (su.CalledProcessError, IndexError):
                failed_dhcp = True
                addr = 'ERROR, check jail logs'

            if failed_dhcp:
                iocage_lib.ioc_stop.IOCStop(
                    self.uuid, self.path, force=True, silent=True
                )

                iocage_lib.ioc_common.logit({
                    'level': 'EXCEPTION',
                    'message': '  + Acquiring DHCP address: FAILED,'
                    f' address received: {addr}\n'
                    f'\nStopped {self.uuid} due to DHCP failure'
                },
                    _callback=self.callback)

            iocage_lib.ioc_common.logit({
                'level': 'INFO',
                'message': f'  + DHCP Address: {addr}'
            },
                _callback=self.callback,
                silent=self.silent)

        self.set(
            "last_started={}".format(
                datetime.datetime.utcnow().strftime("%F %T")
            )
        )

        rctl_keys = set(
            filter(
                lambda k: self.conf.get(k, 'off') != 'off',
                iocage_lib.ioc_json.IOCRCTL.types
            )
        )
        if rctl_keys:

            # We should remove any rules specified for this jail for just in
            # case cases
            rctl_jail = iocage_lib.ioc_json.IOCRCTL(self.uuid)
            rctl_jail.validate_rctl_tunable()

            rctl_jail.remove_rctl_rules()

            # Let's set the specified rules
            iocage_lib.ioc_common.logit({
                'level': 'INFO',
                'message': '  + Setting RCTL props'
            })

            failed = rctl_jail.set_rctl_rules(
                [(k, self.conf[k]) for k in rctl_keys]
            )

            if failed:
                iocage_lib.ioc_common.logit({
                    'level': 'ERROR',
                    'message': f'  + Failed to set {", ".join(failed)} '
                    'RCTL props'
                })

        cpuset = self.conf.get('cpuset', 'off')
        if cpuset != 'off':
            # Let's set the specified rules
            iocage_lib.ioc_common.logit({
                'level': 'INFO',
                'message': f'  + Setting cpuset to: {cpuset}'
            })

            cpuset_jail = iocage_lib.ioc_json.IOCCpuset(self.uuid)
            cpuset_jail.validate_cpuset_prop(cpuset)

            failed = cpuset_jail.set_cpuset(cpuset)
            if failed:
                iocage_lib.ioc_common.logit({
                    'level': 'ERROR',
                    'message': f'  + Failed to set cpuset to: {cpuset}'
                })

    def check_aliases(self, ip_addrs, mode='4'):
        """
        Check if the alias already exists for given IP's, otherwise add
        default interface to the ips and return the new list
        """

        inet_mode = netifaces.AF_INET if mode == '4' else netifaces.AF_INET6
        gws = netifaces.gateways()

        try:
            def_iface = gws['default'][inet_mode][1]
        except KeyError:
            # They have no default gateway for mode 4|6
            return ip_addrs

        _ip_addrs = ip_addrs.split(',')
        interfaces_to_skip = ('vnet', 'bridge', 'epair', 'pflog')
        current_ips = []
        new_ips = []

        # We want to make sure they haven't already created
        # this alias
        for interface in netifaces.interfaces():
            if interface.startswith(interfaces_to_skip):
                continue

            with ioc_exceptions.ignore_exceptions(KeyError):
                for address in netifaces.ifaddresses(interface)[inet_mode]:
                    current_ips.append(address['addr'])

        for ip in _ip_addrs:
            if '|' not in ip:
                ip = ip if ip in current_ips else f'{def_iface}|{ip}'

            new_ips.append(ip)

        return ','.join(new_ips)

    def start_network(self, vnet, nat=False):
        """
        This function is largely a check to see if VNET is true, and then to
        actually run the correct function, otherwise it passes.

        :param vnet: Boolean
        """
        errors = []

        if not vnet:
            return

        _, jid = iocage_lib.ioc_list.IOCList().list_get_jid(self.uuid)
        net_configs = (
            (self.ip4_addr, self.defaultrouter, False),
            (self.ip6_addr, self.defaultrouter6, True))
        nics = self.get("interfaces").split(",")

        vnet_default_interface = self.get('vnet_default_interface')
        if (
                vnet_default_interface != 'auto'
                and vnet_default_interface != 'none'
                and vnet_default_interface not in netifaces.interfaces()
        ):
            # Let's not go into starting a vnet at all if the default
            # interface is supplied incorrectly
            return [
                'Set property "vnet_default_interface" to "auto", "none" or a'
                'valid interface e.g "lagg0"'
            ]

        for nic in nics:
            err = self.start_network_interface_vnet(nic, net_configs, jid, nat)

            if err:
                errors.extend(err)

        if not errors:
            # There have been no errors reported for any interface
            # Let's setup default route as specified
            dhcp = self.get('dhcp')
            wants_dhcp = dhcp or 'DHCP' in self.ip4_addr.upper()
            skip_accepts_rtadv = 'accept_rtadv' not in self.ip6_addr.lower()
            for ip, default_route, ipv6 in map(lambda v: v[1], filter(
                lambda v: v[0] and v[1][0] != 'none' and v[1][1] != 'none',
                zip((not wants_dhcp, skip_accepts_rtadv), net_configs)
            )):
                # TODO: Scope/zone id should be investigated further
                #  to make sure no case is missed wrt this
                if ipv6 and '%' in default_route:
                    # When we have ipv6, it is possible that default route
                    # is "fe80::20d:b9ff:fe33:8716%interface0"
                    # Now interface here is default gateway of the host
                    # machine which the jail isn't aware of. In the jail
                    # when adding default route, the value of interface
                    # should be the default gateway of the jail. Let's
                    # correct that behavior.
                    defined_interfaces = [i.split(':') for i in nics]
                    specified_interfaces = [
                        'vnet0' if '|' not in i else i.split('|')[0]
                        for i in ip
                    ]
                    # The default gateway here for the jail would be the
                    # one which is present first in "defined_interfaces"
                    # and also in "specified_interfaces".
                    default_gw = 'vnet0'  # Defaulting to vnet0
                    for i in defined_interfaces:
                        if i in specified_interfaces:
                            default_gw = i
                            break
                    default_route = f'{default_route.split("%")[0]}' \
                        f'%{default_gw.replace("vnet", "epair")}b'

                self.log.debug(f'Setting default route {default_route}')

                try:
                    iocage_lib.ioc_common.checkoutput(
                        [
                            'setfib', self.exec_fib, 'jexec',
                            f'ioc-{self.uuid}',
                            'route'
                        ] + list(
                            filter(
                                bool, [
                                    'add', '-6' if ipv6 else '',
                                    'default', default_route
                                ]
                            )
                        ),
                        stderr=su.STDOUT
                    )
                except su.CalledProcessError as err:
                    errors.append(f'{err.output.decode("utf-8")}'.rstrip())

        if len(errors) != 0:
            return errors

    def start_network_interface_vnet(
        self, nic_defs, net_configs, jid, nat_addr=0
    ):
        """
        Start VNET on interface

        :param nic_defs: comma separated interface definitions (nic, bridge)
        :param net_configs: Tuple of IP address and router pairs
        :param jid: The jails ID
        """
        errors = []

        nic_defs = nic_defs.split(",")
        nics = list(map(lambda x: x.split(":")[0], nic_defs))

        for nic_def in nic_defs:

            nic, bridge = nic_def.split(":")

            try:
                if self.get(f"{nic}_mtu") != 'auto':
                    membermtu = self.get(f"{nic}_mtu")
                elif not nat_addr:
                    membermtu = self.find_bridge_mtu(bridge)
                else:
                    membermtu = self.get('vnet_default_mtu')

                dhcp = self.get('dhcp')

                ifaces = []

                for addrs, gw, ipv6 in net_configs:
                    if (
                        dhcp or 'DHCP' in self.ip4_addr.upper()
                    ) and 'accept_rtadv' not in addrs:
                        # Spoofing IP address, it doesn't matter with DHCP
                        addrs = f"{nic}|''"

                    if addrs == 'none':
                        continue

                    for addr in addrs.split(','):
                        try:
                            iface, ip = addr.split("|")
                        except ValueError:
                            # They didn't supply an interface, assuming default
                            iface, ip = "vnet0", addr

                        if iface not in nics:
                            continue

                        if iface not in ifaces:
                            err = self.start_network_vnet_iface(
                                nic, bridge, membermtu, jid, nat_addr
                            )
                            if err:
                                errors.append(err)

                            ifaces.append(iface)

                        err = self.start_network_vnet_addr(iface, ip, gw, ipv6)
                        if err:
                            errors.append(err)

            except su.CalledProcessError as err:
                errors.append(err.output.decode("utf-8").rstrip())

        if len(errors) != 0:
            return errors

    def start_network_vnet_iface(self, nic, bridge, mtu, jid, nat_addr=0):
        """
        The real meat and potatoes for starting a VNET interface.

        :param nic: The network interface to assign the IP in the jail
        :param bridge: The bridge to attach the VNET interface
        :param mtu: The mtu of the VNET interface
        :param jid: The jails ID
        :return: If an error occurs it returns the error. Otherwise, it's None
        """
        vnet_default_interface = self.get('vnet_default_interface')
        if vnet_default_interface == 'auto':
            vnet_default_interface = self.get_default_interface()

        mac_a, mac_b = self.__start_generate_vnet_mac__(nic)
        epair_a_cmd = ["ifconfig", "epair", "create"]
        epair_a = su.Popen(epair_a_cmd, stdout=su.PIPE).communicate()[0]
        epair_a = epair_a.decode().strip()
        epair_b = re.sub("a$", "b", epair_a)

        if 'vnet' in nic:
            # Inside jails they are epairN
            jail_nic = f"{nic.replace('vnet', 'epair')}b"
        else:
            jail_nic = nic

        try:
            # Host
            iocage_lib.ioc_common.checkoutput(
                [
                    "ifconfig", epair_a, "name",
                    f"{nic}.{jid}", "mtu", mtu
                ],
                stderr=su.STDOUT
            )
            iocage_lib.ioc_common.checkoutput(
                ["ifconfig", f"{nic}.{jid}", "link", mac_a],
                stderr=su.STDOUT
            )
            iocage_lib.ioc_common.checkoutput(
                ["ifconfig", f"{nic}.{jid}", "description",
                 f"associated with jail: {self.uuid} as nic: {jail_nic}"],
                stderr=su.STDOUT
            )

            if 'accept_rtadv' in self.ip6_addr:
                # Set linklocal for IP6 + rtsold
                iocage_lib.ioc_common.checkoutput(
                    ['ifconfig', f'{nic}.{jid}', 'inet6', 'auto_linklocal',
                     'accept_rtadv', 'autoconf'],
                    stderr=su.STDOUT)

            # Jail
            iocage_lib.ioc_common.checkoutput(
                [
                    "ifconfig", epair_b, "vnet",
                    f"ioc-{self.uuid}"
                ],
                stderr=su.STDOUT
            )
            iocage_lib.ioc_common.checkoutput(
                [
                    'jexec', f'ioc-{self.uuid}', 'ifconfig', epair_b,
                    'mtu', mtu
                ],
                stderr=su.STDOUT
            )

            if epair_b != jail_nic:
                # This occurs on default vnet0 ip4_addr's
                iocage_lib.ioc_common.checkoutput(
                    [
                        "setfib", self.exec_fib, "jexec", f"ioc-{self.uuid}",
                        "ifconfig", epair_b, "name", jail_nic
                    ],
                    stderr=su.STDOUT
                )

            iocage_lib.ioc_common.checkoutput(
                [
                    "setfib", self.exec_fib, "jexec", f"ioc-{self.uuid}",
                    "ifconfig", jail_nic, "link", mac_b
                ],
                stderr=su.STDOUT
            )

            if not nat_addr:
                try:
                    # Host interface as supplied by user also needs to be on
                    # the bridge
                    if vnet_default_interface != 'none':
                        iocage_lib.ioc_common.checkoutput(
                            ['ifconfig', bridge, 'addm',
                             vnet_default_interface],
                            stderr=su.STDOUT
                        )
                except su.CalledProcessError:
                    # Already exists
                    pass

                iocage_lib.ioc_common.checkoutput(
                    ['ifconfig', bridge, 'addm', f'{nic}.{jid}', 'up'],
                    stderr=su.STDOUT
                )
            else:
                iocage_lib.ioc_common.checkoutput(
                    ['ifconfig', f'{nic}.{jid}', 'inet', f'{nat_addr}/30'],
                    stderr=su.STDOUT
                )
            iocage_lib.ioc_common.checkoutput(
                ['ifconfig', f'{nic}.{jid}', 'up'],
                stderr=su.STDOUT
            )
        except su.CalledProcessError as err:
            return f"{err.output.decode('utf-8')}".rstrip()

    def start_network_vnet_addr(self, iface, ip, defaultgw, ipv6=False):
        """
        Add an IP address to a vnet interface inside the jail.

        :param iface: The interface to use
        :param ip:  The IP address to assign
        :param defaultgw: The gateway IP to assign to the nic
        :return: If an error occurs it returns the error. Otherwise, it's None
        """
        dhcp = self.get('dhcp')
        wants_dhcp = True if dhcp or 'DHCP' in self.ip4_addr.upper() else False

        if 'vnet' in iface:
            # Inside jails they are epairNb
            iface = f'{iface.replace("vnet", "epair")}b'

        if ipv6:
            ifconfig = [iface, 'inet6', ip, 'up']
        else:
            ifconfig = [iface, ip, 'alias']

        try:
            if not wants_dhcp and ip != 'accept_rtadv':
                # Jail side
                iocage_lib.ioc_common.checkoutput(
                    ['setfib', self.exec_fib, 'jexec', f'ioc-{self.uuid}',
                     'ifconfig'] + ifconfig, stderr=su.STDOUT)
        except su.CalledProcessError as err:
            return f'{err.output.decode("utf-8")}'.rstrip()
        else:
            return

    def start_copy_localtime(self):
        host_time = self.get("host_time")
        file = f"{self.path}/root/etc/localtime"

        if not iocage_lib.ioc_common.check_truthy(host_time):
            return

        if os.path.isfile(file):
            os.remove(file)

        try:
            shutil.copy("/etc/localtime", file, follow_symlinks=False)
        except FileNotFoundError:
            return

    def start_generate_resolv(self):
        resolver = self.get("resolver")
        #                                     compat

        if resolver != "/etc/resolv.conf" and resolver != "none" and \
                resolver != "/dev/null":
            with iocage_lib.ioc_common.open_atomic(
                    f"{self.path}/root/etc/resolv.conf", "w") as resolv_conf:

                for line in resolver.split(";"):
                    resolv_conf.write(line + "\n")
        elif resolver == "none":
            shutil.copy("/etc/resolv.conf",
                        f"{self.path}/root/etc/resolv.conf")
        elif resolver == "/dev/null":
            # They don't want the resolv.conf to be touched.

            return
        else:
            shutil.copy(resolver, f"{self.path}/root/etc/resolv.conf")

    def __generate_mac_bytes(self, nic):
        m = hashlib.md5()
        m.update(self.uuid.encode("utf-8"))
        m.update(nic.encode("utf-8"))
        prefix = self.get("mac_prefix")

        return f"{prefix}{m.hexdigest()[0:12-len(prefix)]}"

    def __generate_mac_address_pair(self, nic):
        mac_a = self.__generate_mac_bytes(nic)
        mac_b = hex(int(mac_a, 16) + 1)[2:].zfill(12)

        return mac_a, mac_b

    def __start_generate_vnet_mac__(self, nic):
        """
        Generates a random MAC address and checks for uniquness.
        If the jail already has a mac address generated, it will return that
        instead.
        """
        mac = self.get("{}_mac".format(nic))

        if mac == "none":
            mac_a, mac_b = self.__generate_mac_address_pair(nic)
            self.set(f"{nic}_mac={mac_a} {mac_b}")
        else:
            try:
                mac_a, mac_b = mac.replace(',', ' ').split()
            except Exception:
                iocage_lib.ioc_common.logit({
                    "level": "EXCEPTION",
                    "message": f'Please correct mac addresses format for {nic}'
                })

        return mac_a, mac_b

    def __check_dhcp_or_accept_rtadv__(self, ipv4, enable):
        # legacy behavior to enable it on every NIC
        if ipv4 and (self.conf['dhcp'] or not enable):
            nic_list = self.get('interfaces').split(',')
            nics = list(map(lambda x: x.split(':')[0], nic_list))
        else:
            nics = []
            check_var = 'DHCP' if ipv4 else 'ACCEPT_RTADV'
            for ip in filter(
                lambda i: check_var in i.upper() and '|' in i,
                (self.ip4_addr if ipv4 else self.ip6_addr).split(',')
            ):
                nic, addr = ip.rsplit('/', 1)[0].split('|')

                if addr.upper() == check_var:
                    nics.append(nic)

        rc_conf_path = os.path.join(self.path, 'root/etc/rc.conf')
        if not os.path.exists(rc_conf_path):
            open(rc_conf_path, 'w').close()
            entries = {}
        else:
            with open(rc_conf_path, 'r') as f:
                entries = {
                    k: v.replace("'", '').replace('"', '')
                    for k, v in map(
                        lambda l: [e.strip() for e in l.strip().split('=', 1)],
                        filter(
                            lambda l: not l.strip().startswith('#') and '=' in l, f.readlines()
                        )
                    )
                }
        for nic in nics:
            if 'vnet' in nic:
                # Inside jails they are epairNb
                nic = f"{nic.replace('vnet', 'epair')}b"

            key = f'ifconfig_{nic}' if ipv4 else f'ifconfig_{nic}_ipv6'
            value = 'SYNCDHCP' if ipv4 else 'inet6 auto_linklocal accept_rtadv autoconf'
            if enable:
                cmd = [f'{key}={value}']
            else:
                cmd = ['-x', key] if key in entries and entries[key] == value else []

            if cmd:
                su.run(['sysrc', '-f', rc_conf_path] + cmd, stdout=su.PIPE)

    def __check_rtsold__(self):
        if 'accept_rtadv' not in self.ip6_addr:
            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message':
                        'Must set at least one ip6_addr to accept_rtadv!'
                },
                _callback=self.callback,
                silent=self.silent
            )

        su.run(
            [
                'sysrc', '-f', f'{self.path}/root/etc/rc.conf',
                f'rtsold_enable=YES'
            ],
            stdout=su.PIPE
        )

    def get_default_interface(self):
        if self.host_gateways['ipv4']['interface']:
            return self.host_gateways['ipv4']['interface']
        elif self.host_gateways['ipv6']['interface']:
            return self.host_gateways['ipv6']['interface']
        else:
            iocage_lib.ioc_common.logit(
                {
                    'level': 'EXCEPTION',
                    'message': 'No default interface found'
                },
                _callback=self.callback,
                silent=self.silent)

    def get_default_gateway(self, address_family='ipv4'):
        gateway = self.host_gateways[address_family]['gateway']
        if gateway:
            return gateway
        else:
            iocage_lib.ioc_common.logit(
                {
                    'level': 'WARNING',
                    'message': 'No default gateway found'
                    f' for {address_family}.'
                },
                _callback=self.callback,
                silent=self.silent
            )
            return 'none'

    def get_bridge_members(self, bridge):
        return [
            x.split()[1] for x in
            iocage_lib.ioc_common.checkoutput(
                ["ifconfig", bridge]
            ).splitlines()
            if x.strip().startswith("member")
        ]

    def find_bridge_mtu(self, bridge):
        if self.unit_test:
            dhcp = 0
            wants_dhcp = False
        else:
            dhcp = self.get('dhcp')
            wants_dhcp = True if dhcp or 'DHCP' in self.ip4_addr.upper() else \
                False

        try:
            if wants_dhcp:
                # Let's get the default vnet interface
                default_if = self.get('vnet_default_interface')
                if default_if == 'auto':
                    default_if = self.get_default_interface()

                if default_if != 'none':
                    bridge_cmd = [
                        "ifconfig", bridge, "create", "addm", default_if
                    ]
                    su.check_call(bridge_cmd, stdout=su.PIPE, stderr=su.PIPE)

            else:
                bridge_cmd = ["ifconfig", bridge, "create", "addm"]
                su.check_call(bridge_cmd, stdout=su.PIPE, stderr=su.PIPE)
        except su.CalledProcessError:
            # The bridge already exists, this is just best effort.
            pass

        memberif = self.get_bridge_members(bridge)
        if not memberif:
            return self.get('vnet_default_mtu')

        membermtu = iocage_lib.ioc_common.checkoutput(
            ["ifconfig", memberif[0]]
        ).split()

        return membermtu[5]

    def __check_nat__(self, backend='ipfw'):
        su.run(
            ['sysctl', '-q', 'net.inet.ip.forwarding=1'], stdout=su.PIPE,
            stderr=su.PIPE
        )
        self.log.debug('net.inet.ip.forwarding=1 set')

        if backend == 'pf':
            self.__check_nat_pf__()
        else:
            self.__check_nat_ipfw__()

    def __check_nat_pf__(self):
        loaded = su.run(['kldload', 'pf'], stdout=su.PIPE, stderr=su.PIPE)

        # The module was just loaded, enable pf
        if loaded.returncode == 0:
            pfctl = su.run(['pfctl', '-e'], stdout=su.PIPE, stderr=su.PIPE)

            if pfctl.returncode != 0:
                if 'enabled' not in pfctl.stderr.decode():
                    iocage_lib.ioc_common.logit({
                        'level': 'EXCEPTION',
                        'message': pfctl.stderr.decode()
                    }, _callback=self.callback,
                        silent=self.silent,
                        exception=ioc_exceptions.CommandFailed)

            self.log.debug('pf kernel module loaded and pf enabled')

    def __check_nat_ipfw__(self):
        loaded = su.run(
            ['sysctl', 'net.inet.ip.fw.enable=1'],
            stdout=su.PIPE, stderr=su.PIPE
        )

        # The module isn't loaded yet, doing so
        if loaded.returncode != 0:
            su.run(
                ['kenv', 'net.inet.ip.fw.default_to_accept=1'], stdout=su.PIPE,
                stderr=su.PIPE
            )
            su.run(['kldload', '-n', 'ipfw'])
            su.run(['kldload', '-n', 'ipfw_nat'])
            su.run(
                ['sysctl', '-q', 'net.inet.ip.fw.enable=1'], stdout=su.PIPE,
                stderr=su.PIPE
            )
            self.log.debug(
                'ipfw kernel module loaded and net.inet.ip.fw.enable=1 set'
            )

    def __add_nat__(self, nat_interface, forwards, backend='ipfw'):
        if backend == 'pf':
            pf_conf = self.__add_nat_pf__(nat_interface, forwards)
            pf = su.run(
                ['pfctl', '-f', pf_conf], stdout=su.PIPE, stderr=su.PIPE
            )
            self.log.debug(f'pfctl -f {pf_conf} ran')

            if pf.returncode != 0:
                iocage_lib.ioc_common.logit({
                    'level': 'EXCEPTION',
                    'message': pf.stderr.decode()
                }, _callback=self.callback,
                    silent=self.silent,
                    exception=ioc_exceptions.CommandFailed)

        else:
            su.run(['ifconfig', nat_interface, '-tso4', '-lro', '-vlanhwtso'])
            self.log.debug(f'TSO, LRO, VLANHWTSO disabled on {nat_interface}')
            ipfw_conf = self.__add_nat_ipfw__(nat_interface, forwards)
            ipfw = su.run(
                ['sh', '-c', ipfw_conf], stdout=su.PIPE, stderr=su.PIPE
            )
            self.log.debug(f'{ipfw_conf} ran')

            if ipfw.returncode != 0:
                iocage_lib.ioc_common.logit({
                    'level': 'EXCEPTION',
                    'message': ipfw.stderr.decode()
                }, _callback=self.callback,
                    silent=self.silent,
                    exception=ioc_exceptions.CommandFailed)

    def __add_nat_pf__(self, nat_interface, forwards):
        pf_conf = '/tmp/iocage_nat_pf.conf'
        ip4_addr = self.ip4_addr.split('|')[1].rsplit('/')[0]
        nat_network = str(
            ipaddress.IPv4Network(f'{ip4_addr}/24', strict=False)
        )
        rules = [
            f'nat on {nat_interface} from {nat_network} to any ->'
            f' ({nat_interface}:0) static-port'
        ]
        self.log.debug(f'Initial Rule: {rules[0]}')
        rdrs = []

        if forwards != 'none':
            for proto, port, map in self.__parse_nat_fwds__(forwards):
                # ipfw port ranges do not work with pf
                port = port.replace('-', ':')
                map = map.replace('-', ':')

                rdrs.append(
                    f'rdr pass on {nat_interface} inet proto {proto} from any'
                    f' to ({nat_interface}:0) port {map} -> {ip4_addr}'
                    f' port {port}\n'
                )
        self.log.debug(f'Forwards: {rdrs}')

        with open(os.open(pf_conf, os.O_CREAT | os.O_RDWR), 'w+') as f:
            self.log.debug(f'{pf_conf} opened')
            for line in f.readlines():
                line = line.rstrip()
                if line.startswith('rdr') and ip4_addr not in line:
                    rules.append(line)

            f.seek(0)
            for rule in rules:
                f.write(f'{rule}\n')
                self.log.debug(f'Wrote: {rule}')
            for rdr in rdrs:
                f.write(rdr)
                self.log.debug(f'Wrote: {rdr}')
            f.truncate()

        os.chmod(pf_conf, 0o755)

        return pf_conf

    def __add_nat_ipfw__(self, nat_interface, forwards):
        ipfw_conf = '/tmp/iocage_nat_ipfw.conf'
        nat_rule = f'ipfw -q nat 462 config if {nat_interface} same_ports'
        self.log.debug(f'Initial rule: {nat_rule}')
        rdrs = ''
        ip4_addr = self.ip4_addr.split('|')[1].rsplit('/')[0]
        nat_network = str(
            ipaddress.IPv4Network(f'{ip4_addr}/24', strict=False)
        )
        rules = [
            'ipfw -q flush',
            f'ipfw -q add 100 nat 462 ip4 from {nat_network} to any'
            f' out via {nat_interface}',
            'ipfw -q add 101 nat 462 ip4 from any to any in via'
            f' {nat_interface}'
        ]
        self.log.debug(f'Rules: {rules}')

        if forwards != 'none':
            for proto, port, map in self.__parse_nat_fwds__(forwards):
                rdrs += f' redirect_port {proto} {ip4_addr}:{port} {map}'

        with open(os.open(ipfw_conf, os.O_CREAT | os.O_RDWR), 'w+') as f:
            self.log.debug(f'{ipfw_conf} opened')
            for line in f.readlines():
                line = line.rstrip()
                if line not in rules and nat_rule in line:
                    nat_line = line.split('redirect_port ')
                    final_line = nat_rule

                    for n in nat_line:
                        if 'nat' in n:
                            continue

                        if ip4_addr not in n:
                            final_line += f' redirect_port {n}'

                    rules.insert(1, f'{final_line}{rdrs}')
                    self.log.debug(
                        f'Inserted: {final_line}{rdrs} into rules at index 1'
                    )

            if rules[1].endswith(nat_interface):
                # They don't have any port-forwards or the file is empty
                if rdrs:
                    nat_rule += rdrs

                rules.insert(1, nat_rule)
                self.log.debug(f'Inserted: {nat_rule} into rules at index 1')

            f.seek(0)
            for rule in rules:
                f.write(f'{rule}\n')
                self.log.debug(f'Wrote: {rule}')
            f.truncate()

        os.chmod(ipfw_conf, 0o755)

        return ipfw_conf

    def __parse_nat_fwds__(self, forwards):
        self.log.debug(f'Parsing NAT forwards: {forwards}')

        for fwd in forwards.split(','):
            proto, port = fwd.split('(')
            port = port.strip('()')

            self.log.debug(f'Proto: {proto} Port: {port}')
            try:
                port, map = port.rsplit(':', 1)
            except ValueError:
                map = port
            self.log.debug(f'Mapping {port} to {map}')

            yield proto, port, map
