from __future__ import annotations

import logging
import sys
from pathlib import Path

from loguru import logger

from backend.config.settings import get_settings

_LOGGER_CONFIGURED = False


class InterceptHandler(logging.Handler):
    """Redirect standard logging into Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and depth > 0:
            frame = frame.f_back
            depth -= 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def configure_logging() -> None:
    """Configure structured logging for console and file output."""
    global _LOGGER_CONFIGURED
    if _LOGGER_CONFIGURED:
        return

    settings = get_settings()
    log_dir = Path(__file__).resolve().parents[2] / "logs"
    log_dir.mkdir(exist_ok=True)

    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.log_level.upper(),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        enqueue=True,
    )
    logger.add(
        log_dir / "altron.log",
        rotation="10 MB",
        retention="7 days",
        level=settings.log_level.upper(),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        enqueue=True,
    )

    logging.basicConfig(handlers=[InterceptHandler()], level=settings.log_level.upper())
    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = [InterceptHandler()]
        logging_logger.propagate = False

    _LOGGER_CONFIGURED = True


__all__ = ["configure_logging", "InterceptHandler"]
