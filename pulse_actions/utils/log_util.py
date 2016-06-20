import logging
import os

from tempfile import gettempdir
from uuid import uuid4

LOG = None
FORMATTER = logging.Formatter(
    '%(asctime)s %(name)s\t %(levelname)s:\t %(message)s',
    datefmt='%H:%M:%S'
)
ALL_HANDLERS = {}


def start_logging(log_level=logging.INFO):
    global ALL_HANDLERS

    log_path = os.path.join(gettempdir(), str(uuid4()))
    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(FORMATTER)

    LOG.addHandler(file_handler)
    ALL_HANDLERS[log_path] = file_handler
    return log_path


def end_logging(log_path):
    global ALL_HANDLERS

    LOG.removeHandler(ALL_HANDLERS[log_path])


def setup_logging(logging_level):
    global LOG
    if LOG:
        return LOG

    # Let's use the root logger
    LOG = logging.getLogger()
    # This line helps set the root logger's level independent of other handlers
    LOG.setLevel(logging.DEBUG)

    # Handler - Output to console (this is the output for Papertrail)
    console = logging.StreamHandler()
    console.setLevel(logging_level)
    # No need to track asctime as Papertrail logs times
    formatter = logging.Formatter('%(name)s\t %(message)s')
    console.setFormatter(formatter)
    LOG.addHandler(console)

    LOG.info("Console output logs %s level messages." % logging.getLevelName(logging_level))

    # Reduce logging for other noisy modules
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("amqp").setLevel(logging.WARNING)
    return LOG
