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
            }, exit_on_error=True)
    else:
        return int(value)


@click.command(name="create", help="Create a jail.")
@click.option("--count", "-c", callback=validate_count, default="1",
              help="Designate a number of jails to create. Jails are"
                   " numbered sequentially.")
@click.option("--release", "-r", required=False,
              help="Specify the RELEASE to use for the new jail.")
@click.option("--template", "-t", required=False,
              help="Specify the template to use for the new jail instead of"
                   " a RELEASE.")
@click.option("--pkglist", "-p", default=None,
              help="Specify a JSON file which manages the installation of"
                   " each package in the newly created jail.")
@click.option("--name", "-n", default=None,
              help="Provide a specific name instead of an UUID for this jail.")
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
        # noinspection Annotator
        valid = True if re.match("^[a-zA-Z0-9\._-]+$", name) else False
        if not valid:
            ioc_common.logit({
                "level"  : "EXCEPTION",
                "message": f"Invalid character in {name}, please remove it."
            }, exit_on_error=True)

        # At this point we don't care
        _uuid = name

    if release and "=" in release:
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": "Please supply a valid RELEASE!"
        }, exit_on_error=True)

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
            }, exit_on_error=True)
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
                }, exit_on_error=True)

    if empty:
        release = "EMPTY"

    iocage = ioc.IOCage(exit_on_error=True, skip_jails=True)

    try:
        iocage.create(release, props, count, pkglist=pkglist,
                      template=template, short=short, _uuid=_uuid,
                      basejail=basejail, empty=empty)
    except RuntimeError as err:
        if template:
            # We want to list the available templates first
            ioc_common.logit({
                "level"  : "ERROR",
                "message": f"Template: {release} not found!"
            })
            templates = ioc.IOCage(exit_on_error=True).list("template")
            for temp in templates:
                ioc_common.logit({
                    "level"  : "EXCEPTION",
                    "message": f"Created Templates:\n  {temp[1]}"
                }, exit_on_error=True)
            exit(1)
        else:
            # Standard errors
            ioc_common.logit({
                "level"  : "EXCEPTION",
                "message": err
            }, exit_on_error=True)
