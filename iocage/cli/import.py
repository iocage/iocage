import logging
import zipfile
from subprocess import CalledProcessError, PIPE, Popen, STDOUT, check_output

import click
import fnmatch
import os

from iocage.lib.ioc_json import IOCJson

__cmdname__ = "import_cmd"


@click.command(name="import", help="Import a specified jail.")
@click.argument("jail", required=True)
def import_cmd(jail):
    """Import from an iocage export."""
    lgr = logging.getLogger('ioc_cli_import')

    pool = IOCJson().get_prop_value("pool")
    iocroot = IOCJson(pool).get_prop_value("iocroot")
    image_dir = "{}/images".format(iocroot)
    exports = os.listdir(image_dir)
    uuid_matches = fnmatch.filter(exports, "{}*.zip".format(jail))
    tag_matches = fnmatch.filter(exports, "*{}.zip".format(jail))
    cmd = ["zfs", "recv", "-F", "-d", pool]

    # We want to allow the user some flexibility.
    if uuid_matches:
        matches = uuid_matches
    else:
        matches = tag_matches

    if len(matches) == 1:
        image_target = "{}/{}".format(image_dir, matches[0])
        uuid = matches[0].rsplit("_")[0]
        date = matches[0].rsplit("_")[1]
        tag = matches[0].rsplit("_")[2].rsplit(".")[0]
    elif len(matches) > 1:
        lgr.error("Multiple exports found for"
                  " {}:".format(jail))
        for j in sorted(matches):
            lgr.error("  {}".format(j))
        raise RuntimeError()
    else:
        raise RuntimeError("{} not found!".format(jail))

    with zipfile.ZipFile(image_target, "r") as _import:
        for z in _import.namelist():
            z_split = z.split("_")

            # We don't want the date and tag
            del z_split[1]
            del z_split[1]

            z_split_str = "/".join(z_split)
            _z = z_split_str.replace("iocage/images/", "")

            lgr.info("Importing dataset: {}".format(_z))
            dataset = _import.read(z)
            recv = Popen(cmd, stdin=PIPE)
            recv.stdin.write(dataset)
            recv.communicate()
            recv.stdin.close()

    # Cleanup our mess.
    try:
        target = "{}{}/jails/{}@ioc-export-{}".format(pool, iocroot, uuid, date)
        check_output(["zfs", "destroy", "-r", target], stderr=STDOUT)
    except CalledProcessError as err:
        raise RuntimeError("ERROR: {}".format(err.output.strip()))

    tag = IOCJson("{}/jails/{}".format(iocroot, uuid),
                  silent=True).set_prop_value("tag={}".format(tag))
    lgr.info("\nImported: {} ({})".format(uuid, tag))
