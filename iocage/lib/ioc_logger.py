import logging
import logging.handlers
import os
import sys
from logging.config import dictConfig

import coloredlogs


class IOCLogger(object):
    def __init__(self):
        self.cli_logger = logging.getLogger("iocage")
        self.log_file = os.environ.get("IOCAGE_LOGFILE", "/var/log/iocage.log")

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

        if os.geteuid() == 0:
            logging.config.dictConfig(default_logging)

        coloredlogs.install(level="INFO", logger=self.cli_logger,
                            fmt="%(message)s",
                            stream=sys.stdout, level_styles=cli_colors)

    def cli_log(self):
        return self.cli_logger

