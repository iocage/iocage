"""fstab module for the cli."""
import logging

import click

from iocage.lib.ioc_fstab import IOCFstab
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList

__cmdname__ = "fstab_cmd"
__rootcmd__ = True


@click.command(name="fstab", help="Manipulate the specified jails fstab.")
@click.argument("jail")
@click.argument("fstab_string", nargs=-1)
@click.option("--add", "-a", "action",
              help="Adds an entry to the jails fstab and mounts it.",
              flag_value="add")
@click.option("--remove", "-r", "action",
              help="Removes an entry from the jails fstab and unmounts it.",
              flag_value="remove")
@click.option("--edit", "-e", "action",
              help="Opens up the fstab file in your environments EDITOR.",
              flag_value="edit")
def fstab_cmd(action, fstab_string, jail):
    """
    Looks for the jail supplied and passes the uuid, path and configuration
    location to manipulate the fstab.
    """
    lgr = logging.getLogger('ioc_cli_fstab')
    pool = IOCJson().json_get_value("pool")
    iocroot = IOCJson(pool).json_get_value("iocroot")
    index = None
    _index = False
    fstab_string = list(fstab_string)

    _jails, paths = IOCList("uuid").list_datasets()

    if not fstab_string and action != "edit":
        raise RuntimeError("Please supply a fstab entry!")

    _jail = {tag: uuid for (tag, uuid) in _jails.items() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(iter(_jail.items()))
    elif len(_jail) > 1:
        lgr.error("Multiple jails found for"
                  " {}:".format(jail))
        for t, u in sorted(_jail.items()):
            lgr.error("  {} ({})".format(u, t))
        raise RuntimeError()
    else:
        raise RuntimeError("{} not found!".format(jail))

    # The user will expect to supply a string, the API would prefer these
    # separate. If the user supplies a quoted string, we will split it,
    # otherwise the format is acceptable to be imported directly.
    if len(fstab_string) == 1:
        try:
            source, destination, fstype, options, dump, _pass = fstab_string[
                0].split()
        except ValueError:
            # We're going to assume this is an index number.
            try:
                index = int(fstab_string[0])
            except TypeError:
                raise RuntimeError("Please specify either a valid fstab "
                                   "entry or an index number.")
            _index = True
            source, destination, fstype, options, dump, _pass = "", "", "", \
                                                                "", "", ""
    else:
        if action != "edit":
            try:
                source, destination, fstype, options, dump, _pass = \
                    fstab_string
            except ValueError:
                raise RuntimeError("Please specify a valid fstab entry!\n\n"
                                   "Example:\n  /the/source /dest FSTYPE "
                                   "FSOPTIONS FSDUMP FSPASS")
        else:
            source, destination, fstype, options, dump, _pass = "", "", \
                                                                "", "", \
                                                                "", ""

    if not _index and action == "add":
        destination = "{}/jails/{}/root".format(iocroot, uuid) + destination

    IOCFstab(uuid, tag, action, source, destination, fstype, options, dump,
             _pass, index=index)
