"""exec module for the cli."""
import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.iocage as ioc

__rootcmd__ = True


@click.command(context_settings=dict(
    ignore_unknown_options=True, ),
    name="exec", help="Run a command inside a specified jail.")
@click.option("--host_user", "-u", default="root",
              help="The host user to use.")
@click.option("--jail_user", "-U", help="The jail user to use.")
@click.argument("jail", required=True, nargs=1)
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
def cli(command, jail, host_user, jail_user):
    """Runs the command given inside the specified jail as the supplied
    user."""
    # We may be getting ';', '&&' and so forth. Adding the shell for safety.
    if len(command) == 1:
        command = ("/bin/sh", "-c") + command

    if jail.startswith("-"):
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": "Please specify a jail first!"
        })

    ioc.IOCage(jail).exec(command, host_user, jail_user)
