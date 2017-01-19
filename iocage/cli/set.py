"""This is responsible for setting a jail property."""

import logging

import click

from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList

__cmdname__ = "set_cmd"
__rootcmd__ = True


@click.command(name="set", help="Sets the specified property.")
@click.argument("prop")
@click.argument("jail")
def set_cmd(prop, jail):
    """Get a list of jails and print the property."""
    lgr = logging.getLogger('ioc_cli_set')

    jails, paths = IOCList("uuid").get_datasets(set=True)
    _jail = {tag: uuid for (tag, uuid) in jails.iteritems() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(_jail.iteritems())
        path = paths[tag]
        iocjson = IOCJson(path)
    elif len(_jail) > 1:
        lgr.error("Multiple jails found for"
                  " {}:".format(jail))
        for t, u in sorted(_jail.iteritems()):
            lgr.error("  {} ({})".format(u, t))
        raise RuntimeError()
    else:
        raise RuntimeError("{} not found!".format(jail))

    if "template" in prop:
        if "template" in path and prop != "template=no":
            raise RuntimeError("{} ({}) is already a template!".format(
                uuid, tag
            ))
        elif "template" not in path and prop != "template=yes":
            raise RuntimeError("{} ({}) is already a jail!".format(uuid, tag))
    try:
        # We use this to test if it's a valid property at all.
        _prop = prop.partition("=")[0]
        iocjson.get_prop_value(_prop)

        # The actual setting of the property.
        iocjson.set_prop_value(prop)
    except KeyError:
        _prop = prop.partition("=")[0]
        raise RuntimeError("{} is not a valid property!".format(_prop))
