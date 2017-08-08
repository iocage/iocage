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
import click

import Release
import Jail
import Logger
import Host
import helpers

__rootcmd__ = True


def validate_count(ctx, param, value):
    """Takes a string, removes the commas and returns an int."""
    if isinstance(value, str):
        try:
            value = value.replace(",", "")

            return int(value)
        except ValueError:
            logger = Logger.Logger()
            logger.error(f"{value} is not a valid integer.")
            exit(1)
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
@click.option("--basejail", "-b", is_flag=True, default=False,
              help="Set the new jail type to a basejail. Basejails"
                   " mount the specified RELEASE directories"
                   " over the jail's directories.")
@click.option("--basejail-type", type=click.Choice(['nullfs', 'zfs']),
              help="The method of mounting release datasets into"
                   " the basejail on start.")
@click.option("--empty", "-e", is_flag=True, default=False,
              help="Create an empty jail used for unsupported or custom"
                   " jails.")
@click.option("--no-fetch", is_flag=True, default=False,
              help="Do not automatically fetch releases")
@click.option("--force", "-f", is_flag=True, default=False,
              help="Skip the interactive question.")
@click.option("--log-level", "-d", default=None)
@click.argument("props", nargs=-1)
def cli(release, template, count, props, pkglist, basejail, basejail_type,
        empty, name, no_fetch, force, log_level):

    zfs = helpers.get_zfs()
    logger = Logger.Logger()
    host = Host.Host(logger=logger, zfs=zfs)

    if log_level is not None:
        logger.print_level = log_level

    jail_data = {}

    if release is None:
        logger.spam(
            f"No release selected (-r, --release)."
            f" Selecting host release '{host.release_version}' as default."
        )
        release = host.release_version

    if name:
        jail_data["name"] = name

    release = Release.Release(name=release, logger=logger, host=host, zfs=zfs)
    if not release.fetched:
        name = release.name
        if not release.available:
            logger.error(
                f"The release '{release.name}' does not exist"
            )
            exit(1)

        msg = (
            f"The release '{release.name}' is available,"
            "but not downloaded yet"
        )
        if no_fetch:
            logger.error(msg)
            exit(1)
        else:
            logger.spam(msg)
            logger.log("Automatically fetching release '{release.name}'")
            release.fetch()

    if basejail:
        jail_data["basejail"] = True

    if basejail_type is not None:
        if not basejail:
            logger.error(
                "Cannot set --basejail-type without --basejail option")
            exit(1)
        jail_data["basejail_type"] = basejail_type

    if props:
        for prop in props:
            try:
                key, value = prop.split("=", maxsplit=1)
                jail_data[key] = value
            except:
                logger.error(f"Invalid property {prop}")
                exit(1)

    errors = False
    for i in range(count):

        jail = Jail.Jail(
            jail_data,
            logger=logger,
            host=host,
            zfs=zfs,
            new=True
        )

        suffix = " ({i}/{count})" if count > 1 else ""
        try:
            jail.create(release.name, auto_download=True)
            msg = f"{jail.humanreadable_name} successfully created!{suffix}"
            logger.log(msg)
        except:
            errors = True
            msg = f"{jail.humanreadable_name} could not be created!{suffix}"
            logger.warn(msg)

    exit(1 if errors is True else 0)
