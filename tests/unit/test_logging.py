"""Unit tests for structured logging formatters and setup."""

from __future__ import annotations

import json
import logging

from app.logging_config import JSONLogFormatter, TextLogFormatter, setup_logging


def test_json_log_formatter_standard():
    """Verify JSON log formatter generates valid single-line JSON with standard fields."""
    formatter = JSONLogFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message with secret=my_secret_token",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert "my_secret_token" not in parsed["message"]
    assert "REDACTED" in parsed["message"]
    assert "timestamp" in parsed


def test_json_log_formatter_with_extra_context():
    """Verify JSON log formatter includes contextual metadata."""
    formatter = JSONLogFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.ERROR,
        pathname="test.py",
        lineno=20,
        msg="Error occurred during collection",
        args=(),
        exc_info=None,
    )
    record.account_id = "123456789012"  # type: ignore[attr-defined]
    record.run_id = "run-001"  # type: ignore[attr-defined]
    record.granularity = "DAILY"  # type: ignore[attr-defined]

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["account_id"] == "123456789012"
    assert parsed["run_id"] == "run-001"
    assert parsed["granularity"] == "DAILY"


def test_text_log_formatter():
    """Verify text log formatter outputs human-readable format."""
    formatter = TextLogFormatter()
    record = logging.LogRecord(
        name="cli_logger",
        level=logging.WARNING,
        pathname="test.py",
        lineno=10,
        msg="Warning message",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    assert "[WARNING]" in formatted
    assert "[cli_logger]: Warning message" in formatted


def test_setup_logging():
    """Verify setup_logging configures root logger handlers."""
    setup_logging(level="DEBUG", log_format="json")
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) >= 1
    assert isinstance(root.handlers[0].formatter, JSONLogFormatter)

    setup_logging(level="INFO", log_format="text")
    assert isinstance(root.handlers[0].formatter, TextLogFormatter)
