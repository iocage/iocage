"""chroot module for the cli."""
import click
import iocage.lib.iocage as ioc


@click.command(context_settings=dict(
    ignore_unknown_options=True, ),
    name="chroot", help="Chroot to a jail.")
@click.argument("jail")
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
def cli(jail, command):
    """Will chroot into a jail regardless if it's running."""
    if jail.startswith("-"):
        raise RuntimeError("Please specify a jail first!")

    ioc.IOCage(jail).chroot(command)
