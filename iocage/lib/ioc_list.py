"""List all datasets by type"""
import logging
from subprocess import CalledProcessError, PIPE

import libzfs
from texttable import Texttable

from iocage.lib.ioc_common import checkoutput, sort_release, sort_tag
from iocage.lib.ioc_json import IOCJson


class IOCList(object):
    """
    List jails that are a specified type.

    Format is:
        JID UID BOOT STATE TAG TYPE IP4 RELEASE
    """

    def __init__(self, lst_type="all", hdr=True, full=False):
        self.list_type = lst_type
        self.header = hdr
        self.full = full
        self.pool = IOCJson().json_get_value("pool")
        self.iocroot = IOCJson(self.pool).json_get_value("iocroot")
        self.lgr = logging.getLogger('ioc_list')

    def list_datasets(self, set=False):
        """Lists the datasets of given type."""
        zfs = libzfs.ZFS()

        if self.list_type == "all" or self.list_type == "uuid":
            # List the datasets underneath self.POOL/iocroot/jails
            datasets = zfs.get_dataset(f"{self.pool}/iocage/jails").children
        elif self.list_type == "base":
            # List the datasets underneath self.POOL/iocroot/releases
            datasets = zfs.get_dataset(f"{self.pool}/iocage/releases").children
        elif self.list_type == "template":
            # List the datasets underneath self.POOL/iocroot/releases
            datasets = zfs.get_dataset(
                f"{self.pool}/iocage/templates").children

        if self.list_type == "all":
            _all = self.list_all(datasets)

            return _all
        elif self.list_type == "uuid":
            jails = {}
            paths = {}
            dups = {}

            for jail in datasets:
                jail = jail.name.strip(self.pool)
                conf = IOCJson(jail).json_load()

                if not set and conf["tag"] in jails:
                    # Add the original in
                    dups[paths[conf["tag"]]] = conf["tag"]
                    dups[jail] = conf["tag"]
                    tag = conf["tag"]

                jails[conf["tag"]] = conf["host_hostuuid"]
                paths[conf["tag"]] = jail

            template_datasets = zfs.get_dataset(
                f"{self.pool}/iocage/templates")
            template_datasets = template_datasets.children

            for template in template_datasets:
                template = template.name.strip(self.pool)
                conf = IOCJson(template).json_load()

                jails[conf["tag"]] = conf["host_hostuuid"]
                paths[conf["tag"]] = template

            if len(dups):
                self.lgr.error(f"ERROR: Duplicate tag ({tag}) detected!")
                for d, t in sorted(dups.items()):
                    u = [m for m in d.split("/") if len(m) == 36 or len(m)
                         == 8][0]
                    self.lgr.error("  {} ({})".format(u, t))
                self.lgr.error("\nPlease run \"iocage set tag=NEWTAG "
                               "UUID\" for one of the UUID's.")
                raise RuntimeError()

            return jails, paths
        elif self.list_type == "base":
            bases = self.list_bases(datasets)

            return bases
        elif self.list_type == "template":
            templates = self.list_all(datasets)

            return templates

    def list_all(self, jails):
        """List all jails."""
        table = Texttable(max_width=0)
        jail_list = []

        for jail in jails:
            jail = jail.name.strip(self.pool)
            conf = IOCJson(jail).json_load()

            uuid = conf["host_hostuuid"]
            full_ip4 = conf["ip4_addr"]
            jail_root = "{}/iocage/jails/{}/root".format(self.pool, uuid)

            try:
                short_ip4 = full_ip4.split("|")[1].split("/")[0]
            except IndexError:
                short_ip4 = "-"

            tag = conf["tag"]
            boot = conf["boot"]
            jail_type = conf["type"]
            full_release = conf["release"]

            if "HBSD" in full_release:
                full_release = "{}-STABLE-HBSD".format(full_release.split(
                    ".")[0])
                short_release = "{}-STABLE".format(full_release.rsplit("-")[0])
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
                try:
                    template = checkoutput(["zfs", "get", "-H", "-o", "value",
                                            "origin",
                                            jail_root]).split("/")[3]
                except IndexError:
                    template = "-"

            if "release" in template.lower() or "stable" in template.lower():
                template = "-"

            # Append the JID and the UUID to the table
            if self.full:
                jail_list.append([jid, uuid, boot, state, tag, jail_type,
                                  full_ip4, full_release, template])
            else:
                jail_list.append([jid, uuid[:8], state, tag, short_release,
                                  short_ip4])

        jail_list.sort(key=sort_tag)

        # Prints the table
        if self.header:
            if self.full:
                # We get an infinite float otherwise.
                table.set_cols_dtype(["t", "t", "t", "t", "t", "t", "t", "t",
                                      "t"])
                jail_list.insert(0, ["JID", "UUID", "BOOT", "STATE", "TAG",
                                     "TYPE", "IP4", "RELEASE", "TEMPLATE"])
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
        base_list = sort_release(datasets, self.iocroot, split=True)
        table = Texttable(max_width=0)

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
            jid = checkoutput(["jls", "-j", "ioc-{}".format(uuid)],
                              stderr=PIPE).split()[5]
            return (True, jid)
        except CalledProcessError:
            return (False, "-")
