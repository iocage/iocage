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
import sys

import Release
import Host
import Logger
import Prompts

__rootcmd__ = True

logger = Logger.Logger()
host = Host.Host(logger=logger)
prompts = Prompts.Prompts(host=host)

def validate_count(ctx, param, value):
    """Takes a string, removes the commas and returns an int."""
    if isinstance(value, str):
        try:
            value = value.replace(",", "")

            return int(value)
        except ValueError:
            msg = f"({value} is not a valid integer"
            logger.error(msg)
            sys.exit(1)
    else:
        return int(value)

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


@click.command(context_settings=dict(
    max_content_width=400, ),
    name="fetch", help="Fetch a version of FreeBSD for jail usage or a"
                       " preconfigured plugin.")
@click.option("--url", "-u",
              help="Remote URL with path to the release/snapshot directory")
@click.option("--file", "-F", multiple=True,
              help="Specify the files to fetch from the mirror.")
# @click.option("--auth", "-a", default=None, help="Authentication method for "
#                                                 "HTTP fetching. Valid "
#                                                 "values: basic, digest")
# @click.option("--verify/--noverify", "-V/-NV", default=True,
#               help="Enable or disable verifying SSL cert for HTTP fetching.")
@click.option("--release", "-r",
              prompt=f"Release ({host.release_version})",
              default=prompts.release,
              # type=release_choice(),
              help="The FreeBSD release to fetch.")
# @click.option("--plugin-file", "-P", is_flag=True,
#              help="This is a plugin file outside the INDEX, but exists in "
#                   "that location.\nDeveloper option, most will prefer to "
#                   "use --plugins.")
# @click.option("--plugins", help="List all available plugins for creation.",
#              is_flag=True)
# @click.argument("props", nargs=-1)
@click.option("--update/--noupdate", "-U/-NU", default=True,
              help="Decide whether or not to update the fetch to the latest "
                   "patch level.")
# @click.option("--eol/--noeol", "-E/-NE", default=True,
#               help="Enable or disable EOL checking with upstream.")
# @click.option("--name", "-n", help="Supply a plugin name for --plugins to "
#                                    "fetch or use a autocompleted filename"
#                                    " for --plugin-file.\nAlso accepts full"
#                                    " path for --plugin-file.")
# @click.option("--accept/--noaccept", default=False,
#              help="Accept the plugin's LICENSE agreement.")
# Compat
@click.option("--http", "-h", default=False,
              help="Have --server define a HTTP server instead.", is_flag=True)
# Compat files
@click.option("--files", multiple=True,
              help="Specify the files to fetch from the mirror. "
              "(Deprecared: renamed to --file)")
# def cli(url, files, release, update):
def cli(**kwargs):

    release_input = kwargs["release"]

    if isinstance(release_input, int):
        try:
            release = host.distribution.releases[int(release_input)]
        except:
            logger.error("Selection {release_input} out of range")
            sys.exit(1)

    try:
        release = Release.Release(
            name=release_input,
            host=host,
            logger=logger
        )
    except:
        self.logger.error("Invalid Release '{release_input}'")

    url_or_files_selected = False

    # optional --url
    try:
        url = kwargs["url"]
        if url:
            release.mirror_url = url
            url_or_files_selected = True
    except:
        pass

    # optional --files
    try:
        files = kwargs["files"]
        if files:
            release.assets = list(files)
            url_or_files_selected = True
    except:
        pass

    if (url_or_files_selected is False) and (release.available is False):
        logger.error("The release '{release.name}' is not available")
        sys.exit(1)

    logger.log("Fetching release '{release.name}' from '{release.mirror_url}'")
    release.fetch()
