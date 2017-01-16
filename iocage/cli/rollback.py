"""Rollback module for the cli"""
import logging
from subprocess import CalledProcessError, PIPE, Popen, check_call, check_output

import click

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
    lgr = logging.getLogger('ioc_cli_rollback')

    jails, paths = IOCList("uuid").get_datasets()
    pool = IOCJson().get_prop_value("pool")

    _jail = {tag: uuid for (tag, uuid) in jails.iteritems() if
             uuid.startswith(jail) or tag == jail}

    if len(_jail) == 1:
        tag, uuid = next(_jail.iteritems())
        path = paths[tag]
    elif len(_jail) > 1:
        lgr.error("Multiple jails found for"
                  " {}:".format(jail))
        for t, u in sorted(_jail.iteritems()):
            lgr.error("  {} ({})".format(u, t))
        raise RuntimeError()
    else:
        raise RuntimeError("{} not found!".format(jail))

    # Looks like foo/iocage/jails/df0ef69a-57b6-4480-b1f8-88f7b6febbdf@BAR
    target = "{}{}@{}".format(pool, path, name)
    try:
        check_output(["zfs", "get", "-H", "creation", target], stderr=PIPE)
    except CalledProcessError:
        raise RuntimeError("ERROR: Snapshot {} does not exist!".format(target))

    if not force:
        lgr.warning(
                "\nWARNING: This will destroy ALL data created since"
                " {} was taken.".format(
                        name) + "\nIncluding ALL snapshots taken after"
                                " {} for {} ({}).".format(name, uuid, tag))
        answer = raw_input("\nAre you sure? y[N]: ")

        if answer.lower() == "" or answer.lower() == "n":
            exit()
    try:
        datasets = Popen(["zfs", "list", "-H", "-r",
                          "-o", "name", "{}{}".format(pool, path)],
                         stdout=PIPE,
                         stderr=PIPE).communicate()[0].split()

        for dataset in datasets:
            check_call(["zfs", "rollback", "-r", "{}@{}".format(dataset, name)])

        lgr.info("Rolled back to: {}.".format(target))
    except CalledProcessError as err:
        lgr.error("ERROR: {}".format(err))
