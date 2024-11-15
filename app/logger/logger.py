import logging
from typing import Dict

import colorlog


class IAHCustomLogger:
    _loggers: Dict[str, logging.Logger] = {}

    @staticmethod
    def setup_logger(name: str) -> logging.Logger:
        if name not in IAHCustomLogger._loggers:
            logger = logging.getLogger(name)

            if not logger.handlers:
                log_colors = {
                    "DEBUG": "black,bg_green",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "bold_red",
                }

                formatter = colorlog.ColoredFormatter(
                    "%(log_color)s APP: %(asctime)s - %(message)s",
                    datefmt="%y-%m-%d %H:%M:%S",
                    reset=True,
                    log_colors=log_colors,
                    secondary_log_colors={},
                    style="%",
                )

                handler = logging.StreamHandler()
                handler.setFormatter(formatter)

                logger.addHandler(handler)
                logger.setLevel(logging.DEBUG)
                logger.propagate = False

            IAHCustomLogger._loggers[name] = logger

        return IAHCustomLogger._loggers[name]


# Create a logger instance
logger = IAHCustomLogger.setup_logger(__name__)
