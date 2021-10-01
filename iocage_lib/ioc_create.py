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
"""iocage create module."""
import json
import logging
import os
import pathlib
import re
import subprocess as su
import uuid

import iocage_lib.ioc_common
import iocage_lib.ioc_exec
import iocage_lib.ioc_fstab
import iocage_lib.ioc_json
import iocage_lib.ioc_list
import iocage_lib.ioc_start
import iocage_lib.ioc_stop
import iocage_lib.ioc_exceptions
import dns.resolver
import dns.exception
import shutil

from iocage_lib.cache import cache
from iocage_lib.dataset import Dataset


class IOCCreate(object):

    """Create a jail from a clone."""

    def __init__(self, release, props, num, pkglist=None, plugin=False,
                 migrate=False, config=None, silent=False, template=False,
                 short=False, basejail=False, thickjail=False, empty=False,
                 uuid=None, clone=False, thickconfig=False,
                 clone_basejail=False, callback=None):
        cache.reset()
        self.pool = iocage_lib.ioc_json.IOCJson().json_get_value("pool")
        self.iocroot = iocage_lib.ioc_json.IOCJson(self.pool).json_get_value(
            "iocroot")
        self.release = release
        self.props = props
        self.num = num
        self.pkglist = pkglist
        self.plugin = plugin
        self.migrate = migrate
        self.config = config
        self.template = template
        self.short = short
        self.basejail = basejail
        self.thickjail = thickjail
        self.empty = empty
        self.uuid = uuid
        self.clone = clone
        self.silent = silent
        self.callback = callback
        self.thickconfig = thickconfig
        self.log = logging.getLogger('iocage')

        if basejail and not clone_basejail:
            # We want these thick to remove any odd dependency chains later
            self.thickjail = True

    def create_jail(self):
        """Helper to catch SIGINT"""
        import iocage_lib.ioc_destroy  # Circular dep

        if self.uuid:
            jail_uuid = self.uuid
        else:
            jail_uuid = str(uuid.uuid4())

        if self.short:
            jail_uuid = jail_uuid[:8]

        location = f"{self.iocroot}/jails/{jail_uuid}"

        try:
            return self._create_jail(jail_uuid, location)
        except KeyboardInterrupt:
            iocage_lib.ioc_destroy.IOCDestroy().destroy_jail(location)
            iocage_lib.ioc_common.logit({
                'level': 'EXCEPTION',
                'message': 'Keyboard interrupt detected, destroyed'
                           f' {jail_uuid}.'
            },
                _callback=self.callback,
                silent=self.silent)

    def _create_jail(self, jail_uuid, location):
        """
        Create a snapshot of the user specified RELEASE dataset and clone a
        jail from that. The user can also specify properties to override the
        defaults.
        """
        import iocage_lib.ioc_destroy  # Circular dep
        start = False
        is_template = False
        source_template = None
        rtsold_enable = 'NO'

        if iocage_lib.ioc_common.match_to_dir(self.iocroot, jail_uuid):
            iocage_lib.ioc_common.logit({
                'level': 'EXCEPTION',
                'message': f'Jail: {jail_uuid} already exists!'
            })

        if self.migrate:
            config = self.config
        else:
            try:
                if self.clone and self.template:
                    iocage_lib.ioc_common.logit({
                        'level': 'EXCEPTION',
                        'message': 'You cannot clone a template, '
                                   'use create -t instead.'
                    },
                        _callback=self.callback,
                        silent=self.silent)
                elif self.template:
                    _type = "templates"
                    temp_path = f"{self.iocroot}/{_type}/{self.release}"
                    template_config = iocage_lib.ioc_json.IOCJson(
                        temp_path).json_get_value
                    try:
                        cloned_release = template_config('cloned_release')
                    except KeyError:
                        # Thick jails won't have this
                        cloned_release = None
                    source_template = self.release
                elif self.clone:
                    _type = "jails"
                    clone_path = f"{self.iocroot}/{_type}/{self.release}"
                    clone_config = iocage_lib.ioc_json.IOCJson(
                        clone_path).json_get_value
                    try:
                        cloned_release = clone_config('cloned_release')
                    except KeyError:
                        # Thick jails won't have this
                        cloned_release = None
                    clone_uuid = clone_config("host_hostuuid")
                else:
                    _type = "releases"
                    rel_path = f"{self.iocroot}/{_type}/{self.release}"

                    if not self.empty:
                        cloned_release = \
                            iocage_lib.ioc_common.get_jail_freebsd_version(
                                f'{rel_path}/root',
                                self.release
                            )
                    else:
                        cloned_release = "EMPTY"
            except (IOError, OSError, FileNotFoundError, UnboundLocalError):
                # Unintuitevly a missing template will throw a
                # UnboundLocalError as the missing file will kick the
                # migration routine for zfs props. We don't need that :)

                if self.template:
                    raise RuntimeError(f"Template: {self.release} not found!")
                elif self.clone:
                    if os.path.isdir(f"{self.iocroot}/templates/"
                                     f"{self.release}"):
                        iocage_lib.ioc_common.logit({
                            "level": "EXCEPTION",
                            "message": "You cannot clone a template, "
                                       "use create -t instead."
                        },
                            _callback=self.callback,
                            silent=self.silent)
                    else:
                        # Yep, self.release is actually the source jail.
                        iocage_lib.ioc_common.logit({
                            "level": "EXCEPTION",
                            "message": f"Jail: {self.release} not found!"
                        },
                            _callback=self.callback,
                            silent=self.silent)
                else:
                    iocage_lib.ioc_common.logit({
                        "level": "EXCEPTION",
                        "message": f"RELEASE: {self.release} not found!"
                    },
                        _callback=self.callback,
                        silent=self.silent)

            if not self.clone:
                if cloned_release is None:
                    cloned_release = self.release

                config = self.create_config(
                    jail_uuid, cloned_release, source_template
                )
            else:
                clone_config = f"{self.iocroot}/jails/{jail_uuid}/config.json"
                clone_fstab = f"{self.iocroot}/jails/{jail_uuid}/fstab"
                clone_etc_hosts = \
                    f"{self.iocroot}/jails/{jail_uuid}/root/etc/hosts"

        jail = f"{self.pool}/iocage/jails/{jail_uuid}/root"

        if self.template:
            source = f'{self.pool}/iocage/templates/{self.release}@{jail_uuid}'
            snap_cmd = ['zfs', 'snapshot', '-r', source]

            if self.thickjail:
                source = f'{source.split("@")[0]}/root@{jail_uuid}'
                snap_cmd = ['zfs', 'snapshot', source]

            try:
                su.check_call(snap_cmd, stderr=su.PIPE)
            except su.CalledProcessError:
                raise RuntimeError(f'Template: {jail_uuid} not found!')

            if not self.thickjail:
                su.Popen(
                    ['zfs', 'clone', '-p', f'{source.split("@")[0]}/root'
                     f'@{jail_uuid}', jail],
                    stdout=su.PIPE
                ).communicate()
            else:
                self.create_thickjail(jail_uuid, source.split('@')[0])
                del config['cloned_release']

            # self.release is actually the templates name
            config['release'] = iocage_lib.ioc_json.IOCJson(
                f'{self.iocroot}/templates/{self.release}').json_get_value(
                'release')
            try:
                config['cloned_release'] = iocage_lib.ioc_json.IOCJson(
                    f'{self.iocroot}/templates/{self.release}').json_get_value(
                    'cloned_release')
            except KeyError:
                # Thick jails won't have this
                pass
        elif self.clone:
            source = f'{self.pool}/iocage/jails/{self.release}@{jail_uuid}'
            snap_cmd = ['zfs', 'snapshot', '-r', source]

            if self.thickjail:
                source = f'{source.split("@")[0]}/root@{jail_uuid}'
                snap_cmd = ['zfs', 'snapshot', source]

            try:
                su.check_call(snap_cmd, stderr=su.PIPE)
            except su.CalledProcessError:
                raise RuntimeError(f'Jail: {jail_uuid} not found!')

            if not self.thickjail:
                su.Popen(
                    ['zfs', 'clone', source, jail.replace('/root', '')],
                    stdout=su.PIPE
                ).communicate()
                su.Popen(
                    ['zfs', 'clone', f'{source.split("@")[0]}/root@'
                     f'{jail_uuid}', jail],
                    stdout=su.PIPE
                ).communicate()
            else:
                self.create_thickjail(jail_uuid, source.split('@')[0])
                shutil.copyfile(
                    f'{self.iocroot}/jails/{self.release}/config.json',
                    f'{self.iocroot}/jails/{jail_uuid}/config.json'
                )
                shutil.copyfile(
                    f'{self.iocroot}/jails/{self.release}/fstab',
                    f'{self.iocroot}/jails/{jail_uuid}/fstab'
                )

            with open(clone_config, 'r') as _clone_config:
                config = json.load(_clone_config)

            # self.release is actually the clones name
            config['release'] = iocage_lib.ioc_json.IOCJson(
                f'{self.iocroot}/jails/{self.release}').json_get_value(
                'release')
            try:
                config['cloned_release'] = iocage_lib.ioc_json.IOCJson(
                    f'{self.iocroot}/jails/{self.release}').json_get_value(
                    'cloned_release')
            except KeyError:
                # Thick jails won't have this
                pass

            # Clones are expected to be as identical as possible.

            for k, v in config.items():
                try:
                    v = v.replace(clone_uuid, jail_uuid)

                    if '_mac' in k:
                        # They want a unique mac on start
                        config[k] = 'none'
                except AttributeError:
                    # Bool props
                    pass

                config[k] = v
        else:
            if not self.empty:
                dataset = f'{self.pool}/iocage/releases/{self.release}/' \
                    f'root@{jail_uuid}'
                try:
                    su.check_call(['zfs', 'snapshot', dataset], stderr=su.PIPE)
                except su.CalledProcessError:
                    release = os.path.join(
                        self.pool, 'iocage/releases', self.release
                    )
                    if not Dataset(release).exists:
                        raise RuntimeError(
                            f'RELEASE: {self.release} not found!'
                        )
                    else:
                        iocage_lib.ioc_common.logit({
                            'level': 'EXCEPTION',
                            'message': f'Snapshot: {dataset} exists!\n'
                                       'Please manually run zfs destroy'
                                       f' {dataset} if you wish to '
                                       'destroy it.'
                        },
                            _callback=self.callback,
                            silent=self.silent)

                if not self.thickjail:
                    su.Popen(
                        ['zfs', 'clone', '-p', dataset, jail],
                        stdout=su.PIPE
                    ).communicate()
                else:
                    self.create_thickjail(jail_uuid, dataset.split('@')[0])
                    del config['cloned_release']
            else:
                try:
                    iocage_lib.ioc_common.checkoutput(
                        ['zfs', 'create', '-p', jail],
                        stderr=su.PIPE)
                except su.CalledProcessError as err:
                    raise RuntimeError(err.output.decode('utf-8').rstrip())

        cache.reset()
        iocjson = iocage_lib.ioc_json.IOCJson(location, silent=True)

        # This test is to avoid the same warnings during install_packages.

        if jail_uuid == "default" or jail_uuid == "help":
            iocage_lib.ioc_destroy.IOCDestroy(
            ).__destroy_parse_datasets__(
                f"{self.pool}/iocage/jails/{jail_uuid}")
            iocage_lib.ioc_common.logit({
                "level": "EXCEPTION",
                "message": f"You cannot name a jail {jail_uuid}, "
                           "that is a reserved name."
            },
                _callback=self.callback,
                silent=self.silent)

        disable_localhost = False
        for prop in self.props:
            key, _, value = prop.partition("=")
            is_true = iocage_lib.ioc_common.check_truthy(value)

            if key == "boot" and is_true and not self.empty:
                start = True
            elif self.plugin and key == "type" and value == "pluginv2":
                config["type"] = value
            elif key == 'template' and is_true:
                iocjson.json_write(config)  # Set counts on this.
                location = location.replace("/jails/", "/templates/")

                iocjson.json_set_value("type=template")
                iocjson.json_set_value("template=1")
                Dataset(
                    os.path.join(self.pool, 'iocage', 'templates', jail_uuid)
                ).set_property('readonly', 'off')

                # If you supply pkglist and templates without setting the
                # config's type, you will end up with a type of jail
                # instead of template like we want.
                config["type"] = "template"
                start = False
                is_template = True
            elif key == 'ip6_addr':
                if 'accept_rtadv' in value:
                    if not iocage_lib.ioc_common.lowercase_set(
                        iocage_lib.ioc_common.construct_truthy(
                            'vnet'
                        )
                    ) & iocage_lib.ioc_common.lowercase_set(self.props):
                        iocage_lib.ioc_common.logit({
                            'level': 'WARNING',
                            'message': 'accept_rtadv requires vnet,'
                            ' enabling!'
                        },
                            _callback=self.callback,
                            silent=self.silent)
                        config['vnet'] = 1

                    rtsold_enable = 'YES'
            elif (key == 'dhcp' and is_true) or (
                key == 'ip4_addr' and 'DHCP' in value.upper()
            ):
                if not iocage_lib.ioc_common.lowercase_set(
                    iocage_lib.ioc_common.construct_truthy(
                        'vnet'
                    )
                ) & iocage_lib.ioc_common.lowercase_set(self.props):
                    iocage_lib.ioc_common.logit({
                        'level': 'WARNING',
                        'message': 'dhcp requires vnet, enabling!'
                    },
                        _callback=self.callback,
                        silent=self.silent)
                    config['vnet'] = 1
                if not iocage_lib.ioc_common.lowercase_set(
                    iocage_lib.ioc_common.construct_truthy(
                        'bpf'
                    )
                ) & iocage_lib.ioc_common.lowercase_set(self.props):
                    iocage_lib.ioc_common.logit({
                        'level': 'WARNING',
                        'message': 'dhcp requires bpf, enabling!'
                    },
                        _callback=self.callback,
                        silent=self.silent)
                    config['bpf'] = 1
            elif key == 'bpf' and is_true:
                if not iocage_lib.ioc_common.lowercase_set(
                    iocage_lib.ioc_common.construct_truthy(
                        'vnet'
                    )
                ) & iocage_lib.ioc_common.lowercase_set(self.props):
                    iocage_lib.ioc_common.logit({
                        'level': 'WARNING',
                        'message': 'bpf requires vnet, enabling!'
                    },
                        _callback=self.callback,
                        silent=self.silent)
                    config['vnet'] = 1
            elif key == 'assign_localhost' and is_true:
                if iocage_lib.ioc_common.lowercase_set(
                    iocage_lib.ioc_common.construct_truthy(
                        'vnet'
                    )
                ) & iocage_lib.ioc_common.lowercase_set(self.props):
                    iocage_lib.ioc_common.logit({
                        'level': 'WARNING',
                        'message': 'assign_localhost only applies to shared'
                                   ' IP jails, disabling!'
                    },
                        _callback=self.callback,
                        silent=self.silent)
                    disable_localhost = True

            if disable_localhost:
                self.props = [p for p in self.props if not p.startswith(
                    'assign_localhost') and not p.startswith('localhost_ip')]
                if not self.thickconfig:
                    try:
                        del config['assign_localhost']
                    except KeyError:
                        # They may not have specified this
                        pass

                    try:
                        del config['localhost_ip']
                    except KeyError:
                        # They may not have specified this
                        pass
                else:
                    config['assign_localhost'] = 0
                    config['localhost_ip'] = 0

            try:
                value, config = iocjson.json_check_prop(key, value, config)
                config[key] = value
            except RuntimeError as err:
                iocjson.json_write(config)  # Destroy counts on this.
                iocage_lib.ioc_destroy.IOCDestroy().destroy_jail(location)

                raise RuntimeError(f"***\n{err}\n***\n")
            except SystemExit:
                iocjson.json_write(config)  # Destroy counts on this.
                iocage_lib.ioc_destroy.IOCDestroy().destroy_jail(location)
                exit(1)

        # We want these to represent reality on the FS
        iocjson.fix_properties(config)
        if not self.plugin:
            # TODO: Should we probably only write once and maybe at the end
            # of the function ?
            iocjson.json_write(config)

        # Just "touch" the fstab file, since it won't exist and write
        # /etc/hosts
        try:
            etc_hosts_ip_addr = config["ip4_addr"].split("|", 1)[-1].rsplit(
                '/', 1)[0]
        except KeyError:
            # No ip4_addr specified during creation
            pass

        try:
            jail_uuid_short = jail_uuid.rsplit(".")[-2]
            jail_hostname = \
                f"{jail_uuid}\t{jail_uuid_short}"
        except IndexError:
            # They supplied just a normal tag
            jail_uuid_short = jail_uuid
            jail_hostname = jail_uuid

        # If jail is template, the dataset would be readonly at this point
        if is_template:
            Dataset(
                os.path.join(self.pool, 'iocage/templates', jail_uuid)
            ).set_property('readonly', 'off')

        if self.empty:
            open(f"{location}/fstab", "wb").close()

            config["release"] = "EMPTY"
            config["cloned_release"] = "EMPTY"

            iocjson.json_write(config)

        elif not self.clone:
            open(f"{location}/fstab", "wb").close()

            with open(
                    f"{self.iocroot}/"
                    f"{'releases' if not self.template else 'templates'}/"
                    f"{self.release}/root/etc/hosts", "r"
            ) as _etc_hosts:
                with iocage_lib.ioc_common.open_atomic(
                        f"{location}/root/etc/hosts", "w") as etc_hosts:
                    # open_atomic will empty the file, we need these still.

                    for line in _etc_hosts.readlines():
                        if line.startswith("127.0.0.1"):
                            if config.get(
                                'assign_localhost'
                            ) and not config.get('vnet'):
                                l_ip = config.get('localhost_ip', 'none')
                                l_ip = l_ip if l_ip != 'none' else \
                                    iocage_lib.ioc_common.gen_unused_lo_ip()
                                config['localhost_ip'] = l_ip
                                iocjson.json_write(config)

                                # If they are creating multiple jails, we want
                                # this aliased before starting the  jail
                                su.run(
                                    [
                                        'ifconfig', 'lo0', 'alias',
                                        f'{l_ip}/32'
                                    ]
                                )

                                line = f'{l_ip}\t\tlocalhost' \
                                       ' localhost.my.domain' \
                                       f' {jail_uuid_short}\n'
                            else:
                                line = f'{line.rstrip()} {jail_uuid_short}\n'

                        etc_hosts.write(line)
                    else:
                        # We want their IP to have the hostname at the end

                        try:
                            if config["ip4_addr"] != "none":
                                final_line =\
                                    f'{etc_hosts_ip_addr}\t{jail_hostname}\n'
                                etc_hosts.write(final_line)
                        except KeyError:
                            # No ip4_addr specified during creation
                            pass
        else:
            with open(clone_fstab, "r") as _clone_fstab:
                with iocage_lib.ioc_common.open_atomic(
                        clone_fstab, "w") as _fstab:
                    # open_atomic will empty the file, we need these still.

                    for line in _clone_fstab.readlines():
                        _fstab.write(line.replace(clone_uuid, jail_uuid))

            with open(clone_etc_hosts, "r") as _clone_etc_hosts:
                with iocage_lib.ioc_common.open_atomic(
                        clone_etc_hosts, "w") as etc_hosts:
                    # open_atomic will empty the file, we need these still.

                    for line in _clone_etc_hosts.readlines():
                        etc_hosts.write(line.replace(clone_uuid, jail_uuid))

        if not self.empty:
            self.create_rc(
                location,
                config["host_hostname"],
                config.get('basejail', 0)
            )

            if rtsold_enable == 'YES':
                iocage_lib.ioc_common.set_rcconf(
                    location, "rtsold_enable", rtsold_enable)

        if self.basejail or self.plugin:
            basedirs = ["bin", "boot", "lib", "libexec", "rescue", "sbin",
                        "usr/bin", "usr/include", "usr/lib",
                        "usr/libexec", "usr/sbin", "usr/share",
                        "usr/libdata", "usr/lib32"]

            if "-STABLE" in self.release:
                # HardenedBSD does not have this.
                basedirs.remove("usr/lib32")

            for bdir in basedirs:
                if "-RELEASE" not in self.release and "-STABLE" not in \
                        self.release:
                    _type = "templates"
                else:
                    _type = "releases"

                source = f"{self.iocroot}/{_type}/{self.release}/root/{bdir}"
                destination = f"{self.iocroot}/jails/{jail_uuid}/root/{bdir}"

                # This reduces the REFER of the basejail.
                # Just much faster by almost a factor of 2 than the builtins.
                su.Popen(["rm", "-r", "-f", destination]).communicate()
                os.mkdir(destination)

                iocage_lib.ioc_fstab.IOCFstab(jail_uuid, "add", source,
                                              destination, "nullfs", "ro", "0",
                                              "0", silent=True)
                config["basejail"] = 1

            iocjson.json_write(config)

        if not self.plugin:
            if self.clone:
                msg = f"{jail_uuid} successfully cloned!"
            else:
                msg = f"{jail_uuid} successfully created!"

            iocage_lib.ioc_common.logit({
                "level": "INFO",
                "message": msg
            },
                _callback=self.callback,
                silent=self.silent)

        if self.pkglist:
            auto_config = config.get('dhcp') or \
                config.get('ip_hostname') or \
                config.get('nat')

            if config.get('ip4_addr', 'none') == "none" and \
                config.get('ip6_addr', 'none') == "none" and \
                    not auto_config:
                iocage_lib.ioc_common.logit({
                    "level": "WARNING",
                    "message": "You need an IP address for the jail to"
                               " install packages!\n"
                },
                    _callback=self.callback,
                    silent=self.silent)
            else:
                self.create_install_packages(jail_uuid, location)

        if start:
            iocage_lib.ioc_start.IOCStart(jail_uuid, location,
                                          silent=self.silent)

        if is_template:
            # We have to set readonly back, since we're done with our tasks
            Dataset(
                os.path.join(self.pool, 'iocage/templates', jail_uuid)
            ).set_property('readonly', 'on')

        return jail_uuid

    def create_config(self, jail_uuid, release, source_template):
        """
        Create the jail configuration with the minimal needed defaults.
        If self.thickconfig is True, it will create a jail with all properties.
        """
        # Unique jail properties, they will be overridden by user supplied
        # values.
        jail_props = {
            'host_hostname': jail_uuid.replace('_', '-'),
            'host_hostuuid': jail_uuid,
            'release': release,
            'cloned_release': self.release,
            'jail_zfs_dataset': f'iocage/jails/{jail_uuid}/data'
        }

        d_conf = iocage_lib.ioc_json.IOCJson().check_default_config()
        default_mac_prefix = mac_prefix = d_conf['mac_prefix']
        if 'mac_prefix' not in [
            prop.split('=')[0] for prop in (self.props or [])
        ] and not iocage_lib.ioc_json.IOCJson.validate_mac_prefix(default_mac_prefix):
            prefix = iocage_lib.ioc_json.IOCJson.get_mac_prefix()
            iocage_lib.ioc_common.logit({
                'level': 'WARNING',
                'message': f'Default mac_prefix specified in defaults.json {default_mac_prefix!r} '
                           f'is invalid. Using {prefix!r} mac prefix instead.'
            })
            mac_prefix = iocage_lib.ioc_json.IOCJson.get_mac_prefix()
            d_conf['mac_prefix'] = mac_prefix

        if self.thickconfig:
            jail_props.update(d_conf)
            jail_props['CONFIG_TYPE'] = 'THICK'
        elif mac_prefix != default_mac_prefix:
            jail_props['mac_prefix'] = mac_prefix

        if source_template is not None:
            jail_props['source_template'] = source_template

        return jail_props

    def create_install_packages(self, jail_uuid, location,
                                repo="pkg.freebsd.org"):
        """
        Takes a list of pkg's to install into the target jail. The resolver
        property is required for pkg to have network access.
        """
        started = False
        status, jid = iocage_lib.ioc_list.IOCList().list_get_jid(jail_uuid)

        if not status:
            iocage_lib.ioc_start.IOCStart(jail_uuid, location, silent=True)
            started, jid = iocage_lib.ioc_list.IOCList().list_get_jid(
                jail_uuid
            )

        if repo:
            r = re.match('(https?(://)?)?([^/]+)', repo)
            if r and len(r.groups()) >= 3:
                repo = r.group(3)

            iocage_lib.ioc_common.logit({
                "level": "INFO",
                "message": f"\nTesting Host DNS response to {repo}"
            },
                _callback=self.callback,
                silent=False)

            try:
                dns.resolver.query(repo)
            except dns.resolver.NoNameservers:
                iocage_lib.ioc_common.logit({
                    'level': 'EXCEPTION',
                    'message': f'{repo} could not be reached via DNS, check'
                    ' your network'
                },
                    _callback=self.callback,
                    silent=False)
            except dns.exception.DNSException as e:
                iocage_lib.ioc_common.logit({
                    'level': 'EXCEPTION',
                    'message': f'DNS Exception: {e}\n'
                    f'{repo} could not be reached via DNS, check your network'
                },
                    _callback=self.callback,
                    silent=False)

            # Connectivity test courtesy David Cottlehuber off Google Group
            srv_connect_cmd = ["drill", "-t", f"_http._tcp.{repo} SRV"]
            dnssec_connect_cmd = ["drill", "-D", f"{repo}"]
            dns_connect_cmd = ["drill", f"{repo}"]

            iocage_lib.ioc_common.logit({
                "level": "INFO",
                "message": f"Testing {jail_uuid}'s SRV response to {repo}"
            },
                _callback=self.callback,
                silent=False)

            try:
                iocage_lib.ioc_exec.SilentExec(
                    srv_connect_cmd, location, uuid=jail_uuid,
                    plugin=self.plugin
                )
            except iocage_lib.ioc_exceptions.CommandFailed:
                # This shouldn't be fatal since SRV records are not required
                iocage_lib.ioc_common.logit({
                    "level": "WARNING",
                    "message":
                        f"{repo}'s SRV record could not be verified.\n"
                },
                    _callback=self.callback,
                    silent=False)

            iocage_lib.ioc_common.logit({
                "level": "INFO",
                "message": f"Testing {jail_uuid}'s DNSSEC response to {repo}"
            },
                _callback=self.callback,
                silent=False)
            try:
                iocage_lib.ioc_exec.SilentExec(
                    dnssec_connect_cmd, location, uuid=jail_uuid,
                    plugin=self.plugin,
                )
            except iocage_lib.ioc_exceptions.CommandFailed:
                # Not fatal, they may not be using DNSSEC
                iocage_lib.ioc_common.logit({
                    "level": "WARNING",
                    "message": f"{repo} could not be reached via DNSSEC.\n"
                },
                    _callback=self.callback,
                    silent=False)

                iocage_lib.ioc_common.logit({
                    "level": "INFO",
                    "message": f"Testing {jail_uuid}'s DNS response to {repo}"
                },
                    _callback=self.callback,
                    silent=False)

                try:
                    iocage_lib.ioc_exec.SilentExec(
                        dns_connect_cmd, location, uuid=jail_uuid,
                        plugin=self.plugin,
                    )
                except iocage_lib.ioc_exceptions.CommandFailed:
                    iocage_lib.ioc_common.logit({
                        "level": "EXCEPTION",
                        "message": f"{repo} could not be reached via DNS,"
                        f" check {jail_uuid}'s network configuration"
                    },
                        _callback=self.callback,
                        silent=False)

        if isinstance(self.pkglist, str):
            with open(self.pkglist, "r") as j:
                self.pkglist = json.load(j)["pkgs"]

        iocage_lib.ioc_common.logit({
            "level": "INFO",
            "message": "\nInstalling pkg... "
        },
            _callback=self.callback,
            silent=self.silent)

        # To avoid a user being prompted about pkg.
        pkg_retry = 1
        while True:
            pkg_install = su.run(["pkg-static", "-j", jid, "install", "-q",
                                  "-y", "pkg"],
                                 stdout=su.PIPE,
                                 stderr=su.STDOUT)
            pkg_err = pkg_install.returncode

            self.log.debug(pkg_install.stdout)

            if pkg_err == 0:
                break

            iocage_lib.ioc_common.logit(
                {
                    "level": 'INFO',
                    "message": f'pkg failed to install, retry #{pkg_retry}'
                },
                silent=self.silent,
                _callback=self.callback)

            if pkg_retry <= 2:
                pkg_retry += 1
            elif pkg_retry == 3:
                pkg_err_output = pkg_install.stdout.decode().rstrip()
                iocage_lib.ioc_common.logit(
                    {
                        "level": "EXCEPTION",
                        "message": f"\npkg error:\n  - {pkg_err_output}\n"
                                 '\nPlease check your network'
                    },
                    _callback=self.callback)

        # We will have mismatched ABI errors from earlier, this is to be safe.
        pkg_env = {
            **{
                k: os.environ.get(k)
                for k in ['http_proxy', 'https_proxy'] if os.environ.get(k)
            }
            , "ASSUME_ALWAYS_YES": "yes"
        }
        cmd = ("/usr/local/sbin/pkg-static", "upgrade", "-f", "-q", "-y")
        try:
            with iocage_lib.ioc_exec.IOCExec(
                cmd, location, uuid=jail_uuid, plugin=self.plugin,
                su_env=pkg_env
            ) as _exec:
                iocage_lib.ioc_common.consume_and_log(
                    _exec,
                    callback=self.callback,
                    log=not self.silent
                )
        except iocage_lib.ioc_exceptions.CommandFailed as e:
            iocage_lib.ioc_stop.IOCStop(jail_uuid, location, force=True,
                                        silent=True)
            iocage_lib.ioc_common.logit({
                "level": "EXCEPTION",
                "message": e.message.decode().rstrip()
            },
                _callback=self.callback)

        supply_msg = ("\nInstalling supplied packages:", self.silent)

        if self.plugin:
            supply_msg = ("\nInstalling plugin packages:", False)

        iocage_lib.ioc_common.logit({
            "level": "INFO",
            "message": supply_msg[0]
        },
            _callback=self.callback,
            silent=supply_msg[1])

        pkg_err_list = []

        for pkg in self.pkglist:
            iocage_lib.ioc_common.logit({
                "level": "INFO",
                "message": f"  - {pkg}... "
            },
                _callback=self.callback,
                silent=supply_msg[1])

            pkg_retry = 1
            while True:
                pkg_err = False
                cmd = ("/usr/local/sbin/pkg", "install", "-q", "-y", pkg)

                try:
                    with iocage_lib.ioc_exec.IOCExec(
                        cmd, location, uuid=jail_uuid, plugin=self.plugin,
                        su_env=pkg_env
                    ) as _exec:
                        iocage_lib.ioc_common.consume_and_log(
                            _exec,
                            callback=self.callback,
                            log=not(self.silent)
                        )
                except iocage_lib.ioc_exceptions.CommandFailed as e:
                    nonempty_lines = [line.rstrip() for line in e.message if line.rstrip()]
                    pkg_stderr = ''
                    if len(nonempty_lines) > 0:
                        pkg_stderr = nonempty_lines[-1].decode()
                    pkg_err = True

                if not pkg_err:
                    break

                pkg_err_msg = f'{pkg} :{pkg_stderr}'
                iocage_lib.ioc_common.logit(
                    {
                        "level": 'INFO',
                        "message": f'    - {pkg} failed to install, retry'
                                   f' #{pkg_retry}'
                    },
                    silent=False,
                    _callback=self.callback)

                if pkg_retry <= 2:
                    pkg_retry += 1
                elif pkg_retry == 3 and not self.plugin:
                    iocage_lib.ioc_common.logit(
                        {
                            "level": "ERROR",
                            "message": pkg_stderr
                        },
                        _callback=self.callback)
                    break
                elif pkg_retry == 3:
                    if pkg_err_msg not in pkg_err_list:
                        pkg_err_list.append(pkg_err_msg)
                    break

        if started:
            iocage_lib.ioc_stop.IOCStop(jail_uuid, location, silent=True)

        if self.plugin and pkg_err_list:
            return ','.join(pkg_err_list)

    def create_rc(self, location, host_hostname, basejail=0):
        """
        Writes a boilerplate rc.conf file for a jail if it doesn't exist,
         otherwise changes the hostname.
        """
        rc_conf = pathlib.Path(f"{self.iocroot}/default_rc.conf")
        # Template created jails will have this file.
        jail_rc_conf = pathlib.Path(f"{location}/root/etc/rc.conf")

        if not rc_conf.is_file():
            iocage_lib.ioc_common.logit({
                'level': 'NOTICE',
                'message': 'Missing default rc.conf, creating it'
            },
                _callback=self.callback,
                silent=self.silent)
            # Create a sane default for default rc.conf
            rcconf = """\
cron_flags="$cron_flags -J 15"

# Disable Sendmail by default
sendmail_enable="NO"
sendmail_submit_enable="NO"
sendmail_outbound_enable="NO"
sendmail_msp_queue_enable="NO"

# Run secure syslog
syslogd_flags="-c -ss"

# Enable IPv6
ipv6_activate_all_interfaces=\"YES\"
"""
            rc_conf.write_text(rcconf)

        if not jail_rc_conf.is_file():
            shutil.copy(str(rc_conf), str(jail_rc_conf))

        if basejail:
            su.Popen(
                ['mount', '-F', f'{location}/fstab', '-a']).communicate()

        if basejail:
            su.Popen(
                ['umount', '-F', f'{location}/fstab', '-a']).communicate()

    def create_thickjail(self, jail_uuid, source):
        jail = f"{self.pool}/iocage/jails/{jail_uuid}"

        try:
            su.Popen(['zfs', 'create', '-p', jail],
                     stdout=su.PIPE).communicate()
            zfs_send = su.Popen(
                ['zfs', 'send', f'{source}@{jail_uuid}'],
                stdout=su.PIPE
            )
            su.check_call(
                ['zfs', 'receive', '-F', f'{jail}/root'],
                stdin=zfs_send.stdout
            )
            su.check_call(
                ['zfs', 'destroy', f'{source}@{jail_uuid}'],
                stdout=su.PIPE
            )
            su.check_call(
                ['zfs', 'destroy', f'{jail}/root@{jail_uuid}'],
                stdout=su.PIPE
            )
        except su.CalledProcessError:
            su.Popen(
                ['zfs', 'destroy', '-rf', jail],
                stdout=su.PIPE
            ).communicate()
            su.Popen(
                ['zfs', 'destroy', '-r', f'{source}@{jail_uuid}'],
                stdout=su.PIPE
            ).communicate()

            iocage_lib.ioc_common.logit({
                'level': 'EXCEPTION',
                'message': f'Can\'t create thick jail from {source}!'
            },
                _callback=self.callback,
                silent=self.silent)
