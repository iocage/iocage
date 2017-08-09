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
"""fetch module for the cli."""
import click

import iocage.lib.Release
import iocage.lib.Host
import iocage.lib.Logger
import iocage.lib.Prompts


__rootcmd__ = True


# ToDo: remove disabled feature
# def _prettify_release_names(x):
#     if x.name == host.release_version:
#         return f"\033[1m{x.name}\033[0m"
#     else:
#         return x.name
# def release_choice():
#     version =
#     return click.Choice(list(map(
#         _prettify_release_names,
#         host.distribution.releases
#     )))
logger = lib.Logger.Logger()
host = lib.Host.Host()
prompts = lib.Prompts.Prompts(host=host)


@click.command(context_settings=dict(
    max_content_width=400, ),
    name="fetch", help="Fetch a version of FreeBSD for jail usage or a"
                       " preconfigured plugin.")
@click.option("--url", "-u",
              help="Remote URL with path to the release/snapshot directory")
@click.option("--file", "-F", multiple=True,
              help="Specify the files to fetch from the mirror.")
@click.option("--release", "-r",
              prompt=f"Release ({host.release_version})",
              default=prompts.release,
              # type=release_choice(),
              help="The FreeBSD release to fetch.")
@click.option("--update/--no-update", "-U/-NU", default=True,
              help="Decide whether or not to update the fetch to the latest "
                   "patch level.")
@click.option("--fetch-updates/--no-fetch-updates", default=True,
              help="Skip fetching release updates")
# Compat
@click.option("--http", "-h", default=False,
              help="Have --server define a HTTP server instead.", is_flag=True)
# Compat files
@click.option("--files", multiple=True,
              help="Specify the files to fetch from the mirror. "
              "(Deprecared: renamed to --file)")
@click.option("--log-level", "-d", default=None)
# @click.option("--auth", "-a", default=None, help="Authentication method for "
#                                                 "HTTP fetching. Valid "
#                                                 "values: basic, digest")
# @click.option("--verify/--noverify", "-V/-NV", default=True,
#               help="Enable or disable verifying SSL cert for HTTP fetching.")
# def cli(url, files, release, update):
def cli(**kwargs):

    if kwargs["log_level"] is not None:
        logger.print_level = kwargs["log_level"]

    release_input = kwargs["release"]

    if isinstance(release_input, int):
        try:
            release = host.distribution.releases[release_input]
        except:
            logger.error(f"Selection {release_input} out of range")
            exit(1)
    else:
        try:
            release = lib.Release.Release(
                name=release_input,
                host=host,
                logger=logger
            )
        except:
            logger.error(f"Invalid Release '{release_input}'")
            exit(1)

    url_or_files_selected = False

    if is_option_enabled(kwargs, "url"):
        release.mirror_url = kwargs["url"]
        url_or_files_selected = True

    if is_option_enabled(kwargs, "files"):
        release.assets = list(kwargs["files"])
        url_or_files_selected = True

    if (url_or_files_selected is False) and (release.available is False):
        logger.error(f"The release '{release.name}' is not available")
        exit(1)

    if release.fetched:
        msg = f"Release '{release.name}' is already fetched"
        if kwargs["update"] is True:
            logger.log(f"{msg} - updating only")
        else:
            logger.log(f"{msg} - skipping download and updates")
            exit(0)
    else:
        logger.log(
            f"Fetching release '{release.name}' from '{release.mirror_url}'"
        )
        release.fetch(update=False, fetch_updates=False)

    if kwargs["fetch_updates"] is True:
        logger.log("Fetching updates")
        release.fetch_updates()

    if kwargs["update"] is True:
        logger.log("Updating release")
        release.update()

    logger.log('done')
    exit(0)


def is_option_enabled(args, name):

    try:
        value = args[name]
        if value:
            return True
    except:
        pass

    return False
