"""Tests for wkx_beacon._logging.configure()."""

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
