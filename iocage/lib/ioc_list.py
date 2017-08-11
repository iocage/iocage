# Copyright (c) 2014-2017, iocage
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

import libzfs
import texttable

import iocage.lib.ioc_common
import iocage.lib.ioc_json


class IOCList(object):
    """
    List jails that are a specified type.

    Format is:
        JID UID BOOT STATE TYPE IP4 RELEASE
    """

    def __init__(self, lst_type="all", hdr=True, full=False, _sort=None,
                 exit_on_error=False, silent=False, callback=None,
                 plugin=False, quick=False):
        self.list_type = lst_type
        self.header = hdr
        self.full = full
        self.pool = iocage.lib.ioc_json.IOCJson().json_get_value("pool")
        self.zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")
        self.sort = _sort
        self.exit_on_error = exit_on_error
        self.silent = silent
        self.callback = callback
        self.plugin = plugin
        self.quick = quick

    def list_datasets(self):
        """Lists the datasets of given type."""

        if self.list_type == "all" or self.list_type == "uuid":
            ds = self.zfs.get_dataset(f"{self.pool}/iocage/jails").children
        elif self.list_type == "base":
            ds = self.zfs.get_dataset(f"{self.pool}/iocage/releases").children
        elif self.list_type == "template":
            ds = self.zfs.get_dataset(
                f"{self.pool}/iocage/templates").children

        if self.list_type == "all":
            if self.quick:
                _all = self.list_all_quick(ds)
            else:
                _all = self.list_all(ds)

            return _all
        elif self.list_type == "uuid":
            jails = {}

            for jail in ds:
                uuid = jail.name.rsplit("/", 1)[-1]
                jails[uuid] = jail.properties["mountpoint"].value

            template_datasets = self.zfs.get_dataset(
                f"{self.pool}/iocage/templates")
            template_datasets = template_datasets.children

            for template in template_datasets:
                uuid = template.name.rsplit("/", 1)[-1]
                jails[uuid] = template.properties["mountpoint"].value

            return jails
        elif self.list_type == "base":
            bases = self.list_bases(ds)

            return bases
        elif self.list_type == "template":
            templates = self.list_all(ds)

            return templates

    def list_all_quick(self, jails):
        """Returns a table of jails with minimal processing"""
        jail_list = []

        for jail in jails:
            mountpoint = jail.properties["mountpoint"].value

            try:
                with open(f"{mountpoint}/config.json", "r") as loc:
                    conf = json.load(loc)
            except FileNotFoundError:
                uuid = mountpoint.rsplit("/", 1)[-1]
                iocage.lib.ioc_common.logit({
                    "level"  : "EXCEPTION",
                    "message": f"{uuid} is missing its configuration file."
                               "\nPlease run just 'list' instead to create"
                               " it."
                }, exit_on_error=self.exit_on_error, _callback=self.callback,
                    silent=self.silent)

            uuid = conf["host_hostuuid"]
            ip4 = conf["ip4_addr"]

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

        for jail in jails:
            mountpoint = jail.properties["mountpoint"].value
            conf = iocage.lib.ioc_json.IOCJson(mountpoint).json_load()

            uuid = conf["host_hostuuid"]

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
                short_ip4 = full_ip4.split("|")[1].split("/")[0]
            except IndexError:
                short_ip4 = "-"

            boot = conf["boot"]
            jail_type = conf["type"]
            full_release = conf["release"]

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

            status, jid = self.list_get_jid(uuid)

            if status:
                state = "up"
            else:
                state = "down"

            if conf["type"] == "template":
                template = "-"
            else:
                jail_root = self.zfs.get_dataset(f"{jail.name}/root")
                _origin_property = jail_root.properties["origin"]

                if _origin_property and _origin_property.value != "":
                    template = jail_root.properties["origin"].value
                    template = template.rsplit("/root@", 1)[0].rsplit(
                        "/", 1)[-1]
                else:
                    template = "-"

            if "release" in template.lower() or "stable" in template.lower():
                template = "-"

            if conf["dhcp"] == "on" and status and os.geteuid() == 0:
                interface = conf["interfaces"].split(",")[0].split(":")[0]
                short_ip4 = "DHCP"
                full_ip4_cmd = ["jexec", f"ioc-{uuid}", "ifconfig",
                                interface, "inet"]
                out = su.check_output(full_ip4_cmd)
                full_ip4 = f"{interface}|" \
                           f"{out.splitlines()[2].split()[1].decode()}"
            elif conf["dhcp"] == "on" and not status:
                short_ip4 = "DHCP"
                full_ip4 = "DHCP (not running)"
            elif conf["dhcp"] == "on" and os.geteuid() != 0:
                short_ip4 = "DHCP"
                full_ip4 = "DHCP (running -- address requires root)"

            # Append the JID and the NAME to the table
            if self.full:
                if self.plugin:
                    if jail_type != "plugin":
                        # We only want plugin type jails to be apart of the
                        # list
                        continue

                jail_list.append([jid, uuid, boot, state, jail_type,
                                  full_release, full_ip4, ip6, template])
            else:
                jail_list.append([jid, uuid, state, short_release, short_ip4])

        list_type = "list_full" if self.full else "list_short"
        sort = iocage.lib.ioc_common.ioc_sort(list_type,
                                              self.sort, data=jail_list,
                                              exit_on_error=self.exit_on_error)
        jail_list.sort(key=sort)

        # return the list...
        if not self.header:
            flat_jail = [j for j in jail_list]

            return flat_jail

        # Prints the table
        table = texttable.Texttable(max_width=0)

        if self.full:
            # We get an infinite float otherwise.
            table.set_cols_dtype(["t", "t", "t", "t", "t", "t", "t", "t", "t"])
            jail_list.insert(0, ["JID", "NAME", "BOOT", "STATE", "TYPE",
                                 "RELEASE", "IP4", "IP6", "TEMPLATE"])
        else:
            # We get an infinite float otherwise.
            table.set_cols_dtype(["t", "t", "t", "t", "t"])
            jail_list.insert(0, ["JID", "NAME", "STATE", "RELEASE", "IP4"])

        table.add_rows(jail_list)

        return table.draw()

    def list_bases(self, datasets):
        """Lists all bases."""
        base_list = iocage.lib.ioc_common.ioc_sort(
            "list_release", "release", data=datasets,
            exit_on_error=self.exit_on_error)
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
            jid = iocage.lib.ioc_common.checkoutput(
                ["jls", "-j", f"ioc-{uuid.replace('.', '_')}"],
                stderr=su.PIPE).split()[5]
            return True, jid
        except su.CalledProcessError:
            return False, "-"
