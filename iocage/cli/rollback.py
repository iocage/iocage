"""rollback module for the cli."""
from subprocess import CalledProcessError, PIPE, Popen, check_call

import click

import iocage.lib.ioc_logger as ioc_logger
from iocage.lib.ioc_common import checkoutput
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList

__cmdname__ = "rollback_cmd"
__rootcmd__ = True


@click.command(name="rollback", help="Rollbacks the specified jail.")
@click.argument("jail")
@click.option("--name", "-n", help="The snapshot name. This will be what comes"
                                   " after @", required=True)
@click.option("--force", "-f", help="Skip then interactive question.",
              default=False, is_flag=True)
def rollback_cmd(jail, name, force):
    """Get a list of jails and print the property."""
    lgr = ioc_logger.Logger('ioc_cli_rollback')
    lgr = lgr.getLogger()

    jails, paths = IOCList("uuid").list_datasets()
    pool = IOCJson().json_get_value("pool")

    _jail = {tag: uuid for (tag, uuid) in jails.items() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(iter(_jail.items()))
        path = paths[tag]
    elif len(_jail) > 1:
        lgr.error("Multiple jails found for"
                  " {}:".format(jail))
        for t, u in sorted(_jail.items()):
            lgr.error("  {} ({})".format(u, t))
        raise RuntimeError()
    else:
        lgr.critical("{} not found!".format(jail))
        exit(1)

    # Looks like foo/iocage/jails/df0ef69a-57b6-4480-b1f8-88f7b6febbdf@BAR
    target = "{}{}@{}".format(pool, path, name)
    try:
        checkoutput(["zfs", "get", "-H", "creation", target], stderr=PIPE)
    except CalledProcessError:
        lgr.critical("ERROR: Snapshot {} does not exist!".format(target))
        exit(1)

    if not force:
        lgr.warning(
            "\nThis will destroy ALL data created since"
            " {} was taken.".format(
                name) + "\nIncluding ALL snapshots taken after"
                        " {} for {} ({}).".format(name, uuid, tag))
        if not click.confirm("\nAre you sure?"):
            exit()
    try:
        datasets = Popen(["zfs", "list", "-H", "-r",
                          "-o", "name", "{}{}".format(pool, path)],
                         stdout=PIPE,
                         stderr=PIPE).communicate()[0].decode("utf-8").split()

        for dataset in datasets:
            check_call(
                ["zfs", "rollback", "-r", "{}@{}".format(dataset, name)])

        lgr.info("Rolled back to: {}.".format(target))
    except CalledProcessError as err:
        lgr.error("{}".format(err))
