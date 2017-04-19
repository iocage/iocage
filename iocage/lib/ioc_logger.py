import logging
import logging.handlers
import os
import sys
from logging.config import dictConfig


class LoggerFormatter(logging.Formatter):
    """Format the console log messages"""

    CONSOLE_COLOR_FORMATTER = {
        'YELLOW' : '\033[1;33m',  # (warning)
        'GREEN'    : '\033[1;40;97m',  # (info)
        'RED'    : '\033[1;31m',  # (error)
        'HIGHRED': '\033[1;49;31m',  # (critical)
        'RESET'  : '\033[1;m',  # Reset
        'MSG'  : '\033[1;32m',  # General message
    }
    LOGGING_LEVEL = {
        'CRITICAL': 50,
        'ERROR'   : 40,
        'WARNING' : 30,
        'INFO'    : 20,
        'DEBUG'   : 10,
        'NOTSET'  : 0
    }

    def format(self, record):
        """Set the color based on the log level.

            Returns:
                logging.Formatter class.
        """

        if record.levelno == self.LOGGING_LEVEL['CRITICAL']:
            color_start = self.CONSOLE_COLOR_FORMATTER['HIGHRED']
        elif record.levelno == self.LOGGING_LEVEL['ERROR']:
            color_start = self.CONSOLE_COLOR_FORMATTER['HIGHRED']
        elif record.levelno == self.LOGGING_LEVEL['WARNING']:
            color_start = self.CONSOLE_COLOR_FORMATTER['RED']
        elif record.levelno == self.LOGGING_LEVEL['INFO']:
            color_start = self.CONSOLE_COLOR_FORMATTER['GREEN']
        elif record.levelno == self.LOGGING_LEVEL['DEBUG']:
            color_start = self.CONSOLE_COLOR_FORMATTER['YELLOW']
        else:
            color_start = self.CONSOLE_COLOR_FORMATTER['RESET']

        color_reset = self.CONSOLE_COLOR_FORMATTER['RESET']

        record.levelname = color_start
        record.msg = record.msg + color_reset

        return logging.Formatter.format(self, record)


class LoggerStream(object):
    def __init__(self, logger):
        self.logger = logger
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.debug(line.rstrip())


class Logger(object):
    """Pseudo-Class for Logger - Wrapper for logging module"""
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
                'filename'   : '/var/log/iocage.log',
                'mode'       : 'a',
                'maxBytes'   : 10485760,
                'backupCount': 5,
                'encoding'   : 'utf-8',
                'formatter'  : 'file',
            },
        },
        'formatters'              : {
            'file': {
                'format' : '(%(levelname)s) %(message)s',
                'datefmt': '%Y/%m/%d %H:%M:%S',
            },
        },
    }

    def __init__(self, application_name):
        self.application_name = application_name

    def _set_output_file(self):
        """Set the output format for file log."""
        dictConfig(self.DEFAULT_LOGGING)

    def _set_output_console(self):
        """Set the output format for console."""

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)

        log_format = "%(levelname)s%(message)s"
        time_format = "%Y/%m/%d %H:%M:%S"

        if os.isatty(sys.stdout.fileno()):
            console_handler.setFormatter(
                LoggerFormatter(log_format, datefmt=time_format))

        logging.root.addHandler(console_handler)

    def configure_logging(self):
        if os.geteuid() == 0:
            self._set_output_file()
        else:
            for handler in logging.root.handlers:
                if isinstance(handler, logging.StreamHandler):
                    logging.root.removeHandler(handler)

        self._set_output_console()
        logging.root.setLevel(logging.DEBUG)

    def getLogger(self):
        self.configure_logging()

        return logging.getLogger(self.application_name)
