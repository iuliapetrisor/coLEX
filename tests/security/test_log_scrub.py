"""Tokens and secret env values never reach log output."""
from __future__ import annotations

import logging

import pytest

from colex.guardrails import log_scrub

# Built at runtime so this file never contains a token-shaped string.
BOT = "xox" + "b-" + "0000000000-FAKEFAKEFAKE"
APP = "xap" + "p-" + "1-FAKEFAKEFAKE-0000"
KEY = "sk-o" + "r-" + "v1-fakefakefakefake"


@pytest.fixture
def installed():
    log_scrub.install()
    yield
    log_scrub.uninstall()


@pytest.mark.parametrize("token", [BOT, APP, KEY])
def test_scrub_masks_tokens_and_keeps_context(token):
    out = log_scrub.scrub(f"posting with {token} to #legal")
    assert token not in out
    assert out == f"posting with {log_scrub.MASK} to #legal"


def test_scrub_masks_secret_env_values_of_any_shape(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "plain.secret/value+123")
    assert log_scrub.scrub("key=plain.secret/value+123") == f"key={log_scrub.MASK}"


def test_scrub_ignores_short_env_values(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "abc")
    assert log_scrub.scrub("abc def") == "abc def"


def test_scrub_leaves_bare_prefix_alone():
    text = "tokens start with " + "xox" + "b-"
    assert log_scrub.scrub(text) == text


def test_installed_factory_scrubs_message_arguments(installed, caplog):
    with caplog.at_level(logging.INFO):
        logging.getLogger("colex.test").info("token %s for %s", BOT, "legal")
    record = caplog.records[-1]
    assert record.getMessage() == f"token {log_scrub.MASK} for legal"


def test_installed_factory_scrubs_exception_text(installed, caplog):
    with caplog.at_level(logging.ERROR):
        try:
            raise ValueError(f"auth failed for {KEY}")
        except ValueError:
            logging.getLogger("colex.test").exception("call failed")
    formatted = logging.Formatter().format(caplog.records[-1])
    assert KEY not in formatted
    assert log_scrub.MASK in formatted


def test_install_is_idempotent_and_uninstall_restores():
    original = logging.getLogRecordFactory()
    log_scrub.install()
    first = logging.getLogRecordFactory()
    log_scrub.install()
    assert logging.getLogRecordFactory() is first
    log_scrub.uninstall()
    assert logging.getLogRecordFactory() is original


def test_filter_scrubs_a_record():
    record = logging.LogRecord("n", logging.INFO, __file__, 1, "t=%s", (APP,), None)
    assert log_scrub.ScrubFilter().filter(record) is True
    assert record.getMessage() == f"t={log_scrub.MASK}"
