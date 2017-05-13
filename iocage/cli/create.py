"""create module for the cli."""
import json
import os

import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.iocage as ioc

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
    if release and "=" in release:
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": "Please supply a valid RELEASE!"
        })

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
                "level"  : "EXCEPTION",
                "message": f"{pkglist} does not exist!\n"
                           "Please supply a JSON file with the format:"
                           f" {_pkgformat}"
            })
        else:
            try:
                # Just try to open the JSON with the right key.
                with open(pkglist, "r") as p:
                    json.load(p)["pkgs"]  # noqa
            except json.JSONDecodeError:
                ioc_common.logit({
                    "level"  : "EXCEPTION",
                    "message": "Please supply a valid"
                               f" JSON file with the format:{_pkgformat}"
                })

    if empty:
        release = "EMPTY"

    if count == 1:
        err, msg = ioc.IOCage().create(release, props, pkglist=pkglist,
                                       template=template, short=short,
                                       uuid=uuid, basejail=basejail,
                                       empty=empty)
        if err:
            ioc_common.logit({
                "level"  : "ERROR",
                "message": msg
            })

            if template:
                ioc_common.logit({
                    "level"  : "INFO",
                    "message": "Created Templates:"
                })
                templates = ioc.IOCage().list("template")
                for temp in templates:
                    ioc_common.logit({
                        "level"  : "INFO",
                        "message": f"  {temp[3]}"
                    })
    else:
        for j in range(1, count + 1):
            err, msg = ioc.IOCage().create(release, props, j, pkglist=pkglist,
                                           template=template, short=short,
                                           uuid=uuid, basejail=basejail,
                                           empty=empty)
            if err:
                ioc_common.logit({
                    "level"  : "ERROR",
                    "message": msg
                })

                if template:
                    ioc_common.logit({
                        "level"  : "INFO",
                        "message": "Created Templates:"
                    })
                    templates = ioc.IOCage().list("template")
                    for temp in templates:
                        ioc_common.logit({
                            "level"  : "INFO",
                            "message": f"  {temp[3]}"
                        })
                exit(1)
