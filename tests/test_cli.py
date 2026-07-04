from pathlib import Path

import pytest
from fakes import FakeCollector, FakeNotifier, FakeRenderer
from typer.testing import CliRunner

from wkx_beacon.__main__ import app
from wkx_beacon.bootstrap import bootstrap
from wkx_beacon.config import Settings
from wkx_beacon.plugin import PluginRegistry

runner = CliRunner()

FAKE_TOML = """
[[report]]
name = "fake-report"
collector = "fake-collector"
renderers = ["fake-renderer"]
notifiers = ["fake-notifier"]
schedule = "0 7 * * *"
timezone = "Pacific/Auckland"
"""


def settings_for(tmp_path: Path) -> Settings:
    config = tmp_path / "beacon.toml"
    config.write_text(FAKE_TOML)
    return Settings(_env_file=None, data_dir=tmp_path / "data", config_file=config)


def fake_registry() -> PluginRegistry:
    return PluginRegistry(
        collectors={"fake-collector": FakeCollector},
        renderers={"fake-renderer": FakeRenderer},
        notifiers={"fake-notifier": FakeNotifier},
    )


def test_bootstrap_resolves_reports(tmp_path: Path) -> None:
    context = bootstrap(settings=settings_for(tmp_path), registry=fake_registry())

    assert [r.config.name for r in context.reports] == ["fake-report"]


def test_validate_succeeds_against_the_committed_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BEACON_DATA_DIR", "/tmp/beacon-validate")

    result = runner.invoke(app, ["validate"])

    assert result.exit_code == 0, result.output
    assert "platform-cost" in result.output


def test_run_unknown_report_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BEACON_DATA_DIR", "/tmp/beacon-validate")

    result = runner.invoke(app, ["run", "nope"])

    assert result.exit_code == 1
