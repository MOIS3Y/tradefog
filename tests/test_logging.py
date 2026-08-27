"""Tests for the unified logging configuration."""

from logging import INFO, LogRecord

from tradefog.config.logging import LoggingSettings
from tradefog.logging import UtcFormatter


def test_logging_uses_one_console_handler() -> None:
    logging_config = LoggingSettings().django_logging()

    assert logging_config["disable_existing_loggers"] is False
    assert logging_config["root"] == {
        "handlers": ["console"],
        "level": "INFO",
    }
    assert logging_config["loggers"] == {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "tradefog": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    }


def test_utc_formatter_uses_an_explicit_utc_timestamp() -> None:
    formatter = UtcFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    record = LogRecord(
        name="tradefog.test",
        level=INFO,
        pathname=__file__,
        lineno=1,
        msg="ready",
        args=(),
        exc_info=None,
    )
    record.created = 0

    assert formatter.format(record) == (
        "1970-01-01T00:00:00Z INFO tradefog.test: ready"
    )
