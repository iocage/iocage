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
"""The main CLI for ioc."""
import locale
import os
import re
import signal
import subprocess as su
import sys

import click

click.core._verify_python3_env = lambda: None
user_locale = os.environ.get("LANG", "en_US.UTF-8")
locale.setlocale(locale.LC_ALL, user_locale)

# inject ./cli to path
__dirname = os.path.dirname(__file__)
iocage_cmd_folder = os.path.join(__dirname, "cli")
sys.path = [iocage_cmd_folder] + sys.path

# @formatter:off
# Sometimes SIGINT won't be installed.
# http://stackoverflow.com/questions/40775054/capturing-sigint-using-keyboardinterrupt-exception-works-in-terminal-not-in-scr/40785230#40785230
signal.signal(signal.SIGINT, signal.default_int_handler)
# If a utility decides to cut off the pipe, we don't care (IE: head)
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
# @formatter:on

try:
    su.check_call(["sysctl", "vfs.zfs.version.spa"],
                  stdout=su.PIPE, stderr=su.PIPE)
except su.CalledProcessError:
    sys.exit("ZFS is required to use iocage.\n"
             "Try calling 'kldload zfs' as root.")


class IOCageCLI(click.MultiCommand):
    """
    Iterates in the 'cli' directory and will load any module's cli definition.
    """

    def list_commands(self, ctx):
        rv = []

        for filename in os.listdir(iocage_cmd_folder):
            if filename.endswith('.py') and \
                    not filename.startswith('__init__'):
                rv.append(re.sub(".py$", "", filename))
        rv.sort()

        return rv

    def get_command(self, ctx, name):
        try:
            mod = __import__(name, None, None, ["cli"])

            try:
                if mod.__rootcmd__ and "--help" not in sys.argv[1:]:
                    if len(sys.argv) != 1:
                        if os.geteuid() != 0:
                            sys.exit("You need to have root privileges to"
                                     f" run {mod.__name__}")
            except AttributeError:
                # It's not a root required command.
                pass

            return mod.cli
        except (ImportError, AttributeError):
            return


@click.command(cls=IOCageCLI)
@click.version_option(version="0.9.10 07/30/2017", prog_name="iocage",
                      message="%(cat )s")
def cli():
    """A jail manager."""

if __name__ == '__main__':
    cli(prog_name="iocage")
