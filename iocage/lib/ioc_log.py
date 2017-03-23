"""iocage logging module."""

import logging

def getLogger(name):
    log_file = os.environ.get("IOCAGE_ALT_LOGFILE", "/var/log/iocage.log")
    logfile = logging.FileHandler(log_file)
    logfile.setLevel(logging.DEBUG)
    logfile.setFormatter(logging.Formatter(
        '%(asctime)s %(pathname)s [%(process)d]: %(levelname)s %(message)s'))

    logger = logging.getLogger(name)
    logger.addHandler(logfile)
    return logger


def init(log_file, mode, dbg):
    if dbg:
        log_level = logging.DEBUG
    else:
        log_level = logging.WARNING

    logging.basicConfig(filename=log_file, filemode=mode, level=log_level,
                        format='%(message)s')
