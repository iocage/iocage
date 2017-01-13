"""This is responsible for getting a jail property."""
import logging

import click
from tabletext import to_text

from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList

__cmdname__ = "get_cmd"


@click.command(name="get", help="Gets the specified property.")
@click.argument("prop")
@click.argument("jail", required=True, default="")
@click.option("--header", "-h", "-H", is_flag=True, default=True,
              help="For scripting, use tabs for separators.")
@click.option("--recursive", "-r", help="Get the specified property for all " +
                                        "jails.", flag_value="recursive")
def get_cmd(prop, jail, recursive, header):
    """Get a list of jails and print the property."""
    lgr = logging.getLogger('ioc_cli_get')

    get_jid = IOCList.get_jid
    jails, paths = IOCList("uuid").get_datasets()
    jail_list = []

    if recursive is None:
        if jail == "":
            lgr.info("Usage: iocage get [OPTIONS] PROP JAIL\n")
            raise RuntimeError("Error: Missing argument \"jail\".")

        _jail = {tag: uuid for (tag, uuid) in jails.iteritems() if
                 uuid.startswith(jail) or tag == jail}

        if len(_jail) == 1:
            tag, uuid = next(_jail.iteritems())
            path = paths[tag]
        elif len(_jail) > 1:
            lgr.error("Multiple jails found for"
                      " {}:".format(jail))
            for t, u in sorted(_jail.iteritems()):
                lgr.error("  {} ({})".format(u, t))
            raise RuntimeError()
        else:
            raise RuntimeError("{} not found!".format(jail))

        if prop == "state":
            status = get_jid(path.split("/")[3])[0]

            if status:
                state = "up"
            else:
                state = "down"

            lgr.info(state)
        else:
            try:
                lgr.info(IOCJson(path).get_prop_value(prop))
            except:
                raise RuntimeError("{} is not a valid property!".format(prop))
    else:
        for j in jails:
            uuid = jails[j]
            path = paths[j]
            try:
                if prop == "state":
                    status = get_jid(path.split("/")[3])[0]

                    if status:
                        state = "up"
                    else:
                        state = "down"

                    jail_list.append([j, state])
                else:
                    jail_list.append(
                            [uuid, j, IOCJson(path).get_prop_value(prop)])
            except:
                raise RuntimeError("{} is not a valid property!".format(prop))

        # Prints the table
        if header:
            jail_list.insert(0, ["UUID", "TAG", "PROP - {}".format(prop)])
            lgr.info(to_text(jail_list, header=True, hor="-", ver="|",
                             corners="+"))
        else:
            for jail in jail_list:
                lgr.info("\t".join(jail))
