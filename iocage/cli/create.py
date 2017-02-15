"""create module for the cli."""
import logging
import os

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
@click.option("--short", "-s", is_flag=True, default=False,
              help="Use a short UUID of 8 characters instead of the default "
                   "36")
@click.argument("props", nargs=-1)
def create_cmd(release, template, count, props, pkglist, short):
    lgr = logging.getLogger('ioc_cli_create')

    if not template and not release:
        exit("Must supply either --template (-t) or --release (-r)!")

    if release and "=" in release:
        exit("Please supply a valid RELEASE!")

    if template:
        # We don't really care it's not a RELEASE at this point.
        release = template

    if pkglist:
        if not os.path.isfile(pkglist):
            _pkgformat = """
{
    "pkgs": [
    "foo",
    "bar",
    ]
}"""
            raise RuntimeError("{} does not exist!\nPlease supply a JSON file "
                               "with the format:{}".format(pkglist,
                                                           _pkgformat))

    if count == 1:
        try:
            IOCCreate(release, props, 0, pkglist,
                      template=template, short=short).create_jail()
        except RuntimeError as err:
            lgr.error(err)
            if template:
                lgr.info("Created Templates:")
                templates = IOCList("template", hdr=False,
                                    rtrn_object=True).list_datasets()
                for temp in templates:
                    lgr.info("  {}".format(temp))
            else:
                pool = IOCJson().json_get_value("pool")
                iocroot = IOCJson(pool).json_get_value("iocroot")

                if not os.path.isdir("{}/releases/{}".format(iocroot,
                                                             release)):
                    IOCFetch(release).fetch_release()

                IOCCreate(release, props, 0, pkglist,
                          template=template, short=short).create_jail()
    else:
        for j in xrange(1, count + 1):
            try:
                IOCCreate(release, props, j, pkglist,
                          template=template, short=short).create_jail()
            except RuntimeError as err:
                lgr.error(err)
                if template:
                    lgr.info("Created Templates:")
                    templates = IOCList("template", hdr=False,
                                        rtrn_object=True).list_datasets()
                    for temp in templates:
                        lgr.info("  {}".format(temp))
                else:
                    lgr.info("Fetched RELEASEs:")
                    releases = IOCList("base", hdr=False,
                                       rtrn_object=True).list_datasets()
                    for rel in releases:
                        lgr.info("  {}".format(rel))
                exit()
