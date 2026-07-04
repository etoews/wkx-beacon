"""Tests for wkx_beacon._logging.configure()."""

import json
import logging
from collections.abc import Generator

import pytest

from wkx_beacon._logging import configure


@pytest.fixture(autouse=True)
def restore_root_logger() -> Generator[None]:
    """Save and restore the root logger's handlers and level.

    configure() replaces the root logger's handlers outright. pytest's own
    logging plugin also attaches a handler to the root logger, so without
    restoring it here a call to configure() in one test would permanently
    disrupt log capture for the rest of the run.
    """
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    yield
    root.handlers.clear()
    root.handlers.extend(saved_handlers)
    root.setLevel(saved_level)


def test_invalid_log_level_falls_back_to_info_without_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "LOUD")

    configure()

    assert logging.getLogger().level == logging.INFO


def test_invalid_log_level_warns_about_the_bad_value(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "LOUD")

    configure()

    out = capsys.readouterr().out
    assert "LOUD" in out


def test_valid_log_level_is_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "debug")

    configure()

    assert logging.getLogger().level == logging.DEBUG


def test_json_log_format_produces_parseable_json_with_expected_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOG_FORMAT", "json")

    configure()

    formatter = logging.getLogger().handlers[0].formatter
    assert formatter is not None
    record = logging.LogRecord(
        name="wkx_beacon.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )

    payload = json.loads(formatter.format(record))

    assert set(payload) == {"ts", "level", "logger", "msg"}
    assert payload["level"] == "INFO"
    assert payload["logger"] == "wkx_beacon.test"
    assert payload["msg"] == "hello world"


def test_default_dev_log_format_is_not_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOG_FORMAT", raising=False)

    configure()

    formatter = logging.getLogger().handlers[0].formatter
    assert formatter is not None
    record = logging.LogRecord(
        name="wkx_beacon.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )

    formatted = formatter.format(record)

    assert not formatted.startswith("{")
