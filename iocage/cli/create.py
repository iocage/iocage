"""create module for the CLI."""
import logging

import click

from iocage.lib.ioc_create import IOCCreate
from iocage.lib.ioc_list import IOCList

__cmdname__ = "create_cmd"
__rootcmd__ = True


@click.command(name="create", help="Create a jail.")
@click.option("--count", "-c", default=1)
@click.option("--release", "-r", required=True)
@click.option("--pkglist", "-p", default=None)
@click.argument("props", nargs=-1)
def create_cmd(release, count, props, pkglist):
    lgr = logging.getLogger('ioc_cli_create')

    if "=" in release:
        exit("Please supply a valid RELEASE!")

    if count == 1:
        try:
            IOCCreate(release, props, 0, pkglist).create_jail()
        except RuntimeError as err:
            lgr.error(err)
            lgr.info("Fetched RELEASEs:")
            releases = IOCList("base", hdr=False,
                               rtrn_object=True).get_datasets()
            for rel in releases:
                lgr.info("  {}".format(rel))
            exit()
    else:
        for j in xrange(1, count + 1):
            try:
                IOCCreate(release, props, j, pkglist).create_jail()
            except RuntimeError as err:
                lgr.error(err)
                lgr.info("Fetched RELEASEs:")
                releases = IOCList("base", hdr=False,
                                   rtrn_object=True).get_datasets()
                for rel in releases:
                    lgr.info("  {}".format(rel))
                exit()
