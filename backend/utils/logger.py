"""Application logging configuration."""

import logging
from datetime import datetime
from pathlib import Path

from config import settings

_LOGGER_NAME = "fangcunguard"
_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def setup_logger():
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger
    directory = Path(settings.log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(_FORMAT)
    handlers = (
        logging.FileHandler(directory / f"guardrails_{datetime.now():%Y%m%d}.log", encoding="utf-8"),
        logging.StreamHandler(),
    )
    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, settings.log_level.upper()))
    return logger


def get_logger(name: str = None):
    setup_logger()
    return logging.getLogger(f"{_LOGGER_NAME}.{name}" if name else _LOGGER_NAME)
