"""Configuration: env settings (deployment) and beacon.toml (report wiring).

Built once at the entry point, passed down explicitly. Nothing deeper in the
stack reads the environment.
"""

import logging
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from wkx_beacon.exceptions import ConfigError
from wkx_beacon.plugin import Collector, Notifier, PluginRegistry, Renderer

logger = logging.getLogger(__name__)

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class Settings(BaseSettings):
    """Deployment settings from the environment and .env."""

    model_config = SettingsConfigDict(env_prefix="BEACON_", env_file=".env", extra="forbid")

    data_dir: Path
    base_url: str = "http://localhost:8000"
    config_file: Path = Path("beacon.toml")
    host: str = "0.0.0.0"
    port: int = 8000

    @field_validator("base_url")
    @classmethod
    def base_url_has_no_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")


class ReportConfig(BaseModel):
    """One [[report]] block: the wiring of a report."""

    model_config = {"extra": "forbid"}

    name: str
    collector: str
    renderers: list[str]
    notifiers: list[str]
    schedule: str
    timezone: str
    catch_up: bool = False
    collector_config: dict[str, Any] = {}
    renderer_config: dict[str, dict[str, Any]] = {}
    notifier_config: dict[str, dict[str, Any]] = {}

    @field_validator("name")
    @classmethod
    def name_is_slug(cls, v: str) -> str:
        if not SLUG_RE.fullmatch(v):
            raise ValueError(f"report name {v!r} is not a slug (lowercase, digits, hyphens)")
        return v

    @field_validator("schedule")
    @classmethod
    def schedule_is_valid_cron(cls, v: str) -> str:
        try:
            CronTrigger.from_crontab(v)
        except ValueError as e:
            raise ValueError(f"{v!r} is not a valid cron expression: {e}") from e
        return v

    @field_validator("timezone")
    @classmethod
    def timezone_is_valid(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError, KeyError) as e:
            raise ValueError(f"{v!r} is not a valid timezone") from e
        return v


class BeaconConfig(BaseModel):
    model_config = {"extra": "forbid"}

    reports: list[ReportConfig]

    @model_validator(mode="after")
    def names_are_unique(self) -> BeaconConfig:
        seen: set[str] = set()
        for report in self.reports:
            if report.name in seen:
                raise ValueError(f"duplicate report name {report.name!r}")
            seen.add(report.name)
        return self


@dataclass
class ResolvedReport:
    """A report with its plugins instantiated and their configs validated."""

    config: ReportConfig
    collector: Collector
    renderers: dict[str, Renderer]
    notifiers: dict[str, Notifier]


def load_config(path: Path) -> BeaconConfig:
    """Parse beacon.toml. Raises ConfigError on missing file or bad shape."""
    try:
        raw = tomllib.loads(path.read_text())
    except FileNotFoundError as e:
        raise ConfigError(f"config file not found: {path}") from e
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"config file {path} is not valid TOML: {e}") from e
    try:
        return BeaconConfig.model_validate({"reports": raw.get("report", [])})
    except ValueError as e:
        raise ConfigError(str(e)) from e


def _instantiate(kind: str, name: str, available: dict[str, type], raw: dict[str, Any]) -> Any:
    if name not in available:
        raise ConfigError(
            f"unknown {kind} {name!r}; available: {', '.join(sorted(available)) or 'none'}"
        )
    cls = available[name]
    try:
        config_model = cast(type[Collector] | type[Renderer] | type[Notifier], cls).config_model
        config = config_model.model_validate(raw)
    except ValueError as e:
        raise ConfigError(f"{kind} {name!r} config invalid: {e}") from e
    return cls(config)


def resolve(config: BeaconConfig, registry: PluginRegistry) -> list[ResolvedReport]:
    """Wire every report to instantiated plugins. Fails at boot, not at 07:00."""
    resolved: list[ResolvedReport] = []
    for report in config.reports:
        collector = _instantiate(
            "collector", report.collector, registry.collectors, report.collector_config
        )
        renderers = {
            name: _instantiate(
                "renderer", name, registry.renderers, report.renderer_config.get(name, {})
            )
            for name in report.renderers
        }
        notifiers = {
            name: _instantiate(
                "notifier", name, registry.notifiers, report.notifier_config.get(name, {})
            )
            for name in report.notifiers
        }
        resolved.append(
            ResolvedReport(
                config=report, collector=collector, renderers=renderers, notifiers=notifiers
            )
        )
        logger.info("resolved report %s", report.name)
    return resolved
