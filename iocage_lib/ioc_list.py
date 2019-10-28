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
"""List all datasets by type"""
import json
import netifaces
import os
import re
import subprocess as su
import urllib.parse
import uuid as _uuid

import iocage_lib.ioc_common
import iocage_lib.ioc_json
import iocage_lib.ioc_plugin
import texttable

from iocage_lib.dataset import Dataset


class IOCList(object):

    """
    List jails that are a specified type.

    Format is:
        JID UID BOOT STATE TYPE IP4 RELEASE
    """

    def __init__(
        self, lst_type='all', hdr=True, full=False, _sort=None, silent=False,
        callback=None, plugin=False, quick=False, **kwargs
    ):
        self.list_type = lst_type
        self.header = hdr
        self.full = full
        self.iocjson = iocage_lib.ioc_json.IOCJson()
        self.pool = self.iocjson.pool
        self.iocroot = self.iocjson.iocroot
        self.sort = _sort
        self.silent = silent
        self.callback = callback
        self.basejail_only = False if self.list_type != 'basejail' else True
        self.plugin = plugin
        self.quick = quick
        self.plugin_data = kwargs.get('plugin_data', False)

    def list_datasets(self):
        """Lists the datasets of given type."""
        if self.list_type == "base":
            ds = Dataset(f"{self.pool}/iocage/releases").get_dependents()
        elif self.list_type == "template":
            ds = Dataset(
                f"{self.pool}/iocage/templates").get_dependents()
        else:
            ds = Dataset(f"{self.pool}/iocage/jails").get_dependents()

        ds = list(ds)

        if self.list_type in ('all', 'basejail', 'template'):
            if self.quick:
                _all = self.list_all_quick(ds)
            else:
                _all = self.list_all(ds)

            return _all
        elif self.list_type == "uuid":
            jails = {}

            for jail in ds:
                uuid = jail.name.rsplit("/", 1)[-1]
                try:
                    jails[uuid] = jail.properties["mountpoint"]
                except KeyError:
                    iocage_lib.ioc_common.logit(
                        {
                            'level': 'ERROR',
                            'message': f'{jail.name} mountpoint is '
                            'misconfigured. Please correct this.'
                        },
                        _callback=self.callback,
                        silent=self.silent
                    )

            template_datasets = Dataset(
                f'{self.pool}/iocage/templates').get_dependents()

            for template in template_datasets:
                uuid = template.name.rsplit("/", 1)[-1]
                jails[uuid] = template.properties['mountpoint']

            return jails
        elif self.list_type == "base":
            bases = self.list_bases(ds)

            return bases

    def list_all_quick(self, jails):
        """Returns a table of jails with minimal processing"""
        jail_list = []

        for jail in jails:
            try:
                mountpoint = jail.properties['mountpoint']
            except KeyError:
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'ERROR',
                        'message': f'{jail.name} mountpoint is misconfigured. '
                        'Please correct this.'
                    },
                    _callback=self.callback,
                    silent=self.silent
                )
                continue

            try:
                with open(f"{mountpoint}/config.json", "r") as loc:
                    conf = json.load(loc)
            except FileNotFoundError:
                uuid = mountpoint.rsplit("/", 1)[-1]
                iocage_lib.ioc_common.logit({
                    "level": "EXCEPTION",
                    "message": f"{uuid} is missing its configuration file."
                               "\nPlease run just 'list' instead to create"
                               " it."
                }, _callback=self.callback,
                    silent=self.silent)
            except (Exception, SystemExit):
                # Jail is corrupt, we want the user to know
                conf = {
                    'host_hostuuid':
                        f'{mountpoint.rsplit("/", 1)[-1]} - CORRUPTED',
                    'ip4_addr': 'N/A',
                    'dhcp': 'N/A'
                }

            uuid = conf["host_hostuuid"]
            ip4 = conf.get('ip4_addr', 'none')
            dhcp = True if iocage_lib.ioc_common.check_truthy(
                conf.get('dhcp', 0)) or 'DHCP' in ip4.upper() else False
            ip4 = ip4 if not dhcp else 'DHCP'

            if self.basejail_only and not iocage_lib.ioc_common.check_truthy(
                conf.get('basejail', 0)
            ):
                continue

            jail_list.append([uuid, ip4])

        # return the list

        if not self.header:
            flat_jail = [j for j in jail_list]

            return flat_jail

        # Prints the table
        table = texttable.Texttable(max_width=0)

        # We get an infinite float otherwise.
        table.set_cols_dtype(["t", "t"])
        jail_list.insert(0, ["NAME", "IP4"])

        table.add_rows(jail_list)

        return table.draw()

    def list_all(self, jails):
        """List all jails."""
        self.full = True if self.plugin else self.full
        jail_list = []
        plugin_index_data = {}

        for jail in jails:
            try:
                mountpoint = jail.properties['mountpoint']
            except KeyError:
                iocage_lib.ioc_common.logit(
                    {
                        'level': 'ERROR',
                        'message': f'{jail.name} mountpoint is misconfigured. '
                        'Please correct this.'
                    },
                    _callback=self.callback,
                    silent=self.silent
                )
                continue

            try:
                conf = iocage_lib.ioc_json.IOCJson(mountpoint).json_get_value(
                    'all'
                )
                state = ''
            except (Exception, SystemExit):
                # Jail is corrupt, we want all the keys to exist.
                # So we will take the defaults and let the user
                # know that they are not correct.
                def_props = iocage_lib.ioc_json.IOCJson().json_get_value(
                    'all',
                    default=True
                )
                conf = {
                    x: 'N/A'
                    for x in def_props
                }
                conf['host_hostuuid'] = \
                    f'{jail.name.split("/")[-1]}'
                conf['release'] = 'N/A'
                state = 'CORRUPT'
                jid = '-'

            if self.basejail_only and not iocage_lib.ioc_common.check_truthy(
                conf.get('basejail', 0)
            ):
                continue

            uuid_full = conf["host_hostuuid"]
            uuid = uuid_full

            if not self.full:
                # We only want to show the first 8 characters of a UUID,
                # if it's not a UUID, we will show the whole name no matter
                # what.
                try:
                    uuid = str(_uuid.UUID(uuid, version=4))[:8]
                except ValueError:
                    # We leave the "uuid" untouched, as it's not a valid
                    # UUID, but instead a named jail.
                    pass

            full_ip4 = conf["ip4_addr"]
            ip6 = conf["ip6_addr"]

            try:
                short_ip4 = ",".join([item.split("|")[1].split("/")[0]
                                      for item in full_ip4.split(",")])
            except IndexError:
                short_ip4 = full_ip4 if full_ip4 != "none" else "-"

            boot = 'on' if iocage_lib.ioc_common.check_truthy(
                conf.get('boot', 0)) else 'off'
            jail_type = conf["type"]
            full_release = conf["release"]
            basejail = 'yes' if iocage_lib.ioc_common.check_truthy(
                conf.get('basejail', 0)) else 'no'

            if "HBSD" in full_release:
                full_release = re.sub(r"\W\w.", "-", full_release)
                full_release = full_release.replace("--SD", "-STABLE-HBSD")
                short_release = full_release.rstrip("-HBSD")
            else:
                short_release = "-".join(full_release.rsplit("-")[:2])

            if full_ip4 == "none":
                full_ip4 = "-"

            if ip6 == "none":
                ip6 = "-"

            # Will be set already by a corrupt jail
            status = False
            if state != 'CORRUPT':
                status, jid = self.list_get_jid(uuid_full)

                if status:
                    state = "up"
                else:
                    state = "down"

            if conf["type"] == "template":
                template = "-"
            else:
                jail_root = Dataset(f'{jail.name}/root')
                _origin_property = jail_root.properties.get('origin')

                if _origin_property:
                    template = _origin_property
                    template = template.rsplit("/root@", 1)[0].rsplit(
                        "/", 1)[-1]
                else:
                    template = "-"

            if "release" in template.lower() or "stable" in template.lower():
                template = "-"

            if iocage_lib.ioc_common.check_truthy(
                conf['dhcp']
            ) and status and os.geteuid() == 0:
                interface = conf["interfaces"].split(",")[0].split(":")[0]

                if interface == "vnet0":
                    # Inside jails they are epairNb
                    interface = f"{interface.replace('vnet', 'epair')}b"

                short_ip4 = "DHCP"
                full_ip4_cmd = ["jexec", f"ioc-{uuid_full.replace('.', '_')}",
                                "ifconfig", interface, "inet"]
                try:
                    out = su.check_output(full_ip4_cmd)
                    full_ip4 = f'{interface}|' \
                        f'{out.splitlines()[2].split()[1].decode()}'
                except (su.CalledProcessError, IndexError) as e:
                    short_ip4 += '(Network Issue)'
                    if isinstance(e, su.CalledProcessError):
                        full_ip4 = f'DHCP - Network Issue: {e}'
                    else:
                        full_ip4 = f'DHCP - Failed Parsing: {e}'
            elif iocage_lib.ioc_common.check_truthy(
                conf['dhcp']
            ) and not status:
                short_ip4 = "DHCP"
                full_ip4 = "DHCP (not running)"
            elif iocage_lib.ioc_common.check_truthy(
                conf['dhcp']
            ) and os.geteuid() != 0:
                short_ip4 = "DHCP"
                full_ip4 = "DHCP (running -- address requires root)"

            # Append the JID and the NAME to the table

            if self.full and self.plugin:
                if jail_type != "plugin" and jail_type != "pluginv2":
                    # We only want plugin type jails to be apart of the
                    # list

                    continue

                try:
                    with open(f"{mountpoint}/plugin/ui.json", "r") as u:
                        # We want to ensure that we show the correct NAT
                        # ports for nat based plugins and when NAT isn't
                        # desired, we don't show them at all. In all these
                        # variable values, what persists across NAT/DHCP/Static
                        # ip based plugins is that the internal ports of the
                        # jail don't change. For example if a plugin jail has
                        # nginx running on port 4000, it will still want to
                        # have it running on 4000 regardless of the fact
                        # how user configures to start the plugin jail. We take
                        # this fact, and search for an explicit specified port
                        # number in the admin portal, if none is found, that
                        # means that it is ( 80 - default for http ).

                        nat_forwards_dict = {}
                        nat_forwards = conf.get('nat_forwards', 'none')
                        for rule in nat_forwards.split(
                            ','
                        ) if nat_forwards != 'none' else ():
                            # Rule can be proto(port), proto(in/out), port
                            if rule.isdigit():
                                jail = host = rule
                            else:
                                rule = rule.split('(')[-1].strip(')')
                                if ':' in rule:
                                    jail, host = rule.split(':')
                                else:
                                    # only one port provided
                                    jail = host = rule

                            nat_forwards_dict[int(jail)] = int(host)

                        if not conf.get('nat'):
                            all_ips = map(
                                lambda v: 'DHCP' if 'dhcp' in v.lower() else v,
                                [
                                    i.split('|')[-1].split('/')[0].strip()
                                    for i in full_ip4.split(',')
                                ]
                            )
                        else:
                            default_gateways = \
                                iocage_lib.ioc_common.get_host_gateways()

                            all_ips = [
                                f['addr']
                                for k in default_gateways
                                if default_gateways[k]['interface']
                                for f in netifaces.ifaddresses(
                                    default_gateways[k]['interface']
                                )[netifaces.AF_INET
                                    if k == 'ipv4' else netifaces.AF_INET6]
                            ]

                        ui_data = json.load(u)
                        admin_portal = ui_data["adminportal"]
                        admin_portals = []
                        for portal in admin_portal.split(','):
                            if conf.get('nat'):
                                portal_uri = urllib.parse.urlparse(portal)
                                portal_port = portal_uri.port or 80
                                # We do this safely as it's possible
                                # dev hasn't added it to plugin's json yet
                                nat_port = nat_forwards_dict.get(portal_port)
                                if nat_port:
                                    uri = portal_uri._replace(
                                        netloc=f'{portal_uri._hostinfo[0]}:'
                                               f'{nat_port}'
                                    ).geturl()
                                else:
                                    uri = portal
                            else:
                                uri = portal

                            admin_portals.append(
                                ','.join(
                                    map(
                                        lambda v: uri.replace(
                                            '%%IP%%', v),
                                        all_ips
                                    )
                                )
                            )

                        admin_portal = ','.join(admin_portals)

                        try:
                            ph = ui_data["adminportal_placeholders"].items()
                            if ph and not status:
                                admin_portal = f"{uuid} is not running!"
                            else:
                                for placeholder, prop in ph:
                                    admin_portal = admin_portal.replace(
                                        placeholder,
                                        iocage_lib.ioc_json.IOCJson(
                                            mountpoint).json_plugin_get_value(
                                            prop.split("."))
                                    )
                        except KeyError:
                            pass
                        except iocage_lib.ioc_exceptions.CommandNeedsRoot:
                            admin_portal = "Admin Portal requires root"
                        except iocage_lib.ioc_exceptions.CommandFailed as e:
                            admin_portal = b' '.join(e.message).decode()

                        doc_url = ui_data.get('docurl', '-')

                except FileNotFoundError:
                    # They just didn't set a admin portal.
                    admin_portal = doc_url = '-'

                jail_list.append([jid, uuid, boot, state, jail_type,
                                  full_release, full_ip4, ip6, template,
                                  admin_portal, doc_url])
                if self.plugin_data:
                    if conf['plugin_repository'] not in plugin_index_data:
                        repo_obj = iocage_lib.ioc_plugin.IOCPlugin(
                            git_repository=conf['plugin_repository']
                        )
                        if not os.path.exists(repo_obj.git_destination):
                            repo_obj.pull_clone_git_repo()
                        with open(
                            os.path.join(repo_obj.git_destination, 'INDEX')
                        ) as f:
                            plugin_index_data[conf['plugin_repository']] = \
                                json.loads(f.read())

                    index_plugin_conf = plugin_index_data[
                        conf['plugin_repository']
                    ].get(conf['plugin_name'], {})
                    jail_list[-1].extend([
                        conf['plugin_name'], conf['plugin_repository'],
                        index_plugin_conf.get('primary_pkg'),
                        index_plugin_conf.get('category'),
                        index_plugin_conf.get('maintainer'),
                    ])
            elif self.full:
                jail_list.append([jid, uuid, boot, state, jail_type,
                                  full_release, full_ip4, ip6, template,
                                  basejail])
            else:
                jail_list.append([jid, uuid, state, short_release, short_ip4])

        list_type = "list_full" if self.full else "list_short"
        sort = iocage_lib.ioc_common.ioc_sort(list_type,
                                              self.sort, data=jail_list)
        jail_list.sort(key=sort)

        # return the list...

        if not self.header:
            flat_jail = [j for j in jail_list]

            return flat_jail

        # Prints the table
        table = texttable.Texttable(max_width=0)

        if self.full:
            if self.plugin:
                table.set_cols_dtype(["t", "t", "t", "t", "t", "t", "t", "t",
                                      "t", "t", "t"])

                jail_list.insert(0, ["JID", "NAME", "BOOT", "STATE", "TYPE",
                                     "RELEASE", "IP4", "IP6", "TEMPLATE",
                                     "PORTAL", "DOC_URL"])
            else:
                # We get an infinite float otherwise.
                table.set_cols_dtype(["t", "t", "t", "t", "t", "t", "t", "t",
                                      "t", "t"])

                jail_list.insert(0, ["JID", "NAME", "BOOT", "STATE", "TYPE",
                                     "RELEASE", "IP4", "IP6", "TEMPLATE",
                                     'BASEJAIL'])
        else:
            # We get an infinite float otherwise.
            table.set_cols_dtype(["t", "t", "t", "t", "t"])
            jail_list.insert(0, ["JID", "NAME", "STATE", "RELEASE", "IP4"])

        table.add_rows(jail_list)

        return table.draw()

    def list_bases(self, datasets):
        """Lists all bases."""
        base_list = iocage_lib.ioc_common.ioc_sort(
            "list_release", "release", data=datasets)
        table = texttable.Texttable(max_width=0)

        if not self.header:
            flat_base = [b for b in base_list for b in b]

            return flat_base

        base_list.insert(0, ["Bases fetched"])
        table.add_rows(base_list)
        # We get an infinite float otherwise.
        table.set_cols_dtype(["t"])

        return table.draw()

    @classmethod
    def list_get_jid(cls, uuid):
        """Return a tuple containing True or False and the jail's id or '-'."""
        try:
            jid = iocage_lib.ioc_common.checkoutput(
                ["jls", "-j", f"ioc-{uuid.replace('.', '_')}"],
                stderr=su.PIPE).split()[5]

            return True, jid
        except su.CalledProcessError:
            return False, "-"
