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

__rootcmd__ = True

logger = iocage.lib.Logger.Logger()
host = iocage.lib.Host.Host(logger=logger)

def validate_count(ctx, param, value):
    """Takes a string, removes the commas and returns an int."""
    if isinstance(value, str):
        try:
            value = value.replace(",", "")

            return int(value)
        except ValueError:
            ioc_common.logit({
                "level"  : "EXCEPTION",
                "message": f"({value} is not a valid integer."
            }, exit_on_error=True)
    else:
        return int(value)

def release_prompt():
    i = 0
    default = None
    for available_release in host.distribution.releases:
        if available_release.name == host.release_version:
            default = i
            print(f"[{i}] \033[1m{available_release.name}\033[0m")
        else:
            print(f"[{i}] {available_release.name}")
        i += 1
    return default

def release_prompt_title():
    return f"Release ({host.release_version})"

# def release_choice():
#     return click.Choice(list(map(
#         lambda x: f"\033[1m{x.name}\033[0m" if x.name == host.release_version else x.name,
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
#@click.option("--auth", "-a", default=None, help="Authentication method for "
#                                                 "HTTP fetching. Valid "
#                                                 "values: basic, digest")
# @click.option("--verify/--noverify", "-V/-NV", default=True,
#               help="Enable or disable verifying SSL cert for HTTP fetching.")
@click.option("--release", "-r",
              prompt=release_prompt_title(),
              default=release_prompt,
              #type=release_choice(),
              help="The FreeBSD release to fetch.")
#@click.option("--plugin-file", "-P", is_flag=True,
#              help="This is a plugin file outside the INDEX, but exists in "
#                   "that location.\nDeveloper option, most will prefer to "
#                   "use --plugins.")
#@click.option("--plugins", help="List all available plugins for creation.",
#              is_flag=True)
#@click.argument("props", nargs=-1)
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
              help="Specify the files to fetch from the mirror. (Deprecared: renamed to --file)")

#def cli(url, files, release, update):
def cli(**kwargs):

    print(kwargs)

    try:
      release = host.distribution.releases[int(kwargs["release"])]
    except:
      release = iocage.lib.Release.Release(name=kwargs["release"], host=host, logger=logger)

    print(release.name)
    # Deprecated options

    import sys
    sys.exit(1)


    if url:
        release.mirror_url = url

    if files:
        release.assets = list(files)

    release.fetch()
