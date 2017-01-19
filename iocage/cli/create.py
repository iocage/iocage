"""create module for the CLI."""
import logging

import click

from iocage.lib.ioc_create import IOCCreate
from iocage.lib.ioc_list import IOCList

__cmdname__ = "create_cmd"
__rootcmd__ = True


@click.command(name="create", help="Create a jail.")
@click.option("--count", "-c", default=1)
@click.option("--release", "-r", required=False)
@click.option("--template", "-t", required=False)
@click.option("--pkglist", "-p", default=None)
@click.argument("props", nargs=-1)
def create_cmd(release, template, count, props, pkglist):
    lgr = logging.getLogger('ioc_cli_create')

    if not template and not release:
        exit("Must supply either --template (-t) or --release (-r)!")

    if release and "=" in release:
        exit("Please supply a valid RELEASE!")

    if template:
        # We don't really care it's not a RELEASE at this point.
        release = template

    if count == 1:
        try:
            IOCCreate(release, props, 0, pkglist,
                      template=template).create_jail()
        except RuntimeError as err:
            lgr.error(err)
            if template:
                lgr.info("Created Templates:")
                templates = IOCList("template", hdr=False,
                                    rtrn_object=True).get_datasets()
                for temp in templates:
                    lgr.info("  {}".format(temp))
            else:
                lgr.info("Fetched RELEASEs:")
                releases = IOCList("base", hdr=False,
                                   rtrn_object=True).get_datasets()
                for rel in releases:
                    lgr.info("  {}".format(rel))
    else:
        for j in xrange(1, count + 1):
            try:
                IOCCreate(release, props, j, pkglist,
                          template=template).create_jail()
            except RuntimeError as err:
                lgr.error(err)
                if template:
                    lgr.info("Created Templates:")
                    templates = IOCList("template", hdr=False,
                                        rtrn_object=True).get_datasets()
                    for temp in templates:
                        lgr.info("  {}".format(temp))
                else:
                    lgr.info("Fetched RELEASEs:")
                    releases = IOCList("base", hdr=False,
                                       rtrn_object=True).get_datasets()
                    for rel in releases:
                        lgr.info("  {}".format(rel))
                exit()
