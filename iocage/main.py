"""The main CLI for ioc."""
from __future__ import print_function

import glob
import imp
import logging
import os
import stat
import sys

import click

from iocage.lib.ioc_check import IOCCheck

try:
    os.environ["LANG"]
except KeyError:
    exit("Please set a UTF-8 locale before using iocage.")


def print_version(ctx, param, value):
    """Prints the version and then exits."""
    if not value or ctx.resilient_parsing:
        return
    print("Version\t0.9.7 2017/03/08")
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
    log_file = os.environ.get("IOCAGE_LOGFILE", "/dev/stdout")
    mode = "a" if not stat.S_ISCHR(os.stat(log_file).st_mode) else "w"

    for arg in sys.argv:
        key, _, val = arg.partition("=")
        if "IOCAGE_LOGFILE" in key:
            if val:
                log_file = val

            # If IOCAGE_LOGFILE is supplied on activate AFTER the pool name,
            # hilarity ensues. Let's avoid that.
            sys.argv.remove(arg)

    logging.basicConfig(filename=log_file, filemode=mode, level=logging.DEBUG,
                        format='%(message)s')
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
