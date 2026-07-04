from pathlib import Path
from typing import Any

import pytest
from fakes import FakeCollector, FakeNotifier, FakeRenderer

from wkx_beacon.config import BeaconConfig, ReportConfig, Settings, load_config, resolve
from wkx_beacon.exceptions import ConfigError
from wkx_beacon.plugin import PluginRegistry

REGISTRY = PluginRegistry(
    collectors={"fake-collector": FakeCollector},
    renderers={"fake-renderer": FakeRenderer},
    notifiers={"fake-notifier": FakeNotifier},
)


def report_dict(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": "platform-cost",
        "collector": "fake-collector",
        "renderers": ["fake-renderer"],
        "notifiers": ["fake-notifier"],
        "schedule": "0 7 * * *",
        "timezone": "Pacific/Auckland",
    }
    return base | overrides


def test_load_config_parses_toml(tmp_path: Path) -> None:
    toml = """
[[report]]
name = "platform-cost"
collector = "fake-collector"
renderers = ["fake-renderer"]
notifiers = ["fake-notifier"]
schedule = "0 7 * * *"
timezone = "Pacific/Auckland"

[report.collector_config]
fail = false
"""
    path = tmp_path / "beacon.toml"
    path.write_text(toml)

    config = load_config(path)

    assert config.reports[0].name == "platform-cost"
    assert config.reports[0].collector_config == {"fail": False}


@pytest.mark.parametrize("bad_name", ["Platform Cost", "UPPER", "trailing-", "-leading", "a_b"])
def test_report_name_must_be_a_slug(bad_name: str) -> None:
    with pytest.raises(ValueError, match="slug"):
        ReportConfig.model_validate(report_dict(name=bad_name))


def test_report_schedule_must_be_a_valid_cron_expression() -> None:
    with pytest.raises(ValueError, match="cron expression"):
        ReportConfig.model_validate(report_dict(schedule="99 99 * * *"))


def test_report_schedule_rejects_six_field_cron_apscheduler_cannot_boot() -> None:
    with pytest.raises(ValueError, match="cron expression"):
        ReportConfig.model_validate(report_dict(schedule="0 7 * * * *"))


def test_report_timezone_must_be_a_valid_timezone() -> None:
    with pytest.raises(ValueError, match="timezone"):
        ReportConfig.model_validate(report_dict(timezone="Mars/Olympus"))


def test_duplicate_report_names_are_a_boot_error() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        BeaconConfig.model_validate({"reports": [report_dict(), report_dict()]})


def test_resolve_instantiates_plugins_with_validated_config() -> None:
    config = BeaconConfig.model_validate({"reports": [report_dict()]})

    resolved = resolve(config, REGISTRY)

    assert resolved[0].collector.config.fail is False  # type: ignore[attr-defined]
    assert list(resolved[0].renderers) == ["fake-renderer"]


def test_resolve_rejects_unknown_plugin_names() -> None:
    config = BeaconConfig.model_validate({"reports": [report_dict(collector="nope")]})

    with pytest.raises(ConfigError, match=r"nope.*available.*fake-collector"):
        resolve(config, REGISTRY)


def test_resolve_rejects_unknown_plugin_config_keys() -> None:
    config = BeaconConfig.model_validate(
        {"reports": [report_dict(collector_config={"typo": True})]}
    )

    with pytest.raises(ConfigError, match="typo"):
        resolve(config, REGISTRY)


def test_settings_reads_beacon_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BEACON_DATA_DIR", "/tmp/beacon-data")

    settings = Settings(_env_file=None)

    assert settings.data_dir == Path("/tmp/beacon-data")


def test_settings_base_url_drops_trailing_slash(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path, base_url="http://beacon.test/")

    assert settings.base_url == "http://beacon.test"
