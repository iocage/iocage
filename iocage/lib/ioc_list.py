"""
List all datasets by type
"""
import logging
from subprocess import CalledProcessError, PIPE, Popen, check_output

import re
from tabletext import to_text

import iocage.lib.ioc_common as ioc_common
from iocage.lib.ioc_json import IOCJson


class IOCList(object):
    """
    List jails that are a specified type.

    Format is:
        JID UID BOOT STATE TAG TYPE IP4 RELEASE
    """

    def __init__(self, lst_type="all", hdr=True, full=False, rtrn_object=False):
        self.list_type = lst_type
        self.header = hdr
        self.full = full
        self.return_object = rtrn_object
        self.pool = IOCJson().get_prop_value("pool")
        self.iocroot = IOCJson(self.pool).get_prop_value("iocroot")
        self.lgr = logging.getLogger('ioc_list')

    def get_datasets(self, set=False):
        """Lists the datasets of given type."""

        if self.list_type == "all" or self.list_type == "uuid":
            # List the datasets underneath self.POOL/iocroot/jails
            cmd = ["zfs", "list", "-rHd", "1",
                   "{}{}/jails".format(self.pool, self.iocroot)]

            # UUIDS are 12345678-1234-1234-1234-123456789012
            regex = re.compile("{}/jails/".format(self.iocroot) +
                               "\\w{8}-(\\w{4}-){3}\\w{12}")
        elif self.list_type == "base":
            # List the datasets underneath self.POOL/iocroot/releases
            cmd = ["zfs", "list", "-rHd", "1",
                   "{}{}/releases".format(self.pool,
                                          self.iocroot)]

            # Format is Major.Minor-{RELEASE,STABLE,CURRENT,BETA,ALPHA,RC}
            # TODO: Support other "bases" besides RELEASE?
            regex = re.compile("{}/releases/".format(self.iocroot) +
                               "\\w*.\\w-RELEASE")

        zfs_list = Popen(cmd, stdout=PIPE).communicate()[0].split()
        datasets = [d for d in zfs_list if re.match(regex, d)]

        if self.list_type == "all":
            self.list_all(datasets)
        elif self.list_type == "uuid":
            jails = {}
            paths = {}
            dups = {}

            for jail in datasets:
                conf = IOCJson(jail).load_json()

                if not set and conf["tag"] in jails:
                    # Add the original in
                    dups[paths[conf["tag"]]] = conf["tag"]
                    dups[jail] = conf["tag"]
                    tag = conf["tag"]

                jails[conf["tag"]] = conf["host_hostuuid"]
                paths[conf["tag"]] = jail

            if len(dups):
                self.lgr.error("ERROR: Duplicate tag ({}) detected!".format(
                    tag
                ))
                for d, t in sorted(dups.iteritems()):
                    u = d.split("/")[3]
                    self.lgr.error("  {} ({})".format(u, t))
                self.lgr.error("\nPlease run \"iocage set tag=NEWTAG "
                               "UUID\" for one of the UUID's.")
                raise RuntimeError()

            return jails, paths
        elif self.list_type == "base":
            bases = self.list_bases(datasets)

            if self.return_object:
                return bases

    def list_all(self, jails):
        """List all jails."""
        jail_list = []

        for jail in jails:
            conf = IOCJson(jail).load_json()

            full_uuid = conf['host_hostuuid']
            full_ip4 = conf['ip4_addr']
            short_uuid = full_uuid[:8]
            try:
                short_ip4 = full_ip4.split("|")[1].split("/")[0]
            except IndexError:
                short_ip4 = "-"

            tag = conf['tag']
            boot = conf['boot']
            jail_type = conf['type']
            release = conf['release']

            if full_ip4 == "none":
                full_ip4 = "-"

            status = self.get_jid(full_uuid)
            jid = status[1]

            if status[0]:
                state = "up"
            else:
                state = "down"

            # Append the JID and the UUID to the table
            if self.full:
                jail_list.append([jid, full_uuid, boot, state, tag, jail_type,
                                  full_ip4, release])
            else:
                jail_list.append([jid, short_uuid, state, tag, short_ip4])

        jail_list.sort(key=ioc_common.sort_tag)
        # Prints the table
        if self.header:
            if self.full:
                jail_list.insert(0, ["JID", "UUID", "BOOT", "STATE", "TAG",
                                     "TYPE", "IP4", "RELEASE"])
            else:
                jail_list.insert(0, ["JID", "UUID", "STATE", "TAG", "IP4"])

            self.lgr.info(to_text(jail_list, header=True, hor="-", ver="|",
                                  corners="+"))
        else:
            for jail in jail_list:
                self.lgr.info("\t".join(jail))

    def list_bases(self, datasets):
        """Lists all bases."""
        base_list = ioc_common.sort_release(datasets, split=True)

        if self.header:
            base_list.insert(0, ["Bases fetched"])
            self.lgr.info(to_text(base_list, header=True, hor="-", ver="|",
                                  corners="+"))
        else:
            if self.return_object:
                flat_base = [x for x in base_list for x in x]
                return flat_base

            for base in base_list:
                self.lgr.info("\t".join(base))

    @classmethod
    def get_jid(cls, uuid):
        """Return a tuple containing True or False and the jail's id or '-'."""
        try:
            jid = check_output(["jls", "-j", "ioc-{}".format(uuid)],
                               stderr=PIPE).split()[5]
            return (True, jid)
        except CalledProcessError:
            return (False, "-")
