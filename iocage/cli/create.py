"""create module for the cli."""
import json
import os

import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.ioc_create as ioc_create
import iocage.lib.ioc_fetch as ioc_fetch
import iocage.lib.ioc_json as ioc_json
import iocage.lib.ioc_list as ioc_list

__rootcmd__ = True


def validate_count(ctx, param, value):
    """Takes a string, removes the commas and returns an int."""
    if isinstance(value, str):
        try:
            value = value.replace(",", "")

            return int(value)
        except ValueError:
            ioc_common.logit({
                "level"  : "ERROR",
                "message": f"({value} is not a valid  integer."
            })
            exit(1)
    else:
        return int(value)


@click.command(name="create", help="Create a jail.")
@click.option("--count", "-c", callback=validate_count, default="1")
@click.option("--release", "-r", required=False)
@click.option("--template", "-t", required=False)
@click.option("--pkglist", "-p", default=None)
@click.option("--uuid", "-u", default=None,
              help="Provide a specific UUID for this jail")
@click.option("--basejail", "-b", is_flag=True, default=False)
@click.option("--empty", "-e", is_flag=True, default=False)
@click.option("--short", "-s", is_flag=True, default=False,
              help="Use a short UUID of 8 characters instead of the default "
                   "36")
@click.argument("props", nargs=-1)
def cli(release, template, count, props, pkglist, basejail, empty, short,
        uuid):
    if short and uuid:
        uuid = uuid[:8]

        if len(uuid) != 8:
            ioc_common.logit({
                "level"  : "ERROR",
                "message": "Need a minimum of 8 characters to use --short"
                           " (-s) and --uuid (-u) together!"
            })
            exit(1)

    if not template and not release and not empty:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": "Must supply either --template (-t) or --release (-r)!"
        })
        exit(1)

    if release and "=" in release:
        ioc_common.logit({
            "level"  : "ERROR",
            "message": "Please supply a valid RELEASE!"
        })
        exit(1)

    # We don't really care it's not a RELEASE at this point.
    release = template if template else release

    if pkglist:
        _pkgformat = """
{
    "pkgs": [
    "foo",
    "bar"
    ]
}"""

        if not os.path.isfile(pkglist):
            ioc_common.logit({
                "level"  : "ERROR",
                "message": f"{pkglist} does not exist!\n"
                           "Please supply a JSON file with the format:"
                           f" {_pkgformat}"
            })
            exit(1)
        else:
            try:
                # Just try to open the JSON with the right key.
                with open(pkglist, "r") as p:
                    json.load(p)["pkgs"]  # noqa
            except json.JSONDecodeError:
                ioc_common.logit({
                    "level"  : "ERROR",
                    "message": "Please supply a valid"
                               f" JSON file with the format:{_pkgformat}"
                })
                exit(1)

    pool = ioc_json.IOCJson().json_get_value("pool")
    iocroot = ioc_json.IOCJson(pool).json_get_value("iocroot")

    if not os.path.isdir(
            f"{iocroot}/releases/{release}") and not template and not empty:
        freebsd_version = ioc_common.checkoutput(["freebsd-version"])

        if "HBSD" in freebsd_version:
            hardened = True
        else:
            hardened = False

        ioc_fetch.IOCFetch(release, hardened=hardened).fetch_release()

    if empty:
        release = "EMPTY"

    if count == 1:
        try:
            ioc_create.IOCCreate(release, props, 0, pkglist,
                                 template=template, short=short, uuid=uuid,
                                 basejail=basejail, empty=empty).create_jail()
        except RuntimeError as err:
            ioc_common.logit({
                "level"  : "ERROR",
                "message": err
            })

            if template:
                ioc_common.logit({
                    "level"  : "INFO",
                    "message": "Created Templates:"
                })
                templates = ioc_list.IOCList("template",
                                             hdr=False).list_datasets()
                for temp in templates:
                    ioc_common.logit({
                        "level"  : "INFO",
                        "message": f"  {temp[3]}"
                    })
    else:
        for j in range(1, count + 1):
            try:
                ioc_create.IOCCreate(release, props, j, pkglist,
                                     template=template, short=short,
                                     basejail=basejail,
                                     empty=empty).create_jail()
            except RuntimeError as err:
                ioc_common.logit({
                    "level"  : "ERROR",
                    "message": err
                })
                if template:
                    ioc_common.logit({
                        "level"  : "INFO",
                        "message": "Created Templates:"
                    })
                    templates = ioc_list.IOCList("template",
                                                 hdr=False).list_datasets()
                    for temp in templates:
                        ioc_common.logit({
                            "level"  : "INFO",
                            "message": f"  {temp[3]}"
                        })
                exit(1)
