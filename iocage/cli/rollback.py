"""rollback module for the cli."""
from subprocess import CalledProcessError, PIPE, Popen, check_call

import click

from iocage.lib.ioc_common import checkoutput, logit
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList

__rootcmd__ = True


@click.command(name="rollback", help="Rollbacks the specified jail.")
@click.argument("jail")
@click.option("--name", "-n", help="The snapshot name. This will be what comes"
                                   " after @", required=True)
@click.option("--force", "-f", help="Skip then interactive question.",
              default=False, is_flag=True)
def cli(jail, name, force):
    """Get a list of jails and print the property."""
    jails, paths = IOCList("uuid").list_datasets()
    pool = IOCJson().json_get_value("pool")

    _jail = {tag: uuid for (tag, uuid) in jails.items() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(iter(_jail.items()))
        path = paths[tag]
    elif len(_jail) > 1:
        logit({
            "level"  : "ERROR",
            "message": "Multiple jails found for"
                       f" {jail}:"
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

    # Looks like foo/iocage/jails/df0ef69a-57b6-4480-b1f8-88f7b6febbdf@BAR
    conf = IOCJson(path).json_load()

    if conf["template"] == "yes":
        target = f"{pool}/iocage/templates/{tag}"
    else:
        target = f"{pool}/iocage/jails/{uuid}"

    try:
        checkoutput(["zfs", "get", "-H", "creation", target], stderr=PIPE)
    except CalledProcessError:
        logit({
            "level"  : "ERROR",
            "message": f"Snapshot {target} does not exist!"
        })
        exit(1)

    if not force:
        logit({
            "level"  : "WARNING",
            "message": "\nThis will destroy ALL data created since"
                       f" {name} was taken.\nIncluding ALL snapshots taken"
                       f" after {name} for {uuid} ({tag})"
        })
        if not click.confirm("\nAre you sure?"):
            exit()
    try:
        datasets = Popen(["zfs", "list", "-H", "-r",
                          "-o", "name", target],
                         stdout=PIPE,
                         stderr=PIPE).communicate()[0].decode("utf-8").split()

        for dataset in datasets:
            check_call(
                ["zfs", "rollback", "-r", f"{dataset}@{name}"])

        logit({
            "level"  : "INFO",
            "message": f"Rolled back to: {target}"
        })
    except CalledProcessError as err:
        logit({
            "level"  : "ERROR",
            "message": f"{err}"
        })
        exit(1)
