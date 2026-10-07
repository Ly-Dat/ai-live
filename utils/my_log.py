# import sys
# from loguru import logger

# from utils.common import Common
# from utils.config import Config


# # Config file path
# config_path = 'config.json'
# common = Common()

# logger.debug("Config file path=" + str(config_path))

# # Instantiate the config class
# config = Config(config_path)

# # Get the current time and generate the log file path
# file_path = "./log/log-" + common.get_bj_time(1) + ".txt"

# # Configuration logger
# def configure_logger(file_path, log_level, max_file_size):
#     level = log_level.upper() if log_level else "INFO"
#     max_size = max_file_size if max_file_size else "1024 MB"

#     # Clear the previoushandlers
#     logger.remove()

#     # Configure console output
#     if level == "INFO":
#         logger.add(sys.stderr, format="{time:YYYY-MM-DD HH:mm:ss.SSS} | <lvl>{level:8}</>| <lvl>{message}</>", colorize=True, level=level)

#     # Configure file output
#     logger.add(file_path, level=level, rotation=max_size)

# # Get the log config
# log_level = config["webui"]["log"].get("log_level", "INFO")
# max_file_size = config["webui"]["log"].get("max_file_size", "1024 MB")

# # Configuration logger
# configure_logger(file_path, log_level, max_file_size)

# # Export logger for use by other modules
# __all__ = ["logger"]


import sys
import logging
from loguru import logger

from utils.common import Common
from utils.config import Config

# Config file path
config_path = 'config.json'
common = Common()

logger.debug("Config file path=" + str(config_path))

# Instantiate the config class
config = Config(config_path)

# Get the current time and generate the log file path
file_path = "./log/log-" + common.get_bj_time(1) + ".txt"

# Configuration logger
def configure_logger(file_path, log_level, max_file_size):
    level = log_level.upper() if log_level else "INFO"
    max_size = max_file_size if max_file_size else "1024 MB"

    # Clear the previoushandlers
    logger.remove()

    # Configure console output
    # logger.add(sys.stderr, format="{time:YYYY-MM-DD HH:mm:ss.SSS} | <lvl>{level:8}</>| <lvl>{message}</>", colorize=True, level=level)
    logger.add(sys.stderr, colorize=True, level=level)


    # Configure file output
    logger.add(file_path, level=level, rotation=max_size)

# Get the log config
log_level = config["webui"]["log"].get("log_level", "INFO")
max_file_size = config["webui"]["log"].get("max_file_size", "1024 MB")

# Configuration logger
configure_logger(file_path, log_level, max_file_size)

# Get the logger of the jieba library and set its level to WARNING
jieba_logger = logging.getLogger("jieba")
jieba_logger.setLevel(logging.WARNING)

# Get the httpx library logger
httpx_logger = logging.getLogger("httpx")
# Set the httpx logger level to WARNING
httpx_logger.setLevel(logging.WARNING)

# Get the logger of a specific library
watchfiles_logger = logging.getLogger("watchfiles")
# Set the log level to WARNING or higher to suppress INFO-level log messages
watchfiles_logger.setLevel(logging.WARNING)

# Get the logger of the werkzeug library
werkzeug_logger = logging.getLogger("werkzeug")
# Set the httpx logger level to WARNING
werkzeug_logger.setLevel(logging.WARNING)

# Combine loguru with the standard logging
class InterceptHandler(logging.Handler):
    def emit(self, record):
        loguru_logger = logger.bind(name=record.name)
        level = logger.level(record.levelname).name
        frame, depth = logging.currentframe(), 2
        while frame is not None and frame.f_globals["__name__"] != __name__:
            frame = frame.f_back
            depth += 1
        loguru_logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

# Add InterceptHandler to jieba logger
jieba_logger.addHandler(InterceptHandler())
# Add InterceptHandler to httpx logger
httpx_logger.addHandler(InterceptHandler())
watchfiles_logger.addHandler(InterceptHandler())
werkzeug_logger.addHandler(InterceptHandler())

# Export logger for use by other modules
__all__ = ["logger"]
