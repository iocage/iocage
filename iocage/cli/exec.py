"""exec module for the cli."""
import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.ioc_exec as ioc_exec
import iocage.lib.ioc_list as ioc_list

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
            "level"  : "ERROR",
            "message": "Please specify a jail first!"
        })
        exit(1)

    if host_user and jail_user:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": "Please only specify either host_user or"
                       " jail_user, not both!"
        })
        exit(1)

    jails, paths = ioc_list.IOCList("uuid").list_datasets()
    _jail = {tag: uuid for (tag, uuid) in jails.items() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(iter(_jail.items()))
        path = paths[tag]
    elif len(_jail) > 1:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": f"Multiple jails found for {jail}:"
        })
        for t, u in sorted(_jail.items()):
            ioc_common.logit({
                "level"  : "ERROR",
                "message": f"  {u} ({t})"
            })
        exit(1)
    else:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": f"{jail} not found!"
        })
        exit(1)

    msg, err = ioc_exec.IOCExec(command, uuid, tag, path, host_user,
                                jail_user).exec_jail()

    if err:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": err.decode()
        })
    else:
        ioc_common.logit({
            "level"  : "INFO",
            "message": msg.decode("utf-8")
        })
