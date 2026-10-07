import logging
import colorlog

def Configure_logger(log_file):
    log_format = '%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s'
    color_format = '%(log_color)s%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s%(reset)s'

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Create a handler
    handler = logging.FileHandler(log_file, encoding='utf-8', mode='a+')

    handlers = [handler]

    # Create a console handler and set colors
    console = colorlog.StreamHandler()
    console.setFormatter(colorlog.ColoredFormatter(
        color_format,
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG':    'cyan',
            'INFO':     'white', # Set the INFO color to white
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'red,bg_white',
        }
    ))
    handlers.append(console)

    logger.handlers = handlers

    formatter = colorlog.ColoredFormatter(
        color_format,
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Add the handler to the logger and set the formatter
    handler.setFormatter(formatter)