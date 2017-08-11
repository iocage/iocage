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
"""clean module for the cli."""
import click

import iocage.lib.ioc_common as ioc_common
import iocage.lib.iocage as ioc

__rootcmd__ = True


@click.command(name="clean", help="Destroy specified dataset types.")
@click.option("--force", "-f", default=False, is_flag=True,
              help="Runs the command with no further user interaction.")
@click.option("--all", "-a", "dataset_type", flag_value="all",
              help="Destroy all iocage data that has been created.")
@click.option("--jails", "-j", "dataset_type", flag_value="jails",
              help="Destroy all jails created.")
@click.option("--base", "-r", "-b", "dataset_type", flag_value="release",
              help="Destroy all RELEASEs fetched.")
@click.option("--template", "-t", "dataset_type", flag_value="template",
              help="Destroy all templates.")
def cli(force, dataset_type):
    """Calls the correct destroy function."""
    if dataset_type == "jails":
        msg = {
            "level"  : "WARNING",
            "message": "\nThis will destroy ALL jails and any "
                       "snapshots on a RELEASE,"
                       "including templates!"
        }
    elif dataset_type == "all":
        msg = {
            "level"  : "WARNING",
            "message": "\nThis will destroy ALL iocage data!"
        }
    elif dataset_type == "release":
        msg = {
            "level"  : "WARNING",
            "message": "\nThis will destroy ALL fetched RELEASES and"
                       " jails/templates created from them!"
        }
    elif dataset_type == "template":
        msg = {
            "level"  : "WARNING",
            "message": "This will destroy ALL templates and jails"
                       " created from them!"
        }
    else:
        ioc_common.logit({
            "level"  : "EXCEPTION",
            "message": "Please specify a dataset type to clean!"
        }, exit_on_error=True)

    if not force:
        ioc_common.logit(msg)
        if not click.confirm("\nAre you sure?"):
            exit()

    ioc.IOCage(exit_on_error=True, skip_jails=True).clean(dataset_type)
