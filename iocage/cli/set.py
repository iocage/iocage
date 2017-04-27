"""set module for the cli."""
import click

from iocage.lib.ioc_common import logit
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
    jails, paths = IOCList("uuid").list_datasets(set=True)
    _jail = {tag: uuid for (tag, uuid) in jails.items() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(iter(_jail.items()))
        path = paths[tag]
        iocjson = IOCJson(path, cli=True)
    elif len(_jail) > 1:
        logit({
            "level"  : "ERROR",
            "message": f"Multiple jails found for {jail}:"
        })
        for t, u in sorted(_jail.items()):
            logit({
                "level"  : "ERROR",
                "message": f"  {u} ({t})"
            })
        exit(1)
    else:
        logit({
            "level"  : "ERROR",
            "message": f"{jail} not found!"
        })
        exit(1)

    if "template" in prop.split("=")[0]:
        if "template" in path and prop != "template=no":
            logit({
                "level"  : "ERROR",
                "message": f"{uuid} ({tag}) is already a template!"
            })
            exit(1)
        elif "template" not in path and prop != "template=yes":
            logit({
                "level"  : "ERROR",
                "message": f"{uuid} ({tag}) is already a jail!"
            })
            exit(1)
    if plugin:
        _prop = prop.split(".")
        IOCJson(path, cli=True).json_plugin_set_value(_prop)
    else:
        try:
            # We use this to test if it's a valid property at all.
            _prop = prop.partition("=")[0]
            iocjson.json_get_value(_prop)

            # The actual setting of the property.
            iocjson.json_set_value(prop)
        except KeyError:
            _prop = prop.partition("=")[0]
            logit({
                "level"  : "ERROR",
                "message": f"{_prop} is not a valid property!"
            })
            exit(1)
