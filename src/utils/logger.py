import logging
import sys
from .settings import GameSettings

"""
================== HOW TO USE LOGGER ==================
Debug: LOGGER.debug("This is a debug message")
Info : LOGGER.info("Game started")
Warn : LOGGER.warning("FPS dropped below 30")
Err  : LOGGER.error("Failed to load texture")
=======================================================
"""

def create_logger() -> logging.Logger:
    logger = logging.getLogger("your_game")
    logger.setLevel(logging.DEBUG if GameSettings.DEBUG else logging.WARNING)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s", 
        datefmt="%H:%M:%S"
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if GameSettings.DEBUG:
        log_file = "log.txt"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
    def error_and_exit(self, msg, *args, **kwargs):
        logging.Logger.error(self, msg, *args, **kwargs)
        sys.exit(1)
        
    logger.error = error_and_exit.__get__(logger, logging.Logger)
    
    return logger

Logger = create_logger()