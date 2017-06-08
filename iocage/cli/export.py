"""export module for the cli."""
import click

import iocage.lib.iocage as ioc

__rootcmd__ = True


@click.command(name="export", help="Exports a specified jail.")
@click.argument("jail", required=True)
def cli(jail):
    """Make a recursive snapshot of the jail and export to a file."""
    ioc.IOCage(jail).export()
