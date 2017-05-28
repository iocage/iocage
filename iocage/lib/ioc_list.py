"""List all datasets by type"""
import re
import subprocess as su

import libzfs
import texttable

import iocage.lib.ioc_common
import iocage.lib.ioc_json


class IOCList(object):
    """
    List jails that are a specified type.

    Format is:
        JID UID BOOT STATE TAG TYPE IP4 RELEASE
    """

    def __init__(self, lst_type="all", hdr=True, full=False, _sort=None,
                 silent=False, callback=None):
        self.list_type = lst_type
        self.header = hdr
        self.full = full
        self.pool = iocage.lib.ioc_json.IOCJson().json_get_value("pool")
        self.zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")
        self.sort = _sort
        self.silent = silent
        self.callback = callback

    def list_datasets(self, set=False):
        """Lists the datasets of given type."""

        if self.list_type == "all" or self.list_type == "uuid":
            ds = self.zfs.get_dataset(f"{self.pool}/iocage/jails").children
        elif self.list_type == "base":
            ds = self.zfs.get_dataset(f"{self.pool}/iocage/releases").children
        elif self.list_type == "template":
            ds = self.zfs.get_dataset(
                f"{self.pool}/iocage/templates").children

        if self.list_type == "all":
            _all = self.list_all(ds)

            return _all
        elif self.list_type == "uuid":
            jails = {}
            paths = {}
            dups = {}

            for jail in ds:
                jail = jail.properties["mountpoint"].value
                conf = iocage.lib.ioc_json.IOCJson(jail).json_load()

                if not set and conf["tag"] in jails:
                    # Add the original in
                    dups[paths[conf["tag"]]] = conf["tag"]
                    dups[jail] = conf["tag"]
                    tag = conf["tag"]

                jails[conf["tag"]] = conf["host_hostuuid"]
                paths[conf["tag"]] = jail

            template_datasets = self.zfs.get_dataset(
                f"{self.pool}/iocage/templates")
            template_datasets = template_datasets.children

            for template in template_datasets:
                template = template.properties["mountpoint"].value
                conf = iocage.lib.ioc_json.IOCJson(template).json_load()

                jails[f"{conf['tag']} (template)"] = conf["host_hostuuid"]
                paths[f"{conf['tag']} (template)"] = template

            if len(dups):
                iocage.lib.ioc_common.logit({
                    "level"  : "ERROR",
                    "message": f"Duplicate tag ({tag}) detected!"
                },
                    _callback=self.callback,
                    silent=self.silent)
                for d, t in sorted(dups.items()):
                    u = [m for m in d.split("/") if len(m) == 36 or len(m)
                         == 8][0]
                    iocage.lib.ioc_common.logit({
                        "level"  : "ERROR",
                        "message": f"  {u} ({t})"
                    },
                        _callback=self.callback,
                        silent=self.silent)
                iocage.lib.ioc_common.logit({
                    "level"  : "ERROR",
                    "message": "\nPlease run \"iocage set tag=NEWTAG "
                               "UUID\" for one of the UUID's."
                },
                    _callback=self.callback,
                    silent=self.silent)
                raise RuntimeError()

            return jails, paths
        elif self.list_type == "base":
            bases = self.list_bases(ds)

            return bases
        elif self.list_type == "template":
            templates = self.list_all(ds)

            return templates

    def list_all(self, jails):
        """List all jails."""
        table = texttable.Texttable(max_width=0)
        jail_list = []

        for jail in jails:
            mountpoint = jail.properties["mountpoint"].value
            conf = iocage.lib.ioc_json.IOCJson(mountpoint).json_load()

            uuid = conf["host_hostuuid"]
            full_ip4 = conf["ip4_addr"]
            ip6 = conf["ip6_addr"]
            jail_root = f"{self.pool}/iocage/jails/{uuid}/root"

            try:
                short_ip4 = full_ip4.split("|")[1].split("/")[0]
            except IndexError:
                short_ip4 = "-"

            tag = conf["tag"]
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

            status, jid = self.list_get_jid(uuid)

            if status:
                state = "up"
            else:
                state = "down"

            if conf["type"] == "template":
                template = "-"
            else:
                _origin_property = jail.properties["origin"]
                if _origin_property and (_origin_property.value != ""):
                    template = jail.properties["origin"].value
                else:
                    template = "-"

            if "release" in template.lower() or "stable" in template.lower():
                template = "-"

            # Append the JID and the UUID to the table
            if self.full:
                jail_list.append([jid, uuid, boot, state, tag, jail_type,
                                  full_release, full_ip4, ip6, template])
            else:
                jail_list.append([jid, uuid[:8], state, tag, short_release,
                                  short_ip4])

        list_type = "list_full" if self.full else "list_short"
        sort = iocage.lib.ioc_common.ioc_sort(list_type, self.sort,
                                              data=jail_list)
        jail_list.sort(key=sort)

        # Prints the table
        if self.header:
            if self.full:
                # We get an infinite float otherwise.
                table.set_cols_dtype(["t", "t", "t", "t", "t", "t", "t", "t",
                                      "t", "t"])
                jail_list.insert(0, ["JID", "UUID", "BOOT", "STATE", "TAG",
                                     "TYPE", "RELEASE", "IP4", "IP6",
                                     "TEMPLATE"])
            else:
                # We get an infinite float otherwise.
                table.set_cols_dtype(["t", "t", "t", "t", "t", "t"])
                jail_list.insert(0, ["JID", "UUID", "STATE", "TAG",
                                     "RELEASE", "IP4"])

            table.add_rows(jail_list)

            return table.draw()
        else:
            flat_jail = [j for j in jail_list]

            return flat_jail

    def list_bases(self, datasets):
        """Lists all bases."""
        base_list = iocage.lib.ioc_common.ioc_sort("list_release", "release",
                                                   data=datasets)
        table = texttable.Texttable(max_width=0)

        if self.header:
            base_list.insert(0, ["Bases fetched"])
            table.add_rows(base_list)
            # We get an infinite float otherwise.
            table.set_cols_dtype(["t"])

            return table.draw()
        else:
            flat_base = [b for b in base_list for b in b]

            return flat_base

    @classmethod
    def list_get_jid(cls, uuid):
        """Return a tuple containing True or False and the jail's id or '-'."""
        try:
            jid = iocage.lib.ioc_common.checkoutput(
                ["jls", "-j", f"ioc-{uuid}"], stderr=su.PIPE).split()[5]
            return True, jid
        except su.CalledProcessError:
            return False, "-"
