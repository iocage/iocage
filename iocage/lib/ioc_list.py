"""List all datasets by type"""
import logging
import re
from subprocess import CalledProcessError, PIPE, Popen

from texttable import Texttable

from iocage.lib.ioc_common import checkoutput, sort_release, sort_tag
from iocage.lib.ioc_json import IOCJson


class IOCList(object):
    """
    List jails that are a specified type.

    Format is:
        JID UID BOOT STATE TAG TYPE IP4 RELEASE
    """

    def __init__(self, lst_type="all", hdr=True, full=False,
                 rtrn_object=False):
        self.list_type = lst_type
        self.header = hdr
        self.full = full
        self.return_object = rtrn_object
        self.pool = IOCJson().json_get_value("pool")
        self.iocroot = IOCJson(self.pool).json_get_value("iocroot")
        self.lgr = logging.getLogger('ioc_list')

    def list_datasets(self, set=False):
        """Lists the datasets of given type."""

        if self.list_type == "all" or self.list_type == "uuid":
            # List the datasets underneath self.POOL/iocroot/jails
            cmd = ["zfs", "list", "-rHd", "1",
                   "{}/iocage/jails".format(self.pool)]

            # UUIDS are 12345678-1234-1234-1234-123456789012
            regex = re.compile("{}/jails/".format(self.iocroot) + "\\w{8}")
        elif self.list_type == "base":
            # List the datasets underneath self.POOL/iocroot/releases
            cmd = ["zfs", "list", "-rHd", "1",
                   "{}/iocage/releases".format(self.pool)]

            # Format is Major.Minor-{RELEASE,STABLE,CURRENT,BETA,ALPHA,RC}
            regex = re.compile("{}/releases/".format(self.iocroot) +
                               "\\w*.\\w")
        elif self.list_type == "template":
            # List the datasets underneath self.POOL/iocroot/releases
            cmd = ["zfs", "list", "-rHd", "1",
                   "{}/iocage/templates".format(self.pool)]

            regex = re.compile("{}/templates/".format(self.iocroot))

        zfs_list = Popen(cmd, stdout=PIPE).communicate()[0].decode(
            "utf-8").split()
        datasets = [d for d in zfs_list if re.match(regex, d)]

        if self.list_type == "all":
            self.list_all(datasets)
        elif self.list_type == "uuid":
            jails = {}
            paths = {}
            dups = {}

            for jail in datasets:
                conf = IOCJson(jail).json_load()

                if not set and conf["tag"] in jails:
                    # Add the original in
                    dups[paths[conf["tag"]]] = conf["tag"]
                    dups[jail] = conf["tag"]
                    tag = conf["tag"]

                jails[conf["tag"]] = conf["host_hostuuid"]
                paths[conf["tag"]] = jail

            template_cmd = ["zfs", "list", "-rHd", "1",
                            "{}/iocage/templates".format(self.pool)]
            template_regex = re.compile("{}/templates/".format(self.iocroot))
            template_zfs_list = Popen(template_cmd, stdout=PIPE).communicate()[
                0].decode("utf-8").split()
            template_datasets = [t for t in template_zfs_list if re.match(
                template_regex, t)]

            for template in template_datasets:
                conf = IOCJson(template).json_load()

                jails[conf["tag"]] = conf["host_hostuuid"]
                paths[conf["tag"]] = template

            if len(dups):
                self.lgr.error("ERROR: Duplicate tag ({}) detected!".format(
                    tag))
                for d, t in sorted(dups.items()):
                    u = [m for m in d.split("/") if len(m) == 36][0]
                    self.lgr.error("  {} ({})".format(u, t))
                self.lgr.error("\nPlease run \"iocage set tag=NEWTAG "
                               "UUID\" for one of the UUID's.")
                raise RuntimeError()

            return jails, paths
        elif self.list_type == "base":
            bases = self.list_bases(datasets)

            if self.return_object:
                return bases
        elif self.list_type == "template":
            templates = self.list_all(datasets)
            if self.return_object:
                return templates

    def list_all(self, jails):
        """List all jails."""
        table = Texttable(max_width=0)
        jail_list = []

        for jail in jails:
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
            self.lgr.info(table.draw())
        else:
            if self.return_object:
                flat_jail = [j[3] for j in jail_list]
                return flat_jail

            for jail in jail_list:
                self.lgr.info("\t".join(jail))

    def list_bases(self, datasets):
        """Lists all bases."""
        base_list = sort_release(datasets, self.iocroot, split=True)
        table = Texttable(max_width=0)

        if self.header:
            base_list.insert(0, ["Bases fetched"])
            table.add_rows(base_list)
            # We get an infinite float otherwise.
            table.set_cols_dtype(["t"])
            self.lgr.info(table.draw())
        else:
            if self.return_object:
                flat_base = [b for b in base_list for b in b]
                return flat_base

            for base in base_list:
                self.lgr.info("\t".join(base))

    @classmethod
    def list_get_jid(cls, uuid):
        """Return a tuple containing True or False and the jail's id or '-'."""
        try:
            jid = checkoutput(["jls", "-j", "ioc-{}".format(uuid)],
                              stderr=PIPE).split()[5]
            return (True, jid)
        except CalledProcessError:
            return (False, "-")
