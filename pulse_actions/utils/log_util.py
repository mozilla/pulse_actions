import logging

LOG = None


def setup_logging(logging_level):
    global LOG
    if LOG:
        return LOG
    # Let's use the root logger
    LOG = logging.getLogger()
    LOG.setLevel(logging.DEBUG)

    format = '%(asctime)s %(name)s\t %(levelname)s:\t %(message)s'
    formatter = logging.Formatter(format, datefmt='%H:%M:%S')
    # Handler 1 - Store all INFO messages in a specific file
    # This logging.txt file will *only* show messages for that same day as Heroku
    # dynos restart every day - Use papertrail for more details.
    fh = logging.FileHandler('logging.txt')
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    LOG.addHandler(fh)

    # Handler 2 - Store all DEBUG messages in a specific file
    fh = logging.FileHandler('logging_debug.txt')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    LOG.addHandler(fh)

    # Handler 3 - Output to console (this is the output for Papertrail)
    console = logging.StreamHandler()
    console.setLevel(logging_level)
    formatter = logging.Formatter('%(name)s\t %(levelname)s:\t %(message)s')
    console.setFormatter(formatter)
    LOG.addHandler(console)

    LOG.info("Console output logs %s level messages." % logging.getLevelName(logging_level))

    # Reduce logging for other noisy modules
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("amqp").setLevel(logging.WARNING)
