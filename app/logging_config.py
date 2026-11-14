"""Structured logging configuration for CloudCost Pilot."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

# Sensitive patterns to sanitize from log records
SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(secret|password|access_key|token|auth|credential)['\":\s=]+([^'\"\s,;]+)"),
]


def sanitize_message(message: str) -> str:
    """Mask sensitive patterns such as AWS secret keys or tokens in log strings."""
    sanitized = message
    for pattern in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(r"\1=***REDACTED***", sanitized)
    return sanitized


class JSONLogFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=UTC).isoformat()
        log_payload: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_message(record.getMessage()),
        }

        # Include contextual fields passed in extra
        if hasattr(record, "account_id") and record.account_id:  # type: ignore[attr-defined]
            log_payload["account_id"] = record.account_id  # type: ignore[attr-defined]
        if hasattr(record, "run_id") and record.run_id:  # type: ignore[attr-defined]
            log_payload["run_id"] = record.run_id  # type: ignore[attr-defined]
        if hasattr(record, "granularity") and record.granularity:  # type: ignore[attr-defined]
            log_payload["granularity"] = record.granularity  # type: ignore[attr-defined]

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_payload)


class TextLogFormatter(logging.Formatter):
    """Formats log records as human-readable text."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=UTC).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
        msg = sanitize_message(record.getMessage())
        base = f"[{timestamp}] [{record.levelname:5s}] [{record.name}]: {msg}"
        if record.exc_info:
            base += f"\n{self.formatException(record.exc_info)}"
        return base


def setup_logging(
    level: str = "INFO",
    log_format: str = "json",
) -> None:
    """Configure root logger with the specified level and format.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: 'json' for machine-readable JSON logs or 'text' for CLI output.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to prevent duplicate lines
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    if log_format.lower() == "json":
        console_handler.setFormatter(JSONLogFormatter())
    else:
        console_handler.setFormatter(TextLogFormatter())

    root_logger.addHandler(console_handler)

    # Silence noisy 3rd party loggers by default
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger."""
    return logging.getLogger(name)
