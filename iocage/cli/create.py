"""create module for the cli."""
import json
import logging
import os
from json import JSONDecodeError

import click

from iocage.lib.ioc_create import IOCCreate
from iocage.lib.ioc_fetch import IOCFetch
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList

__cmdname__ = "create_cmd"
__rootcmd__ = True


def validate_count(ctx, param, value):
    """Takes a string, removes the commas and returns an int."""
    try:
        count = value.replace(",", "")
        return int(count)
    except ValueError:
        return int(value)


@click.command(name="create", help="Create a jail.")
@click.option("--count", "-c", callback=validate_count, default="1")
@click.option("--release", "-r", required=False)
@click.option("--template", "-t", required=False)
@click.option("--pkglist", "-p", default=None)
@click.option("--uuid", "-u", default=None,
              help="Provide a specific UUID for this jail")
@click.option("--basejail", "-b", is_flag=True, default=False)
@click.option("--empty", "-e", is_flag=True, default=False)
@click.option("--short", "-s", is_flag=True, default=False,
              help="Use a short UUID of 8 characters instead of the default "
                   "36")
@click.argument("props", nargs=-1)
def create_cmd(release, template, count, props, pkglist, basejail, empty,
               short, uuid):
    lgr = logging.getLogger('ioc_cli_create')

    if short and uuid:
        raise RuntimeError(
            "Can't use --short (-s) and --uuid (-u) at the same time!")

    if not template and not release and not empty:
        raise RuntimeError(
            "Must supply either --template (-t) or --release (-r)!")

    if release and "=" in release:
        raise RuntimeError("Please supply a valid RELEASE!")

    if template:
        # We don't really care it's not a RELEASE at this point.
        release = template

    if pkglist:
        _pkgformat = """
{
    "pkgs": [
    "foo",
    "bar"
    ]
}"""

        if not os.path.isfile(pkglist):
            raise RuntimeError("{} does not exist!\nPlease supply a JSON file "
                               "with the format:{}".format(pkglist,
                                                           _pkgformat))
        else:
            try:
                # Just try to open the JSON with the right key.
                with open(pkglist, "r") as p:
                    json.load(p)["pkgs"]  # noqa
            except JSONDecodeError:
                raise RuntimeError("Please supply a valid JSON file with the"
                                   f" format:\n{_pkgformat}")

    pool = IOCJson().json_get_value("pool")
    iocroot = IOCJson(pool).json_get_value("iocroot")

    if not os.path.isdir(
            f"{iocroot}/releases/{release}") and not template and not empty:
        IOCFetch(release).fetch_release()

    if empty:
        release = "EMPTY"

    if count == 1:
        try:
            IOCCreate(release, props, 0, pkglist,
                      template=template, short=short, uuid=uuid,
                      basejail=basejail, empty=empty).create_jail()
        except RuntimeError as err:
            lgr.error(err)
            if template:
                lgr.info("Created Templates:")
                templates = IOCList("template", hdr=False).list_datasets()
                for temp in templates:
                    lgr.info("  {}".format(temp[3]))
    else:
        for j in range(1, count + 1):
            try:
                IOCCreate(release, props, j, pkglist,
                          template=template, short=short,
                          basejail=basejail, empty=empty).create_jail()
            except RuntimeError as err:
                lgr.error(err)
                if template:
                    lgr.info("Created Templates:")
                    templates = IOCList("template", hdr=False).list_datasets()
                    for temp in templates:
                        lgr.info("  {}".format(temp[3]))
                exit(1)
