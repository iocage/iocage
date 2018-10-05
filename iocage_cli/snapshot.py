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
"""Create and manage jail snapshots with the CLI."""
import typing
import click

import iocage.Jail
import iocage.Logger

from .shared.click import IocageClickContext
from .shared.jail import get_jail
from .shared.output import print_table

__rootcmd__ = True


@click.command(
    name="list_or_create"
)
@click.pass_context
def cli_list_or_create(
    ctx: IocageClickContext
) -> None:
    """
    Choose whether to list or create a snapshot.

    When a full snapshot identifier `<dataset>@<snapshot_name>` is seen, the
    snapshot will be created. Otherwise existing snapshots are listed.
    """
    if "@" in ctx.info_name:
        return _cli_create(ctx, ctx.info_name)
    else:
        return _cli_list(ctx, ctx.info_name)


@click.command(
    name="create",
    help="Create a snapshot"
)
@click.pass_context
@click.argument("identifier", nargs=1, required=True)
def cli_create(ctx: IocageClickContext, identifier: str) -> None:
    """Create a snapshot."""
    _cli_create(ctx, identifier)


def _cli_create(ctx: IocageClickContext, identifier: str) -> None:
    try:
        ioc_jail, snapshot_name = _parse_identifier(
            ctx=ctx.parent,
            identifier=identifier,
            require_full_identifier=True
        )
        ioc_jail.snapshots.create(snapshot_name)
    except iocage.errors.IocageException:
        pass


@click.command(
    name="rollback",
    help="Rollback to a snapshot"
)
@click.pass_context
@click.argument("identifier", nargs=1, required=True)
@click.option("--force", "-f", is_flag=True, help="Force ZFS rollback")
def cli_rollback(
    ctx: IocageClickContext,
    identifier: str,
    force: bool
) -> None:
    """Rollback to a previously taken snapshot."""
    try:
        ioc_jail, snapshot_name = _parse_identifier(
            ctx=ctx.parent,
            identifier=identifier,
            require_full_identifier=True
        )
        ioc_jail.snapshots.rollback(snapshot_name, force=force)
    except iocage.errors.IocageException:
        pass


@click.command(
    name="list",
    help="List all snapshots"
)
@click.pass_context
@click.argument("jail", nargs=1, required=True)
def cli_list(ctx: IocageClickContext, jail: str) -> None:
    """List existing snapshots."""
    _cli_list(ctx, jail)


def _cli_list(ctx: IocageClickContext, jail: str) -> None:
    try:
        ioc_jail, snapshot_name = _parse_identifier(
            ctx=ctx.parent,
            identifier=jail,
            require_full_identifier=False
        )
        columns = ["NAME"]
        data = [[x.name.split("@", maxsplit=1)[1]] for x in ioc_jail.snapshots]
        print_table(data, columns)
    except iocage.errors.IocageException:
        pass


@click.command(
    name="remove",
    help="Delete existing snapshots"
)
@click.argument("identifier", nargs=1, required=True)
@click.pass_context
def cli_remove(ctx: IocageClickContext, identifier: str) -> None:
    """Remove a snapshot."""
    try:
        ioc_jail, snapshot_name = _parse_identifier(
            ctx=ctx.parent,
            identifier=identifier,
            require_full_identifier=True
        )
        ioc_jail.snapshots.delete(snapshot_name)
    except iocage.errors.IocageException:
        pass


class SnapshotCli(click.MultiCommand):
    """Python Click snapshot subcommand boilerplate."""

    def list_commands(self, ctx: click.core.Context) -> list:
        """Mock Click subcommands."""
        return [
            "list",
            "create",
            "rollback",
            "remove"
        ]

    def get_command(
        self,
        ctx: click.core.Context,
        cmd_name: str
    ) -> click.core.Command:
        """Wrap Click subcommands."""
        command: click.core.Command

        if cmd_name == "list":
            command = cli_list
        elif cmd_name == "create":
            command = cli_create
        elif cmd_name == "remove":
            command = cli_remove
        elif cmd_name == "rollback":
            command = cli_rollback
        else:
            command = cli_list_or_create

        return command


@click.group(
    name="snapshot",
    cls=SnapshotCli,
    context_settings=dict(
        ignore_unknown_options=True,
    )
)
@click.pass_context
def cli(
    ctx: IocageClickContext
) -> None:
    """Take and manage resource snapshots."""
    ctx.logger = ctx.parent.logger
    ctx.host = ctx.parent.host


def _parse_identifier(
    ctx: IocageClickContext,
    identifier: str,
    require_full_identifier: bool=False
) -> typing.Tuple[iocage.Jail.JailGenerator, typing.Optional[str]]:

    snapshot_name: typing.Optional[str] = None
    try:
        jail, snapshot_name = identifier.split("@")
    except ValueError:
        if require_full_identifier is True:
            raise iocage.errors.InvalidSnapshotIdentifier(
                identifier=identifier,
                logger=ctx.parent.logger
            )
        jail = identifier

    return get_jail(jail, ctx), snapshot_name
