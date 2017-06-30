# Copyright (c) 2014-2017, iocage
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""create module for the cli."""
import json
import os
import re
import uuid

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
                "level"  : "EXCEPTION",
                "message": f"{value} is not a valid integer."
            })
    else:
        return int(value)


@click.command(name="create", help="Create a jail.")
@click.option("--count", "-c", callback=validate_count, default="1",
              help="Designate a number of jails to create. Jails are"
                   " numbered sequentially.")
@click.option("--release", "-r", required=False,
              help="Specify the RELEASE to use for the new jail.")
@click.option("--template", "-t", required=False,
              help="Flag this jail as a template, which allows for rapid"
                   " redeployment of a customized jail.")
@click.option("--pkglist", "-p", default=None,
              help="Specify a JSON file which manages the installation of"
                   " each package in the newly created jail.")
@click.option("--name", "-n", default=None,
              help="Provide a specific name and tag instead of an UUID for"
                   " this jail.")
@click.option("--uuid", "-u", "_uuid", default=None,
              help="Provide a specific UUID for this jail.")
@click.option("--basejail", "-b", is_flag=True, default=False,
              help="Set the new jail type to a basejail. Basejails"
                   " mount the specified RELEASE directories as nullfs"
                   " mounts over the jail's directories.")
@click.option("--empty", "-e", is_flag=True, default=False,
              help="Create an empty jail used for unsupported or custom"
                   " jails.")
@click.option("--short", "-s", is_flag=True, default=False,
              help="Use a short UUID of 8 characters instead of the default"
                   " 36.")
@click.option("--force", "-f", is_flag=True, default=False,
              help="Skip the interactive question.")
@click.argument("props", nargs=-1)
def cli(release, template, count, props, pkglist, basejail, empty, short,
        name, _uuid, force):
    if name:
        valid = True if re.match("^[a-zA-Z0-9_]*$", name) else False
        if not valid:
            ioc_common.logit({
                "level"  : "EXCEPTION",
                "message": f"Invalid character in {name}, please remove it."
            })

        _props = []
        if f"tag={name}" not in props:
            _props.append(f"tag={name}")

        for prop in props:
            replace = f"tag={name}"
            prop = re.sub(r"tag=.*", replace, prop)
            _props.append(prop)

        props = tuple(_props)

        # At this point we don't care
        _uuid = name

    if release and "=" in release:
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": "Please supply a valid RELEASE!"
        })

    if template:
        try:
            uuid.UUID(template, version=4)
            ioc_common.logit({
                "level"  : "EXCEPTION",
                "message": "Template creation only supports TAGs!"
            })
        except ValueError:
            if not force:
                ioc_common.logit({
                    "level"  : "WARNING",
                    "message": "This may be a short UUID, "
                               "template creation only supports TAGs"
                })
                if not click.confirm("\nProceed?"):
                    exit()

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

    iocage = ioc.IOCage(skip_jails=True)

    if count == 1:
        err, msg = iocage.create(release, props, pkglist=pkglist,
                                 template=template, short=short,
                                 uuid=_uuid, basejail=basejail,
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
    else:
        iocage.create(release, props, count, pkglist=pkglist,
                      template=template, short=short, uuid=_uuid,
                      basejail=basejail, empty=empty)
