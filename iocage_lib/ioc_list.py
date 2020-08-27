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
import os
import re
import subprocess as su
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
        active_jails = iocage_lib.ioc_common.get_active_jails()
        default_gateways = iocage_lib.ioc_common.get_host_gateways()
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
            jid = None
            if state != 'CORRUPT':
                jid = active_jails.get(f'ioc-{uuid.replace(".", "_")}', {}).get('jid')
                state = 'up' if jid else 'down'

            if conf["type"] == "template":
                template = "-"
            else:
                jail_root = Dataset(f'{jail.name}/root')
                if jail_root.exists:
                    _origin_property = jail_root.properties.get('origin')
                else:
                    _origin_property = None

                if _origin_property:
                    template = _origin_property
                    template = template.rsplit("/root@", 1)[0].rsplit(
                        "/", 1)[-1]
                else:
                    template = "-"

            if "release" in template.lower() or "stable" in template.lower():
                template = "-"

            ip_dict = iocage_lib.ioc_common.retrieve_ip4_for_jail(conf, bool(jid))
            full_ip4 = ip_dict['full_ip4'] or full_ip4
            short_ip4 = ip_dict['short_ip4'] or short_ip4

            # Append the JID and the NAME to the table

            if self.full and self.plugin:
                if jail_type != "plugin" and jail_type != "pluginv2":
                    # We only want plugin type jails to be apart of the
                    # list

                    continue

                try:
                    with open(f"{mountpoint}/plugin/ui.json", "r") as u:
                        ui_data = json.load(u)
                        admin_portal = ','.join(
                            iocage_lib.ioc_common.retrieve_admin_portals(
                                conf, bool(jid), ui_data['adminportal'], default_gateways, ip_dict
                            )
                        )
                        try:
                            ph = ui_data["adminportal_placeholders"].items()
                            if ph and not bool(jid):
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
                            try:
                                repo_obj.pull_clone_git_repo()
                            except Exception as e:
                                iocage_lib.ioc_common.logit(
                                    {
                                        'level': 'ERROR',
                                        'message':
                                            'Failed to clone '
                                            f'{conf["plugin_repository"]} '
                                            f'for {uuid_full}: {e}'
                                    },
                                    _callback=self.callback,
                                    silent=self.silent
                                )
                        index_path = os.path.join(
                            repo_obj.git_destination, 'INDEX'
                        )
                        if not os.path.exists(index_path):
                            iocage_lib.ioc_common.logit(
                                {
                                    'level': 'ERROR',
                                    'message':
                                        f'{index_path} does not exist '
                                        f'for {uuid_full} plugin.'
                                },
                                _callback=self.callback,
                                silent=self.silent
                            )
                            plugin_index_data[
                                conf['plugin_repository']
                            ] = {}
                        else:
                            with open(index_path) as f:
                                plugin_index_data[
                                    conf['plugin_repository']
                                ] = json.loads(f.read())
                    elif not plugin_index_data[conf['plugin_repository']]:
                        iocage_lib.ioc_common.logit(
                            {
                                'level': 'ERROR',
                                'message':
                                    'Unable to retrieve INDEX from '
                                    f'{conf["plugin_repository"]} for '
                                    f'{uuid_full}'
                            },
                            _callback=self.callback,
                            silent=self.silent
                        )

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
