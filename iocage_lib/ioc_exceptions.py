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
"""Exception classes for iocage"""
import collections
from contextlib import contextmanager


class ExceptionWithMsg(Exception):
    """message attribute will be an iterable if a message is supplied"""
    def __init__(self, message):
        if not isinstance(message, str) and not isinstance(
            message,
            collections.Iterable
        ):
            message = [message]

        self.message = message
        super().__init__(message)


class PoolNotActivated(Exception):
    pass


class JailRunning(Exception):
    pass


class CommandFailed(ExceptionWithMsg):
    pass


class CommandNeedsRoot(ExceptionWithMsg):
    pass


class JailMisconfigured(ExceptionWithMsg):
    pass


class JailCorruptConfiguration(JailMisconfigured):
    pass


class JailMissingConfiguration(JailMisconfigured):
    pass


class ValidationFailed(ExceptionWithMsg):
    pass


class ValueNotFound(Exception):
    pass


class Exists(ExceptionWithMsg):
    pass


@contextmanager
def ignore_exceptions(*exceptions, clean=None, suppress_exception=True):
    """
    Ignore any exceptions specified by `exceptions` and make sure that
    we clean any resources specified by callable `clean`
    """
    try:
        yield
    except exceptions as e:
        if clean is not None:
            assert callable(clean) is True

            return clean()

        if not suppress_exception:
            # For cases where this block is used dynamically to suppress
            # exceptions
            raise e
