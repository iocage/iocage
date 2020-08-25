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
"""The main CLI for ioc."""

import locale
import logging
import logging.config
import logging.handlers
import os
import re
import signal
import subprocess as su
import sys

import click
import coloredlogs
import iocage_lib.ioc_check as ioc_check
# This prevents it from getting in our way.
from click import core
from iocage_lib.ioc_common import set_interactive

core._verify_python3_env = lambda: None
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf8', buffering=1)
sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf8', buffering=1)
set_interactive(True)

# @formatter:off
# Sometimes SIGINT won't be installed.
# http://stackoverflow.com/questions/40775054/capturing-sigint-using-keyboardinterrupt-exception-works-in-terminal-not-in-scr/40785230#40785230
signal.signal(signal.SIGINT, signal.default_int_handler)
# If a utility decides to cut off the pipe, we don't care (IE: head)
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
# @formatter:on

try:
    su.check_call(
        ["sysctl", "vfs.zfs.version.spa"], stdout=su.PIPE, stderr=su.PIPE)
except su.CalledProcessError:
    sys.exit("ZFS is required to use iocage.\n"
             "Try calling 'kldload zfs' as root.")


def print_version(ctx, param, value):
    """Prints the version and then exits."""

    if not value or ctx.resilient_parsing:
        return
    print("Version\t1.2")
    sys.exit()


class InfoHandler(logging.Handler):

    def emit(self, record):
        log = self.format(record)

        if record.levelno < 30:
            print(log, file=sys.stdout)
        else:
            print(log, file=sys.stderr)


class IOCLogger(object):

    def __init__(self):
        self.log_file = os.environ.get("IOCAGE_LOGFILE", "/var/log/iocage.log")
        self.colorize = os.environ.get("IOCAGE_COLOR", "FALSE")
        logger = logging.getLogger("iocage")

        if logger.hasHandlers():
            # If we're imported multiple times (like tests) this will prevent
            # a large duplicate flood of text.
            logger.handlers = []

        logging.addLevelName(5, "SPAM")
        logging.addLevelName(15, "VERBOSE")
        logging.addLevelName(25, "NOTICE")
        logger.setLevel('VERBOSE')

        default_logging = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'log': {
                    'format': '%(asctime)s (%(levelname)s) %(message)s',
                    'datefmt': '%Y/%m/%d %H:%M:%S',
                },
            },
            'handlers': {
                'file': {
                    'level': 'DEBUG',
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': f'{self.log_file}',
                    'mode': 'a',
                    'maxBytes': 10485760,
                    'backupCount': 5,
                    'encoding': 'utf-8',
                    'formatter': 'log',
                },
            },
            'loggers': {
                '': {
                    'handlers': ['file'],
                    'level': 'DEBUG',
                    'propagate': False
                },
            },
        }

        if self.colorize == "TRUE":
            cli_colors = {
                'info': {'color': 'white'},
                'notice': {'color': 'magenta'},
                'verbose': {'color': 'blue'},
                'spam': {'color': 'green'},
                'critical': {'color': 'red', 'bold': True},
                'error': {'color': 'red'},
                'debug': {'color': 'green'},
                'warning': {'color': 'yellow'}
            }
        else:
            cli_colors = {}

        if os.geteuid() == 0:
            logging.config.dictConfig(default_logging)

        handler = InfoHandler()
        handler.setFormatter(coloredlogs.ColoredFormatter(
            fmt="%(message)s",
            level_styles=cli_colors))
        logger.addHandler(handler)

    def setConsoleLogLevel(self, level):
        logger = logging.getLogger("iocage")
        logger.setLevel(level)


cmd_folder = os.path.abspath(os.path.dirname(__file__))


class IOCageCLI(click.MultiCommand):

    """
    Iterates in the 'cli' directory and will load any module's cli definition.
    """

    def list_commands(self, ctx):
        rv = []

        for filename in os.listdir(cmd_folder):
            if filename.endswith('.py') and \
                    not filename.startswith('__init__'):
                rv.append(re.sub(".py$", "", filename))
        rv.sort()

        return rv

    def get_command(self, ctx, name):

        try:
            mod = __import__(f"iocage_cli.{name}", None, None, ["cli"])
            mod_name = mod.__name__.replace("iocage_cli.", "")
        except ImportError:
            # No such command
            return

        try:
            if mod.__rootcmd__ and sys.argv[-1] not in ("help", "--help"):
                if len(sys.argv) != 1:
                    if os.geteuid() != 0:
                        sys.exit("You need to have root privileges to"
                                 f" run {mod_name}")
        except AttributeError:
            # It's not a root required command.
            pass

        return mod.cli


@click.command(cls=IOCageCLI)
@click.option(
    "--version",
    "-v",
    is_flag=True,
    callback=print_version,
    help="Display iocage's version and exit.")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Allow iocage to rename datasets.")
@click.option(
    "--debug",
    "-D",
    is_flag=True,
    help="Log debug output to the console.")
def cli(version, force, debug):
    """A jail manager."""
    os.environ['IOCAGE_DEBUG'] = 'FALSE'
    logger = IOCLogger()

    if debug:
        os.environ['IOCAGE_DEBUG'] = 'TRUE'
        logger.setConsoleLogLevel(logging.DEBUG)

    skip_check = False
    os.environ["IOCAGE_SKIP"] = "FALSE"
    skip_check_cmds = ["--help", "activate", "-v", "--version", "--rc"]

    try:
        if force:
            os.environ["IOCAGE_FORCE"] = "TRUE"
        else:
            os.environ["IOCAGE_FORCE"] = "FALSE"

        if "iocage" in sys.argv[0] and len(sys.argv) == 1:
            skip_check = True
        elif "help" in sys.argv and len(sys.argv) == 3:
            cmd = sys.argv[sys.argv.index("help") - 1]
            mod = __import__(f"iocage_cli.{cmd}", None, None, ["iocage_cli"])
            with click.Context(mod.cli) as ctx:
                print(mod.cli.get_help(ctx))
                exit(0)

        for arg in sys.argv[1:]:
            if arg in skip_check_cmds:
                os.environ["IOCAGE_SKIP"] = "TRUE"
                skip_check = True
            elif "clean" in arg:
                skip_check = True
                os.environ["IOCAGE_FORCE"] = "TRUE"
                os.environ["IOCAGE_SKIP"] = "TRUE"
                ioc_check.IOCCheck(silent=True)

        if not skip_check:
            ioc_check.IOCCheck()
    except RuntimeError as err:
        exit(err)


if __name__ == '__main__':
    cli(prog_name="iocage")
