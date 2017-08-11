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
import logging
import logging.config
import logging.handlers
import os
import sys

import coloredlogs
import verboselogs


class IOCLogger(object):
    def __init__(self):
        self.cli_logger_stdout = verboselogs.VerboseLogger("iocage")
        self.cli_logger_stderr = verboselogs.VerboseLogger("iocage_stderr")
        self.log_file = os.environ.get("IOCAGE_LOGFILE", "/var/log/iocage.log")
        self.colorize = os.environ.get("IOCAGE_COLOR", "FALSE")

        default_logging = {
            'version'                 : 1,
            'disable_existing_loggers': False,
            'formatters'              : {
                'log': {
                    'format' : '%(asctime)s (%(levelname)s) %(message)s',
                    'datefmt': '%Y/%m/%d %H:%M:%S',
                },
            },
            'handlers'                : {
                'file': {
                    'level'      : 'DEBUG',
                    'class'      : 'logging.handlers.RotatingFileHandler',
                    'filename'   : f'{self.log_file}',
                    'mode'       : 'a',
                    'maxBytes'   : 10485760,
                    'backupCount': 5,
                    'encoding'   : 'utf-8',
                    'formatter'  : 'log',
                },
            },
            'loggers'                 : {
                '': {
                    'handlers' : ['file'],
                    'level'    : 'DEBUG',
                    'propagate': True
                },
            },
        }

        if self.colorize == "TRUE":
            cli_colors = {
                'info'    : {'color': 'white'},
                'notice'  : {'color': 'magenta'},
                'verbose' : {'color': 'blue'},
                'spam'    : {'color': 'green'},
                'critical': {'color': 'red', 'bold': True},
                'error'   : {'color': 'red'},
                'debug'   : {'color': 'green'},
                'warning' : {'color': 'yellow'}
            }
        else:
            cli_colors = {}

        if os.geteuid() == 0:
            logging.config.dictConfig(default_logging)

        coloredlogs.install(level="VERBOSE", logger=self.cli_logger_stdout,
                            fmt="%(message)s",
                            stream=sys.stdout, level_styles=cli_colors)
        coloredlogs.install(level="WARNING", logger=self.cli_logger_stderr,
                            fmt="%(message)s",
                            stream=sys.stderr, level_styles=cli_colors)

    def cli_log_stdout(self):
        return self.cli_logger_stdout

    def cli_log_stderr(self):
        return self.cli_logger_stderr
