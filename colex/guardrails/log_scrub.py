"""Masks API keys and Slack tokens in log output (brief §4.3; G0-SEC-01).

Call `install()` once at process start. It wraps the log record factory, so every record
from every logger is scrubbed before any handler sees it.

Limit: `record.exc_info` still holds the original exception object. The standard
`logging.Formatter` uses the scrubbed `record.exc_text`; a custom formatter that formats
`exc_info` itself is not covered.
"""
from __future__ import annotations

import logging
import os
import re

MASK = "[REDACTED]"
SECRET_ENV_VARS = ("OPENROUTER_API_KEY", "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN")

_TOKEN = re.compile(r"(xox[a-z]|xapp|sk-or)-[A-Za-z0-9_-]{6,}")
_MIN_ENV_VALUE_LEN = 8
_FORMATTER = logging.Formatter()
_previous_factory = None


def scrub(text: str) -> str:
    """Return `text` with secret env values and token-shaped strings masked."""
    for name in SECRET_ENV_VARS:
        value = os.environ.get(name, "")
        if len(value) >= _MIN_ENV_VALUE_LEN:
            text = text.replace(value, MASK)
    return _TOKEN.sub(MASK, text)


def scrub_record(record: logging.LogRecord) -> logging.LogRecord:
    try:
        message = record.getMessage()
    except Exception:  # bad format string or args: still scrub what we can
        message = f"{record.msg} {record.args!r}"
    record.msg = scrub(message)
    record.args = None
    if record.exc_info and not record.exc_text:
        record.exc_text = _FORMATTER.formatException(record.exc_info)
    if record.exc_text:
        record.exc_text = scrub(record.exc_text)
    if record.stack_info:
        record.stack_info = scrub(record.stack_info)
    return record


class ScrubFilter(logging.Filter):
    """Handler- or logger-level alternative to `install()`."""

    def filter(self, record: logging.LogRecord) -> bool:
        scrub_record(record)
        return True


def install() -> None:
    """Scrub every log record in this process. Safe to call more than once."""
    global _previous_factory
    if _previous_factory is not None:
        return
    previous = logging.getLogRecordFactory()

    def factory(*args, **kwargs):
        return scrub_record(previous(*args, **kwargs))

    _previous_factory = previous
    logging.setLogRecordFactory(factory)


def uninstall() -> None:
    global _previous_factory
    if _previous_factory is not None:
        logging.setLogRecordFactory(_previous_factory)
        _previous_factory = None
