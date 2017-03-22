"""iocage logging module."""

import logging

def getLogger(name):
    logfile = logging.FileHandler('/var/log/some.log')
    logfile.setLevel(logging.DEBUG)

    logger = logging.getLogger(name)
    logger.addHandler(logfile)
    return logger
