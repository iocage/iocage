import logging
import logging.handlers
import os
from logging.config import dictConfig

import coloredlogs
import sys


class IOCLogger(object):
    def __init__(self):
        self.logger = logging.getLogger("iocage")
        self.cli_logger = logging.getLogger("iocage")

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
        coloredlogs.install(level="INFO", logger=self.cli_logger,
                            fmt="%(message)s",
                            stream=sys.stdout, level_styles=cli_colors)

    def cli_log(self):
        return self.cli_logger


class Logger(object):
    """Pseudo-Class for Logger - Wrapper for logging module"""
    log_file = os.environ.get("IOCAGE_LOGFILE", "/var/log/iocage.log")

    DEFAULT_LOGGING = {
        'version'                 : 1,
        'disable_existing_loggers': True,
        'root'                    : {
            'level'   : 'NOTSET',
            'handlers': ['file'],
        },
        'handlers'                : {
            'file': {
                'level'      : 'DEBUG',
                'class'      : 'logging.handlers.RotatingFileHandler',
                'filename'   : f'{log_file}',
                'mode'       : 'a',
                'maxBytes'   : 10485760,
                'backupCount': 5,
                'encoding'   : 'utf-8',
                'formatter'  : 'file',
            },
        },
        'formatters'              : {
            'file': {
                'format' : '%(asctime)s (%(levelname)s) %(message)s',
                'datefmt': '%Y/%m/%d %H:%M:%S',
            },
        },
    }

    def __init__(self, application_name):
        self.application_name = application_name

    def _set_output_file(self):
        """Set the output format for file log."""
        dictConfig(self.DEFAULT_LOGGING)

    def configure_logging(self):
        if os.geteuid() == 0:
            self._set_output_file()
        else:
            for handler in logging.root.handlers:
                if isinstance(handler, logging.StreamHandler):
                    logging.root.removeHandler(handler)

        logging.root.setLevel(logging.DEBUG)

    def getLogger(self):
        self.configure_logging()

        return logging.getLogger(self.application_name)
