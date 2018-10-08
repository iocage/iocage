# Copyright (c) 2014-2018, iocage
# Copyright (c) 2017-2018, Stefan Grönke
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
"""View and manipulate fstab files of a jail."""
import typing
import errno
import click
import os

import iocage.errors
import iocage.Logger
import iocage.Host
import iocage.helpers
import iocage.Jail
import iocage.Config.Jail.File.Fstab

from .shared.jail import get_jail
from .shared.click import IocageClickContext

__rootcmd__ = True
FstabLine = iocage.Config.Jail.File.Fstab.FstabLine


def _get_relpath(path: str, jail: iocage.Jail.JailGenerator) -> str:
    if path.startswith(jail.root_path) is True:
        return path[len(jail.root_path.rstrip("/")):]
    else:
        return path


def _get_abspath(path: str, jail: iocage.Jail.JailGenerator) -> str:
    result = str(os.path.realpath(os.path.join(
        jail.root_path,
        _get_relpath(path, jail).lstrip("/")
    )))

    if result.startswith(jail.root_path):
        return result

    raise iocage.errors.InsecureJailPath(
        path=result,
        logger=jail.logger
    )


@click.command(
    name="add"
)
@click.pass_context
@click.argument(
    "source",
    nargs=1,
    required=True
)
@click.argument(
    "destination",
    nargs=-1,
    required=False
)
@click.argument("jail", nargs=1, required=True)
@click.option("--read-write", "-rw", is_flag=True, default=False)
def cli_add(
    ctx: IocageClickContext,
    source: str,
    destination: typing.Tuple[str],
    jail: str,
    read_write: bool
) -> None:
    """Add lines to a jails fstab file."""
    ioc_jail = get_jail(jail, ctx.parent)

    if len(destination) == 0:
        desination_path = source
    else:
        desination_path = destination[0]

    if os.path.exists(source) is False:
        ctx.parent.logger.error(
            f"The mount source {source} is does not exist"
        )
        exit(1)

    if os.path.isdir(source) is False:
        ctx.parent.logger.error(
            f"The mount source {source} is not a directory"
        )
        exit(1)

    try:
        mount_opts = "rw" if read_write is True else "ro"
        desination_path = _get_abspath(desination_path, ioc_jail)

        fstab = ioc_jail.fstab
        fstab.read_file()
        fstab.new_line(
            source=source,
            destination=desination_path,
            type="nullfs",
            options=mount_opts,
            dump="0",
            passnum="0",
            comment=None
        )

        # ensure destination directory exists
        try:
            os.makedirs(desination_path)
        except OSError as exc:  # Python >2.5
            if exc.errno == errno.EEXIST and os.path.isdir(desination_path):
                pass
            else:
                raise

        fstab.save()
        ctx.parent.logger.log(
            f"fstab mount added: {source} -> {desination_path} ({mount_opts})"
        )
        exit(0)
    except iocage.errors.IocageException:
        exit(1)


@click.command(
    name="show"
)
@click.pass_context
@click.argument("jail", nargs=1, required=True)
def cli_show(ctx: IocageClickContext, jail: str) -> None:
    """Show a jails fstab file."""
    ioc_jail = get_jail(jail, ctx.parent)
    if os.path.isfile(ioc_jail.fstab.path):
        with open(ioc_jail.fstab.path, "r") as f:
            print(f.read())


@click.command(
    name="rm"
)
@click.argument(
    "source",
    nargs=1,
    required=False
)
@click.argument("jail", nargs=1, required=True)
@click.pass_context
def cli_rm(ctx: IocageClickContext, source: str, jail: str) -> None:
    """Remove a line from a jails fstab file."""
    ioc_jail = get_jail(jail, ctx.parent)
    fstab = ioc_jail.fstab
    destination = None
    i = 0

    try:
        fstab.read_file()
        for existing_line in fstab:
            i += 1
            if isinstance(existing_line, FstabLine) is False:
                continue
            if existing_line["source"] == source:
                destination = fstab[i - 1]["destination"]
                del fstab[i - 1]
                fstab.save()
                break
    except iocage.errors.IocageException:
        exit(1)

    if destination is None:
        ctx.parent.logger.error("no matching fstab line found")
        exit(1)

    ctx.parent.logger.log(f"fstab mount removed: {source} -> {destination}")


class FstabCli(click.MultiCommand):
    """Python Click fstab subcommand boilerplate."""

    def list_commands(self, ctx: click.core.Context) -> list:
        """Mock subcommands for Python Click."""
        return [
            "show",
            "add",
            "rm"
        ]

    def get_command(
        self,
        ctx: click.core.Context,
        cmd_name: str
    ) -> click.core.Command:
        """Wrap subcommand for Python Click."""
        command: typing.Optional[click.core.Command] = None

        if cmd_name == "show":
            command = cli_show
        elif cmd_name == "add":
            command = cli_add
        elif cmd_name == "rm":
            command = cli_rm

        if command is None:
            raise NotImplementedError("action does not exist")

        return command


@click.group(
    name="fstab",
    cls=FstabCli,
    context_settings=dict(
        ignore_unknown_options=True,
    )
)
@click.pass_context
def cli(
    ctx: IocageClickContext
) -> None:
    """View and manipulate a jails fstab file."""
    ctx.logger = ctx.parent.logger
    ctx.host = ctx.parent.host
