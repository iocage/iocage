"""export module for the cli."""
import os
import zipfile
from datetime import datetime
from subprocess import CalledProcessError, PIPE, Popen, STDOUT, check_call

import click

import iocage.lib.ioc_logger as ioc_logger
from iocage.lib.ioc_common import checkoutput
from iocage.lib.ioc_json import IOCJson
from iocage.lib.ioc_list import IOCList

__cmdname__ = "export_cmd"
__rootcmd__ = True


@click.command(name="export", help="Exports a specified jail.")
@click.argument("jail", required=True)
def export_cmd(jail):
    """Make a recursive snapshot of the jail and export to a file."""
    lgr = ioc_logger.Logger('ioc_cli_export')
    lgr = lgr.getLogger()

    pool = IOCJson().json_get_value("pool")
    iocroot = IOCJson(pool).json_get_value("iocroot")
    date = datetime.utcnow().strftime("%F")
    jails, paths = IOCList("uuid").list_datasets()
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

    status, _ = IOCList().list_get_jid(uuid)
    if status:
        lgr.critical("{} ({}) is runnning, stop the jail before "
                     "exporting!".format(uuid, tag))
        exit(1)

    images = "{}/images".format(iocroot)
    name = "{}_{}".format(uuid, date)
    image = "{}/{}_{}".format(images, name, tag)
    image_path = "{}{}".format(pool, path)
    jail_list = []

    # Looks like foo/iocage/jails/df0ef69a-57b6-4480-b1f8-88f7b6febbdf@BAR
    target = "{}@ioc-export-{}".format(image_path, date)

    try:
        checkoutput(["zfs", "snapshot", "-r", target], stderr=STDOUT)
    except CalledProcessError as err:
        lgr.critical("{}".format(err.output.decode("utf-8").rstrip()))
        exit(1)

    datasets = Popen(["zfs", "list", "-H", "-r",
                      "-o", "name", "{}{}".format(pool, path)],
                     stdout=PIPE, stderr=PIPE).communicate()[0].decode(
        "utf-8").split()

    for dataset in datasets:
        if len(dataset) == 54:
            _image = image
            jail_list.append(_image)
        elif len(dataset) > 54:
            image_name = dataset.partition("{}{}".format(pool, path))[2]
            name = image_name.replace("/", "_")
            _image = image + name
            jail_list.append(_image)
            target = "{}@ioc-export-{}".format(dataset, date)

        # Sending each individually as sending them recursively to a file does
        # not work how one expects.
        try:
            with open(_image, "wb") as export:
                lgr.info("Exporting dataset: {}".format(dataset))
                check_call(["zfs", "send", target], stdout=export)
        except CalledProcessError as err:
            lgr.critical("{}".format(err))
            exit(1)

    lgr.info("\nPreparing zip file: {}.zip.".format(image))
    with zipfile.ZipFile("{}.zip".format(image), "w",
                         compression=zipfile.ZIP_DEFLATED,
                         allowZip64=True) as final:
        os.chdir(images)

        for jail in jail_list:
            final.write(jail)

    # Cleanup our mess.
    try:
        checkoutput(["zfs", "destroy", "-r", target], stderr=STDOUT)

        for jail in jail_list:
            os.remove(jail)

    except CalledProcessError as err:
        lgr.critical("{}".format(err.output.decode("utf-8").rstrip()))
        exit(1)

    lgr.info("\nExported: {}.zip".format(image))
