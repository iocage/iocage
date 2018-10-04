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
"""Use CLI helper functions for console output."""
import typing
import texttable


def print_table(
    data: typing.List[typing.List[str]],
    columns: typing.List[str],
    show_header: bool=True,
    sort_key: typing.Optional[str]=None
) -> None:
    """Print a table to stdout."""
    table = texttable.Texttable(max_width=0)
    table.set_cols_dtype(["t"] * len(columns))

    table_head = (list(x.upper() for x in columns))
    table_data = data

    if sort_key is None:
        sort_index = -1
    else:
        try:
            sort_index = columns.index(sort_key)
        except ValueError:
            sort_index = -1

    if sort_index > -1:
        table_data.sort(key=lambda x: x[sort_index])

    if show_header is True:
        table.add_rows([table_head] + table_data)
    else:
        table.add_rows(table_data, header=False)

    print(table.draw())
