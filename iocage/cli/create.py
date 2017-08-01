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
import sys
import re

import click

import Release
import Jail
import Logger

logger = Logger.Logger()
__rootcmd__ = True


def validate_count(ctx, param, value):
    """Takes a string, removes the commas and returns an int."""
    if isinstance(value, str):
        try:
            value = value.replace(",", "")

            return int(value)
        except ValueError:
            logger.log.error(f"{value} is not a valid integer.")
            sys.exit(1)
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
@click.option("--log-level", "-d", default="info")
@click.argument("props", nargs=-1)
def cli(release, template, count, props, pkglist, basejail, clonejail_cj,
        empty, short, name, _uuid, force, log_level):

    if basejail and clonejail_cj:
        logger.error("A jail can either be a basejail or a clonejail")
        sys.exit(1)

    if name:
        # noinspection Annotator
        valid = True if re.match("^[a-zA-Z0-9\._-]+$", name) else False
        if not valid:
            error_message = f"Invalid character in {name}, please remove it."
            logger.error(error_message)
            raise Exception(error_message)

    release = Release.Release(name=release)
    if not release.fetched:
        name = release.name
        if not release.available:
            error_message = f"The release '{name}' does not exist"
            logger.error(error_message)
            raise Exception(error_message)
        msg = f"The release '{name}' is available, but not downloaded yet"
        logger.error(msg)
        raise Exception(msg)

    for i in range(count):
        jail = Jail.Jail({
            "basejail": basejail,
            "clonejail": clonejail_cj
        })

        if props:
            for prop in props:
                try:
                    key, value = prop.split("=", maxsplit=1)
                    jail.config.__setattr__(key, value)
                except:
                    logger.error(f"Invalid property {prop}")
                    sys.exit(1)

        jail.create(release.name)
