"""set module for the cli."""
import logging
from builtins import next

import click

from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList

__cmdname__ = "set_cmd"
__rootcmd__ = True


@click.command(context_settings=dict(
    max_content_width=400, ), name="set", help="Sets the specified property.")
@click.argument("prop")
@click.argument("jail")
@click.option("--plugin", "-P",
              help="Set the specified key for a plugin jail, if accessing a"
                   " nested key use . as a separator."
                   "\n\b Example: iocage set -P foo.bar.baz=VALUE PLUGIN",
              is_flag=True)
def set_cmd(prop, jail, plugin):
    """Get a list of jails and print the property."""
    lgr = logging.getLogger('ioc_cli_set')

    jails, paths = IOCList("uuid").list_datasets(set=True)
    _jail = {tag: uuid for (tag, uuid) in jails.items() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(iter(_jail.items()))
        path = paths[tag]
        iocjson = IOCJson(path)
    elif len(_jail) > 1:
        lgr.error("Multiple jails found for"
                  " {}:".format(jail))
        for t, u in sorted(_jail.items()):
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
    if plugin:
        _prop = prop.split(".")
        IOCJson(path).json_plugin_set_value(_prop)
    else:
        try:
            # We use this to test if it's a valid property at all.
            _prop = prop.partition("=")[0]
            iocjson.json_get_value(_prop)

            # The actual setting of the property.
            iocjson.json_set_value(prop)
        except KeyError:
            _prop = prop.partition("=")[0]
            raise RuntimeError("{} is not a valid property!".format(_prop))
