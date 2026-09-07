"""Centralized Loguru logging configuration and standard library interception."""

import inspect
import logging
import sys
from typing import override

from loguru import logger

from tradefog.config.logging import LoggingSettings


class InterceptHandler(logging.Handler):
    """Intercept standard library logging messages and redirect them to Loguru."""

    @override
    def emit(self, record: logging.LogRecord) -> None:
        """Forward a standard logging record to Loguru."""
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame = inspect.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            if frame.f_back:
                frame = frame.f_back
                depth += 1
            else:
                break

        logger.opt(depth=depth, exception=record.exc_info).log(
            level,
            record.getMessage(),
        )


def setup_logging(settings: LoggingSettings | None = None) -> None:
    """Configure Loguru sinks and attach interception to standard loggers."""
    log_level = settings.level if settings else "INFO"
    diagnose = settings.diagnose if settings else False
    backtrace = settings.backtrace if settings else True

    # Remove default logger configuration
    logger.remove()

    # Add primary terminal stdout sink
    _ = logger.add(
        sys.stdout,
        level=log_level,
        colorize=True,
        diagnose=diagnose,
        backtrace=backtrace,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )

    # Intercept standard library loggers (uvicorn, fastapi, httpx, etc.)
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(log_level)

    for logger_name in (
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "httpx",
    ):
        mod_logger = logging.getLogger(logger_name)
        mod_logger.handlers = [InterceptHandler()]
        mod_logger.propagate = False


__all__ = ["InterceptHandler", "logger", "setup_logging"]
