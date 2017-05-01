"""The main CLI for ioc."""
import glob
import imp
import locale
import os
import signal
import subprocess as su
import sys

import click
# This prevents it from getting in our way.
from click import core

from iocage.lib.ioc_check import IOCCheck

core._verify_python3_env = lambda: None
user_locale = os.environ.get("LANG", "en_US.UTF-8")
locale.setlocale(locale.LC_ALL, user_locale)

# @formatter:off
# Sometimes SIGINT won't be installed.
# http://stackoverflow.com/questions/40775054/capturing-sigint-using-keyboardinterrupt-exception-works-in-terminal-not-in-scr/40785230#40785230
signal.signal(signal.SIGINT, signal.default_int_handler)
# @formatter:on

try:
    su.check_call(["sysctl", "vfs.zfs.version.spa"],
                  stdout=su.PIPE, stderr=su.PIPE)
except su.CalledProcessError:
    sys.exit("ZFS is required to use iocage.\n"
             "Try calling 'kldload zfs' as root.")


def print_version(ctx, param, value):
    """Prints the version and then exits."""
    if not value or ctx.resilient_parsing:
        return
    print("Version\t0.9.8 BETA")
    sys.exit()


@click.group(help="A jail manager.")
@click.option("--version", "-v", is_flag=True, callback=print_version,
              help="Display iocage's version and exit.")
@click.pass_context
def cli(ctx, version):
    """The placeholder for the calls."""
    mod = ctx.obj[ctx.invoked_subcommand]
    try:
        if mod.__rootcmd__:
            if "--help" not in sys.argv[1:]:
                if os.geteuid() != 0:
                    sys.exit("You need to have root privileges"
                             " to run {}!".format(mod.__name__))
    except AttributeError:
        pass


IOC_LIB = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join("{}/cli".format(IOC_LIB))
MODULES = {}
for lib in glob.glob("{}/*.py".format(PATH)):
    if "__init__.py" in lib:
        continue

    replace = lib.split("/")[-1].replace(".py", "")
    _file, pathname, description = imp.find_module(replace, [PATH])
    module = imp.load_module(replace, _file, pathname, description)
    MODULES[replace] = module
    cli.add_command(getattr(module, module.__cmdname__))


def main():
    skip_check = False
    skip_check_cmds = ["--help", "activate", "deactivate", "-v", "--version"]

    try:
        if "iocage" in sys.argv[0] and len(sys.argv) == 1:
            skip_check = True

        for arg in sys.argv[1:]:
            if arg in skip_check_cmds:
                skip_check = True
            elif "clean" in arg:
                skip_check = True
                IOCCheck(silent=True)

        if not skip_check:
            IOCCheck()

        cli(obj=MODULES)
    except RuntimeError as err:
        exit(err)


if __name__ == '__main__':
    main()
