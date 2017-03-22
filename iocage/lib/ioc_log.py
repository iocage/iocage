"""iocage logging module."""

import logging

def getLogger(name):
    logfile = logging.FileHandler('/var/log/some.log')
    logfile.setLevel(logging.DEBUG)
    logfile.setFormatter(logging.Formatter(
        '%(asctime)s %(pathname)s [%(process)d]: %(levelname)s %(message)s'))

    logger = logging.getLogger(name)
    logger.addHandler(logfile)
    return logger


def init(dbg):
    if dbg:
        log_level = logging.DEBUG
    else:
        log_level = logging.WARNING

    logging.basicConfig(filename=log_file, filemode=mode, level=log_level,
                        format='%(message)s')
