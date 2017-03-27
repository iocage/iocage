"""get module for the cli."""
import json

import click
from texttable import Texttable

import iocage.lib.ioc_logger as ioc_logger
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList

__cmdname__ = "get_cmd"


@click.command(context_settings=dict(
    max_content_width=400, ), name="get", help="Gets the specified property.")
@click.argument("prop", required=True, default="")
@click.argument("jail", required=True, default="")
@click.option("--header", "-h", "-H", is_flag=True, default=True,
              help="For scripting, use tabs for separators.")
@click.option("--recursive", "-r", help="Get the specified property for all " +
                                        "jails.", flag_value="recursive")
@click.option("--plugin", "-P",
              help="Get the specified key for a plugin jail, if accessing a"
                   " nested key use . as a separator."
                   "\n\b Example: iocage get -P foo.bar.baz PLUGIN",
              is_flag=True)
@click.option("--all", "-a", "_all", help="Get all properties for the "
                                          "specified jail.", is_flag=True)
@click.option("--pool", "-p", "_pool", help="Get the currently activated "
                                            "zpool.", is_flag=True)
def get_cmd(prop, _all, _pool, jail, recursive, header, plugin):
    """Get a list of jails and print the property."""
    lgr = ioc_logger.Logger('ioc_cli_get')
    lgr = lgr.getLogger()

    get_jid = IOCList.list_get_jid
    jails, paths = IOCList("uuid").list_datasets()
    jail_list = []
    table = Texttable(max_width=0)

    if _all:
        # Confusing I know.
        jail = prop
        prop = "all"

    if _pool:
        pool = IOCJson().json_get_value("pool")

        lgr.info(pool)
        exit()

    if recursive is None:
        if jail == "":
            lgr.info("Usage: iocage get [OPTIONS] PROP JAIL\n")
            lgr.error("Missing argument \"jail\".")
            exit(1)

        _jail = {tag: uuid for (tag, uuid) in jails.items() if
                 uuid.startswith(jail) or tag == jail}

        if len(_jail) == 1:
            tag, uuid = next(iter(_jail.items()))
            path = paths[tag]
        elif len(_jail) > 1:
            lgr.error("Multiple jails found for"
                      " {}:".format(jail))
            for t, u in sorted(_jail.items()):
                lgr.error("  {} ({})".format(u, t))
            raise RuntimeError()
        else:
            lgr.critical("{} not found!".format(jail))
            exit(1)

        if prop == "state":
            status, _ = get_jid(path.split("/")[3])

            if status:
                state = "up"
            else:
                state = "down"

            lgr.info(state)
        elif plugin:
            _prop = prop.split(".")
            props = IOCJson(path).json_plugin_get_value(_prop)

            if isinstance(props, dict):
                lgr.info(json.dumps(props, indent=4))
            else:
                pass
        elif prop == "all":
            props = IOCJson(path).json_get_value(prop)

            for p, v in props.items():
                lgr.info("{}:{}".format(p, v))
        elif prop == "fstab":
            pool = IOCJson().json_get_value("pool")
            iocroot = IOCJson(pool).json_get_value("iocroot")
            index = 0

            with open("{}/jails/{}/fstab".format(iocroot, uuid), "r") as \
                    fstab:
                for line in fstab.readlines():
                    line = line.rsplit("#")[0].rstrip()
                    jail_list.append([index, line.replace("\t", " ")])
                    index += 1

            if header:
                jail_list.insert(0, ["INDEX", "FSTAB ENTRY"])
                # We get an infinite float otherwise.
                table.set_cols_dtype(["t", "t"])
                table.add_rows(jail_list)
                lgr.info(table.draw())
            else:
                for fstab in jail_list:
                    lgr.info("{}\t{}".format(fstab[0], fstab[1]))
        else:
            try:
                lgr.info(IOCJson(path).json_get_value(prop))
            except:
                lgr.warning("{} is not a valid property!".format(prop))
                exit(1)
    else:
        for j in jails:
            uuid = jails[j]
            path = paths[j]
            try:
                if prop == "state":
                    status, _ = get_jid(path.split("/")[3])

                    if status:
                        state = "up"
                    else:
                        state = "down"

                    jail_list.append([uuid, j, state])
                elif prop == "all":
                    props = IOCJson(path).json_get_value(prop)

                    for p, v in props.items():
                        jail_list.append([uuid, j, "{}:{}".format(p, v)])
                else:
                    jail_list.append(
                        [uuid, j, IOCJson(path).json_get_value(prop)])
            except:
                lgr.warning("{} is not a valid property!".format(prop))
                exit(1)

        # Prints the table
        if header:
            jail_list.insert(0, ["UUID", "TAG", "PROP - {}".format(prop)])
            # We get an infinite float otherwise.
            table.set_cols_dtype(["t", "t", "t"])
            table.add_rows(jail_list)
            lgr.info(table.draw())
        else:
            for jail in jail_list:
                lgr.info("\t".join(jail))
