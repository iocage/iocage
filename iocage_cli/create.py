# Copyright (c) 2014-2019, iocage
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
import iocage_lib.ioc_common as ioc_common
import iocage_lib.iocage as ioc
import iocage_lib.ioc_exceptions as ioc_exceptions

__rootcmd__ = True


def validate_count(ctx, param, value):
    """Takes a string, removes the commas and returns an int."""

    if isinstance(value, str):
        try:
            value = value.replace(",", "")

            return int(value)
        except ValueError:
            ioc_common.logit({
                "level": "EXCEPTION",
                "message": f"{value} is not a valid integer."
            })
    else:
        return int(value)


@click.command(
    name="create", help="Create a jail."
)
@click.option(
    "--count", "-c", callback=validate_count, default="1",
    help="Designate a number of jails to create. Jails are "
         "numbered sequentially."
)
@click.option(
    "--thickconfig", "-C", default=False, is_flag=True,
    help="Do not use inheritable configuration with jails"
)
@click.option(
    "--release", "-r", required=False,
    help="Specify the RELEASE to use for the new jail."
)
@click.option(
    "--template", "-t", required=False,
    help="Specify the template to use for the new jail instead of a RELEASE."
)
@click.option(
    "--pkglist", "-p", default=None,
    help="Specify a JSON file which manages the installation of "
         "each package in the newly created jail."
)
@click.option(
    "--name", "-n", default=None,
    help="Provide a specific name instead of an UUID for this jail."
)
@click.option(
    "--uuid", "-u", "_uuid", default=None,
    help="Provide a specific UUID for this jail."
)
@click.option(
    '--proxy', '-S', default=None,
    help='Provide proxy to use for creating jail'
)
@click.option(
    "--basejail", "-b", is_flag=True, default=False,
    help="Set the new jail type to a basejail. Basejails are "
         "thick jails (unless specified) that mount the specified "
         "RELEASE directories as nullfs mounts over the jail's "
         "directories."
)
@click.option(
    "--clone_basejail", "-B", is_flag=True, default=False,
    help="Set the new jail type to a clonetype basejail. Basejails "
         "mount the specified RELEASE directories as nullfs mounts "
         "over the jail's directories.")
@click.option(
    "--thickjail", "-T", is_flag=True, default=False,
    help="Set the new jail type to a thickjail. Thickjails "
         "are copied (not cloned) from specified RELEASE."
)
@click.option(
    "--empty", "-e", is_flag=True, default=False,
    help="Create an empty jail used for unsupported or custom jails."
)
@click.option(
    "--short", "-s", is_flag=True, default=False,
    help="Use a short UUID of 8 characters instead of the default 36."
)
@click.argument("props", nargs=-1)
def cli(
    release, template, count, props, pkglist, basejail, clone_basejail,
    thickjail, empty, short, name, _uuid, thickconfig, proxy
):

    if _uuid:
        try:
            uuid.UUID(_uuid, version=4)
        except ValueError:
            ioc_common.logit({
                "level": "EXCEPTION",
                "message": "Please provide a valid UUID"
            })
        else:
            if count > 1:
                ioc_common.logit({
                    "level": "EXCEPTION",
                    "message": "Flag --count cannot be used with --uuid"
                })

    if proxy:
        os.environ.update({
            'http_proxy': proxy,
            'https_proxy': proxy
        })

    if name:
        # noinspection Annotator
        valid = True if re.match(r"^[a-zA-Z0-9\._-]+$", name) else False

        if not valid:
            ioc_common.logit({
                "level": "EXCEPTION",
                "message": f"Invalid character in {name}, please remove it."
            })

        # At this point we don't care
        _uuid = name

    if release and "=" in release:
        ioc_common.logit({
            "level": "EXCEPTION",
            "message": "Please supply a valid RELEASE!"
        })
    elif release and release.lower() == "latest":
        release = ioc_common.parse_latest_release()

    if release:
        try:
            ioc_common.check_release_newer(release, major_only=True)
        except ValueError:
            # We're assuming they understand the implications of a custom
            # scheme
            iocroot = ioc.PoolAndDataset().get_iocroot()
            path = f'{iocroot}/releases/{release}/root'
            _release = ioc_common.get_jail_freebsd_version(path, release)

            try:
                ioc_common.check_release_newer(_release, major_only=True)
            except ValueError:
                # We tried
                pass

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
                "level": "EXCEPTION",
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
                    "level": "EXCEPTION",
                    "message": "Please supply a valid"
                               f" JSON file with the format:{_pkgformat}"
                })

    if empty:
        release = "EMPTY"

    if clone_basejail:
        # We want to still create a basejail
        basejail = True

    iocage = ioc.IOCage(skip_jails=True)

    try:
        iocage.create(release, props, count, pkglist=pkglist,
                      template=template, short=short, _uuid=_uuid,
                      basejail=basejail, thickjail=thickjail, empty=empty,
                      thickconfig=thickconfig, clone_basejail=clone_basejail)
    except (RuntimeError, ioc_exceptions.JailMissingConfiguration) as err:
        if template and "Dataset" in str(err) or str(
                err).startswith('Template'):
            # We want to list the available templates first
            ioc_common.logit({
                "level": "ERROR",
                "message": f"Template: {release} not found!"
            })
            templates = ioc.IOCage(silent=True).list('template')
            template_names = ''
            for temp in templates:
                template_names += '\n  ' + temp[1]

            ioc_common.logit({
                'level': 'EXCEPTION',
                'message': f'Created Templates:{template_names}'
            })
            exit(1)
        else:
            # Standard errors
            ioc_common.logit({
                "level": "EXCEPTION",
                "message": err
            })
