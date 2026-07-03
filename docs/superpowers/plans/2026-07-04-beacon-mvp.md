# wkx-beacon MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the wkx-beacon MVP: a containerised plugin-framework report generator whose first vertical slice is a daily AWS cost report rendered to a self-contained HTML artefact, served by a read-only htmx viewer, and announced by email via Amazon SES.

**Architecture:** One container, one process. A scheduler fires report pipelines (collect, render, store, notify); plugins discovered through entry points do the platform-, format-, and channel-specific work; a FastAPI + Jinja2 + htmx viewer serves the filesystem store read-only. See `docs/superpowers/specs/2026-07-04-wkx-beacon-design.md`, `CONTEXT.md` (canonical terms), and `docs/adr/0001..0003`.

**Tech Stack:** Python 3.14, uv, FastAPI, uvicorn, Jinja2, APScheduler 3.x, croniter, boto3, pydantic + pydantic-settings, Typer, htmx (vendored), pytest + botocore Stubber, ruff, ty.

## Global Constraints

- Python `>=3.14`; all commands run through `uv run`; deps added with `uv add` / `uv add --dev`, never pip.
- Every function and method in `src/` and `tests/` has a full type signature, including `-> None`. Modern syntax only (`list[int]`, `X | None`).
- `ruff check`, `ruff format --check`, `ty check`, and `pytest` must pass at the end of every task (each task's final verify step runs all four).
- stdlib `logging` with module loggers (`logger = logging.getLogger(__name__)`); `%` formatting; never `print()` in library code; never log secrets or report contents.
- Exceptions: raise `BeaconError` subclasses; translate third-party exceptions at the boundary with `raise X(...) from e`.
- Canonical terms from `CONTEXT.md`: Platform, report type, report, report name, run, published, run status (`ok` / `degraded` / `failed`), artefact (spelled `artifacts/` in code paths and URLs), collector, renderer, notifier, template pack, store, run record, billing day.
- ADR-0002: no authentication anywhere in beacon. ADR-0003: no database; the filesystem store is the only state.
- Money is `Decimal`, never `float`. Billing data is always UTC days and UTC months.
- Prose (docstrings, README, docs) in New Zealand English, no em dashes. Diagrams in Mermaid.
- Git: work on branch `feat/mvp` (created in Task 1 from `feat/design-spec`). Never author on `main`. Commit at the end of every task at minimum.

## File Map

| File | Responsibility |
|---|---|
| `src/wkx_beacon/exceptions.py` | `BeaconError` hierarchy |
| `src/wkx_beacon/_logging.py` | `configure()` for the app entry point |
| `src/wkx_beacon/plugin/contracts.py` | Public API: `ReportData`, `Artefact`, `RunSummary`, `RunStatus`, `Collector`, `Renderer`, `Notifier` |
| `src/wkx_beacon/plugin/discovery.py` | Entry-point discovery into a `PluginRegistry` |
| `src/wkx_beacon/plugin/__init__.py` | Re-exports the public API surface |
| `src/wkx_beacon/config.py` | `Settings` (env), `ReportConfig`/`BeaconConfig` (beacon.toml), resolution against the registry |
| `src/wkx_beacon/store.py` | Filesystem store: run records, artefacts, listing, latest published |
| `src/wkx_beacon/pipeline.py` | `execute()`: collect, render, store, notify with the status model |
| `src/wkx_beacon/scheduler.py` | Cron triggers per report, opt-in catch-up |
| `src/wkx_beacon/web/app.py` | FastAPI app factory, routes, security headers |
| `src/wkx_beacon/web/templates/*.html.j2` | Viewer chrome: base, index, report history, run detail |
| `src/wkx_beacon/web/static/htmx.min.js` | Vendored htmx |
| `src/wkx_beacon/plugins/aws_cost/` | `aws-cost` collector + cost template pack |
| `src/wkx_beacon/plugins/html_renderer.py` | `html` renderer |
| `src/wkx_beacon/plugins/email_ses.py` | `email-ses` notifier |
| `src/wkx_beacon/bootstrap.py` | Assemble settings, registry, config, store, reports |
| `src/wkx_beacon/__main__.py` | Typer CLI: `serve`, `run`, `validate` |
| `tests/fakes.py` | Fake collector/renderer/notifier used across tests |

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`, `.python-version`, `.gitignore`, `.pre-commit-config.yaml`, `src/wkx_beacon/__init__.py`, `src/wkx_beacon/_logging.py`, `src/wkx_beacon/exceptions.py`, `tests/test_exceptions.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `BeaconError`, `ConfigError`, `CollectError`, `RenderError`, `StoreError`, `NotifyError` in `wkx_beacon.exceptions`; `configure() -> None` in `wkx_beacon._logging`.

- [ ] **Step 1: Branch and scaffold**

```bash
cd /Users/etoews/dev/etoews/wkx-beacon
git switch feat/design-spec && git switch -c feat/mvp
uv init --app --name wkx-beacon --python 3.14 .
rm -f main.py
mkdir -p src/wkx_beacon tests
```

- [ ] **Step 2: Write `pyproject.toml`** (replace the generated one entirely)

```toml
[project]
name = "wkx-beacon"
version = "0.1.0"
description = "Reports about the platform beacon runs on: collected, rendered, stored, announced."
readme = "README.md"
requires-python = ">=3.14"
authors = [{ name = "Everett Toews" }]
license = { text = "MIT" }
dependencies = [
    "fastapi>=0.115",
    "uvicorn>=0.34",
    "jinja2>=3.1",
    "apscheduler>=3.10,<4",
    "croniter>=2",
    "boto3>=1.35",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "typer>=0.15",
]

[project.scripts]
beacon = "wkx_beacon.__main__:main"

[project.entry-points."wkx_beacon.collectors"]
aws-cost = "wkx_beacon.plugins.aws_cost:AwsCostCollector"

[project.entry-points."wkx_beacon.renderers"]
html = "wkx_beacon.plugins.html_renderer:HtmlRenderer"

[project.entry-points."wkx_beacon.notifiers"]
email-ses = "wkx_beacon.plugins.email_ses:EmailSesNotifier"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/wkx_beacon"]

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-cov>=5",
    "ruff>=0.8",
    "ty>=0.0.1",
    "httpx>=0.28",
]

[tool.ruff]
line-length = 100
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]
ignore = []

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "D"]

[tool.ruff.format]
quote-style = "double"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers --strict-config"
filterwarnings = ["error"]

[tool.ty.src]
include = ["src"]
```

Note: the three `[project.entry-points]` tables point at classes that do not exist yet; they are created in Tasks 8 to 10. `uv sync` tolerates this (entry points are metadata, only resolved on `.load()`), and Task 12 tests them end to end. `httpx` is a dev dependency because FastAPI's `TestClient` needs it.

- [ ] **Step 3: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.coverage
dist/
build/
*.egg-info/
.env
data/
```

- [ ] **Step 4: Write `src/wkx_beacon/__init__.py`**

```python
"""wkx-beacon: reports about the platform beacon runs on."""

import logging

logging.getLogger("wkx_beacon").addHandler(logging.NullHandler())
```

- [ ] **Step 5: Write `src/wkx_beacon/exceptions.py`**

```python
"""Exception hierarchy. Catch BeaconError for anything raised by beacon."""


class BeaconError(Exception):
    """Base class for all wkx-beacon exceptions."""


class ConfigError(BeaconError):
    """Raised when configuration is missing, malformed, or fails validation at boot."""


class CollectError(BeaconError):
    """Raised when a collector fails to gather platform data."""


class RenderError(BeaconError):
    """Raised when a renderer fails to produce artefacts."""


class StoreError(BeaconError):
    """Raised when the store cannot write or read runs."""


class NotifyError(BeaconError):
    """Raised when a notifier fails to announce a run."""
```

- [ ] **Step 6: Write `src/wkx_beacon/_logging.py`** (copy the PROJECT.md §14d template verbatim; it provides `configure() -> None` reading `LOG_LEVEL` and `LOG_FORMAT` from the environment, JSON to stdout when `LOG_FORMAT=json`)

- [ ] **Step 7: Write the failing test** in `tests/test_exceptions.py`

```python
"""The hierarchy contract: every beacon exception is catchable as BeaconError."""

import pytest

from wkx_beacon.exceptions import (
    BeaconError,
    CollectError,
    ConfigError,
    NotifyError,
    RenderError,
    StoreError,
)


@pytest.mark.parametrize(
    "exc_type", [ConfigError, CollectError, RenderError, StoreError, NotifyError]
)
def test_all_exceptions_are_beacon_errors(exc_type: type[BeaconError]) -> None:
    assert issubclass(exc_type, BeaconError)
```

- [ ] **Step 8: Sync and run everything**

```bash
uv sync
uv run pytest -v                 # expected: 1 passed (5 params)
uv run ruff check --fix && uv run ruff format
uv run ty check                  # expected: clean
```

- [ ] **Step 9: Write `.pre-commit-config.yaml`** (copy PROJECT.md §11 verbatim), then `pre-commit install`.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat: scaffold wkx-beacon project per PROJECT.md conventions"
```

---

### Task 2: Plugin contracts and discovery

**Files:**
- Create: `src/wkx_beacon/plugin/__init__.py`, `src/wkx_beacon/plugin/contracts.py`, `src/wkx_beacon/plugin/discovery.py`, `tests/fakes.py`, `tests/plugin/test_contracts.py`, `tests/plugin/test_discovery.py`

**Interfaces:**
- Consumes: `wkx_beacon.exceptions.ConfigError`.
- Produces (the public plugin API, used by every later task):
  - `RunStatus = Literal["ok", "degraded", "failed"]`
  - `class ReportData(BaseModel)`: fields `report_type: str`, `headline: str`
  - `class Artefact(BaseModel)`: fields `filename: str`, `media_type: str`, `content: bytes`
  - `class RunSummary(BaseModel)`: fields `report_name: str`, `run_id: str`, `status: RunStatus`, `headline: str`, `failed_stage: str | None = None`, `error: str | None = None`, `report_url: str | None = None`
  - `Collector`, `Renderer`, `Notifier` Protocols (shapes below)
  - `class PluginRegistry`: attrs `collectors: dict[str, type]`, `renderers: dict[str, type]`, `notifiers: dict[str, type]`
  - `def discover(entry_points_fn: Callable[[str], Iterable[EntryPointLike]] | None = None) -> PluginRegistry`
  - Group constants `GROUP_COLLECTORS = "wkx_beacon.collectors"`, `GROUP_RENDERERS = "wkx_beacon.renderers"`, `GROUP_NOTIFIERS = "wkx_beacon.notifiers"`

- [ ] **Step 1: Write `src/wkx_beacon/plugin/contracts.py`**

```python
"""The public plugin API. Semver-governed: breaking this module breaks third parties."""

from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel

RunStatus = Literal["ok", "degraded", "failed"]


class ReportData(BaseModel):
    """Base class for collector output.

    report_type identifies the template pack used to render this data.
    headline is the one-line human summary notifiers put in subjects.
    """

    report_type: str
    headline: str


class Artefact(BaseModel):
    """A rendered output of a run. Immutable once written to the store."""

    filename: str
    media_type: str
    content: bytes


class RunSummary(BaseModel):
    """What a notifier sees: never raw platform data."""

    report_name: str
    run_id: str
    status: RunStatus
    headline: str
    failed_stage: str | None = None
    error: str | None = None
    report_url: str | None = None


@runtime_checkable
class Collector(Protocol):
    """Gathers data from a platform for one (report type, platform) pair."""

    name: str
    report_type: str
    platform: str
    config_model: type[BaseModel]

    def collect(self) -> ReportData: ...

    def template_dir(self) -> Path | None: ...


@runtime_checkable
class Renderer(Protocol):
    """Turns report data into artefacts."""

    name: str
    config_model: type[BaseModel]

    def render(self, data: ReportData, template_dir: Path | None) -> list[Artefact]: ...


@runtime_checkable
class Notifier(Protocol):
    """Announces a completed run on a channel."""

    name: str
    config_model: type[BaseModel]

    def notify(self, summary: RunSummary) -> None: ...
```

Convention (documented, checked by the conformance kit in Task 12): a plugin class is instantiated as `cls(config)` where `config` is an instance of its own `config_model`.

- [ ] **Step 2: Write `tests/fakes.py`** (used by many later tasks; keep names exact)

```python
"""Fake plugins for tests. Deliberately minimal, deliberately breakable."""

from pathlib import Path

from pydantic import BaseModel

from wkx_beacon.exceptions import CollectError, NotifyError, RenderError
from wkx_beacon.plugin.contracts import Artefact, ReportData, RunSummary


class FakeConfig(BaseModel):
    model_config = {"extra": "forbid"}

    fail: bool = False


class FakeCollector:
    name = "fake-collector"
    report_type = "fake"
    platform = "fake-platform"
    config_model = FakeConfig

    def __init__(self, config: FakeConfig) -> None:
        self.config = config

    def collect(self) -> ReportData:
        if self.config.fail:
            raise CollectError("fake collector told to fail")
        return ReportData(report_type="fake", headline="all fake, all good")

    def template_dir(self) -> Path | None:
        return None


class FakeRenderer:
    name = "fake-renderer"
    config_model = FakeConfig

    def __init__(self, config: FakeConfig) -> None:
        self.config = config

    def render(self, data: ReportData, template_dir: Path | None) -> list[Artefact]:
        if self.config.fail:
            raise RenderError("fake renderer told to fail")
        html = f"<html><body>{data.headline}</body></html>"
        return [Artefact(filename="report.html", media_type="text/html", content=html.encode())]


class FakeNotifier:
    name = "fake-notifier"
    config_model = FakeConfig

    def __init__(self, config: FakeConfig) -> None:
        self.config = config
        self.received: list[RunSummary] = []

    def notify(self, summary: RunSummary) -> None:
        if self.config.fail:
            raise NotifyError("fake notifier told to fail")
        self.received.append(summary)
```

- [ ] **Step 3: Write the failing discovery test** in `tests/plugin/test_discovery.py`

```python
from collections.abc import Iterable
from types import SimpleNamespace
from typing import Any

import pytest

from wkx_beacon.exceptions import ConfigError
from wkx_beacon.plugin.discovery import (
    GROUP_COLLECTORS,
    GROUP_NOTIFIERS,
    GROUP_RENDERERS,
    discover,
)
from fakes import FakeCollector, FakeNotifier, FakeRenderer


def _entry_points_fn(group: str) -> Iterable[Any]:
    table = {
        GROUP_COLLECTORS: [SimpleNamespace(name="fake-collector", load=lambda: FakeCollector)],
        GROUP_RENDERERS: [SimpleNamespace(name="fake-renderer", load=lambda: FakeRenderer)],
        GROUP_NOTIFIERS: [SimpleNamespace(name="fake-notifier", load=lambda: FakeNotifier)],
    }
    return table[group]


def test_discover_builds_registry_from_entry_points() -> None:
    registry = discover(_entry_points_fn)

    assert registry.collectors == {"fake-collector": FakeCollector}
    assert registry.renderers == {"fake-renderer": FakeRenderer}
    assert registry.notifiers == {"fake-notifier": FakeNotifier}


def test_duplicate_plugin_name_is_a_boot_error() -> None:
    def duplicated(group: str) -> Iterable[Any]:
        if group == GROUP_COLLECTORS:
            return [
                SimpleNamespace(name="fake-collector", load=lambda: FakeCollector),
                SimpleNamespace(name="fake-collector", load=lambda: FakeCollector),
            ]
        return []

    with pytest.raises(ConfigError, match="duplicate"):
        discover(duplicated)
```

- [ ] **Step 4: Run to verify failure**

```bash
uv run pytest tests/plugin/test_discovery.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'wkx_beacon.plugin'`.

- [ ] **Step 5: Write `src/wkx_beacon/plugin/discovery.py`**

```python
"""Entry-point discovery. Built-ins and third-party plugins register the same way."""

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from typing import Any, Protocol

from wkx_beacon.exceptions import ConfigError

logger = logging.getLogger(__name__)

GROUP_COLLECTORS = "wkx_beacon.collectors"
GROUP_RENDERERS = "wkx_beacon.renderers"
GROUP_NOTIFIERS = "wkx_beacon.notifiers"


class EntryPointLike(Protocol):
    name: str

    def load(self) -> type: ...


EntryPointsFn = Callable[[str], Iterable[EntryPointLike]]


@dataclass
class PluginRegistry:
    collectors: dict[str, type] = field(default_factory=dict)
    renderers: dict[str, type] = field(default_factory=dict)
    notifiers: dict[str, type] = field(default_factory=dict)


def _default_entry_points(group: str) -> Iterable[Any]:
    return entry_points(group=group)


def _load_group(group: str, fn: EntryPointsFn) -> dict[str, type]:
    loaded: dict[str, type] = {}
    for ep in fn(group):
        if ep.name in loaded:
            raise ConfigError(f"duplicate plugin name {ep.name!r} in group {group!r}")
        loaded[ep.name] = ep.load()
        logger.debug("discovered plugin %s in %s", ep.name, group)
    return loaded


def discover(entry_points_fn: EntryPointsFn | None = None) -> PluginRegistry:
    """Discover all plugins. Injectable entry_points_fn keeps this testable."""
    fn = entry_points_fn or _default_entry_points
    return PluginRegistry(
        collectors=_load_group(GROUP_COLLECTORS, fn),
        renderers=_load_group(GROUP_RENDERERS, fn),
        notifiers=_load_group(GROUP_NOTIFIERS, fn),
    )
```

- [ ] **Step 6: Write `src/wkx_beacon/plugin/__init__.py`**

```python
"""Public plugin API surface. Import from here, not from submodules."""

from wkx_beacon.plugin.contracts import (
    Artefact,
    Collector,
    Notifier,
    Renderer,
    ReportData,
    RunStatus,
    RunSummary,
)
from wkx_beacon.plugin.discovery import (
    GROUP_COLLECTORS,
    GROUP_NOTIFIERS,
    GROUP_RENDERERS,
    PluginRegistry,
    discover,
)

__all__ = [
    "GROUP_COLLECTORS",
    "GROUP_NOTIFIERS",
    "GROUP_RENDERERS",
    "Artefact",
    "Collector",
    "Notifier",
    "PluginRegistry",
    "Renderer",
    "ReportData",
    "RunStatus",
    "RunSummary",
    "discover",
]
```

- [ ] **Step 7: Write `tests/plugin/test_contracts.py`**

```python
from wkx_beacon.plugin import Collector, Notifier, Renderer
from fakes import FakeCollector, FakeConfig, FakeNotifier, FakeRenderer


def test_fakes_satisfy_the_protocols() -> None:
    assert isinstance(FakeCollector(FakeConfig()), Collector)
    assert isinstance(FakeRenderer(FakeConfig()), Renderer)
    assert isinstance(FakeNotifier(FakeConfig()), Notifier)
```

- [ ] **Step 8: Run tests, verify pass, run full checks**

```bash
uv run pytest tests/plugin -v      # expected: 3 passed
uv run ruff check --fix && uv run ruff format && uv run ty check && uv run pytest
```

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: plugin contracts and entry-point discovery"
```

---

### Task 3: Configuration

**Files:**
- Create: `src/wkx_beacon/config.py`, `tests/test_config.py`, `.env.example`

**Interfaces:**
- Consumes: `PluginRegistry`, Protocols from Task 2; `ConfigError`.
- Produces:
  - `class Settings(BaseSettings)`: `data_dir: Path`, `base_url: str = "http://localhost:8000"`, `config_file: Path = Path("beacon.toml")`, `host: str = "0.0.0.0"`, `port: int = 8000`; env prefix `BEACON_`, reads `.env`, `extra="forbid"`
  - `class ReportConfig(BaseModel)`: `name`, `collector`, `renderers`, `notifiers`, `schedule`, `timezone`, `catch_up: bool = False`, `collector_config: dict[str, Any]`, `renderer_config: dict[str, dict[str, Any]]`, `notifier_config: dict[str, dict[str, Any]]`
  - `class BeaconConfig(BaseModel)`: `reports: list[ReportConfig]`
  - `def load_config(path: Path) -> BeaconConfig`
  - `@dataclass class ResolvedReport`: `config: ReportConfig`, `collector: Collector`, `renderers: dict[str, Renderer]`, `notifiers: dict[str, Notifier]`
  - `def resolve(config: BeaconConfig, registry: PluginRegistry) -> list[ResolvedReport]`

- [ ] **Step 1: Write the failing tests** in `tests/test_config.py`

```python
from pathlib import Path
from typing import Any

import pytest

from wkx_beacon.config import BeaconConfig, ReportConfig, Settings, load_config, resolve
from wkx_beacon.exceptions import ConfigError
from wkx_beacon.plugin import PluginRegistry
from fakes import FakeCollector, FakeNotifier, FakeRenderer

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

    with pytest.raises(ConfigError, match="nope.*available.*fake-collector"):
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
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_config.py -v
```
Expected: FAIL with `ModuleNotFoundError` or `ImportError` on `wkx_beacon.config`.

- [ ] **Step 3: Write `src/wkx_beacon/config.py`**

```python
"""Configuration: env settings (deployment) and beacon.toml (report wiring).

Built once at the entry point, passed down explicitly. Nothing deeper in the
stack reads the environment.
"""

import logging
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


class BeaconConfig(BaseModel):
    model_config = {"extra": "forbid"}

    reports: list[ReportConfig]

    @model_validator(mode="after")
    def names_are_unique(self) -> "BeaconConfig":
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
        config = cls.config_model.model_validate(raw)
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
```

- [ ] **Step 4: Write `.env.example`**

```
# Deployment settings. Copy to .env for local development; production values
# come from the host platform, never from a committed file.
BEACON_DATA_DIR=./data
BEACON_BASE_URL=http://localhost:8000
BEACON_CONFIG_FILE=beacon.toml
```

- [ ] **Step 5: Run tests to verify pass, then full checks**

```bash
uv run pytest tests/test_config.py -v    # expected: 8 passed
uv run ruff check --fix && uv run ruff format && uv run ty check && uv run pytest
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: settings, beacon.toml loading, and plugin resolution"
```

---

### Task 4: Store

**Files:**
- Create: `src/wkx_beacon/store.py`, `tests/test_store.py`

**Interfaces:**
- Consumes: `Artefact`, `RunStatus` from Task 2; `StoreError`.
- Produces:
  - `def new_run_id(now: datetime) -> str` (format `YYYYMMDDTHHMMSSZ`, UTC, sortable)
  - `class StageOutcome(BaseModel)`: `stage: str`, `ok: bool`, `error: str | None = None`, `duration_ms: int = 0`
  - `class RunRecord(BaseModel)`: `report_name: str`, `run_id: str`, `status: RunStatus`, `started_at: datetime`, `finished_at: datetime`, `stages: list[StageOutcome]`, `headline: str`, `artefacts: list[str] = []`; property `published: bool` (`status != "failed"`)
  - `class Store`: `__init__(self, data_dir: Path)`, `write_artefacts(report_name, run_id, artefacts) -> None`, `write_record(record) -> None`, `read_record(report_name, run_id) -> RunRecord | None`, `list_runs(report_name) -> list[RunRecord]` (newest first), `latest_published(report_name) -> RunRecord | None`, `artefact_path(report_name, run_id, filename) -> Path | None` (refuses path traversal)

- [ ] **Step 1: Write the failing tests** in `tests/test_store.py`

```python
from datetime import UTC, datetime
from pathlib import Path

from wkx_beacon.plugin import Artefact
from wkx_beacon.store import RunRecord, StageOutcome, Store, new_run_id

NOW = datetime(2026, 7, 4, 7, 0, 15, tzinfo=UTC)


def record(run_id: str, status: str = "ok") -> RunRecord:
    return RunRecord(
        report_name="platform-cost",
        run_id=run_id,
        status=status,  # type: ignore[arg-type]
        started_at=NOW,
        finished_at=NOW,
        stages=[StageOutcome(stage="collect", ok=True)],
        headline="fine",
        artefacts=["report.html"],
    )


def test_new_run_id_is_utc_and_sortable() -> None:
    assert new_run_id(NOW) == "20260704T070015Z"


def test_round_trip_record_and_artefact(tmp_path: Path) -> None:
    store = Store(tmp_path)
    run_id = new_run_id(NOW)
    artefact = Artefact(filename="report.html", media_type="text/html", content=b"<html/>")

    store.write_artefacts("platform-cost", run_id, [artefact])
    store.write_record(record(run_id))

    read = store.read_record("platform-cost", run_id)
    assert read is not None and read.headline == "fine"
    path = store.artefact_path("platform-cost", run_id, "report.html")
    assert path is not None and path.read_bytes() == b"<html/>"


def test_runs_without_commit_marker_are_ignored(tmp_path: Path) -> None:
    store = Store(tmp_path)
    store.write_artefacts("platform-cost", "20260704T070015Z", [])  # dir exists, no run.json

    assert store.list_runs("platform-cost") == []


def test_latest_published_skips_failed_runs(tmp_path: Path) -> None:
    store = Store(tmp_path)
    store.write_record(record("20260702T070015Z", status="ok"))
    store.write_record(record("20260703T070015Z", status="degraded"))
    store.write_record(record("20260704T070015Z", status="failed"))

    latest = store.latest_published("platform-cost")

    assert latest is not None and latest.run_id == "20260703T070015Z"


def test_artefact_path_refuses_traversal(tmp_path: Path) -> None:
    store = Store(tmp_path)

    assert store.artefact_path("platform-cost", "20260704T070015Z", "../../etc/passwd") is None
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_store.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'wkx_beacon.store'`.

- [ ] **Step 3: Write `src/wkx_beacon/store.py`**

```python
"""Filesystem store (ADR-0003). run.json is written last, as the commit marker."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel

from wkx_beacon.exceptions import StoreError
from wkx_beacon.plugin import Artefact, RunStatus

logger = logging.getLogger(__name__)

RECORD_FILE = "run.json"
ARTEFACTS_DIR = "artifacts"  # spelled this way in code paths and URLs; see CONTEXT.md


def new_run_id(now: datetime) -> str:
    """Sortable, filesystem-safe UTC run identity."""
    return now.strftime("%Y%m%dT%H%M%SZ")


class StageOutcome(BaseModel):
    stage: str
    ok: bool
    error: str | None = None
    duration_ms: int = 0


class RunRecord(BaseModel):
    report_name: str
    run_id: str
    status: RunStatus
    started_at: datetime
    finished_at: datetime
    stages: list[StageOutcome]
    headline: str
    artefacts: list[str] = []

    @property
    def published(self) -> bool:
        """Published means the artefacts made it into the store."""
        return self.status != "failed"


class Store:
    """All state beacon has. One directory per run under each report name."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    def _run_dir(self, report_name: str, run_id: str) -> Path:
        return self.data_dir / "reports" / report_name / "runs" / run_id

    def write_artefacts(
        self, report_name: str, run_id: str, artefacts: Sequence[Artefact]
    ) -> None:
        target = self._run_dir(report_name, run_id) / ARTEFACTS_DIR
        try:
            target.mkdir(parents=True, exist_ok=True)
            for artefact in artefacts:
                (target / artefact.filename).write_bytes(artefact.content)
        except OSError as e:
            raise StoreError(f"cannot write artefacts for {report_name}/{run_id}: {e}") from e

    def write_record(self, record: RunRecord) -> None:
        run_dir = self._run_dir(record.report_name, record.run_id)
        try:
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / RECORD_FILE).write_text(record.model_dump_json(indent=2))
        except OSError as e:
            raise StoreError(f"cannot write run record {record.run_id}: {e}") from e
        logger.info("stored run %s %s status=%s", record.report_name, record.run_id, record.status)

    def read_record(self, report_name: str, run_id: str) -> RunRecord | None:
        path = self._run_dir(report_name, run_id) / RECORD_FILE
        if not path.is_file():
            return None
        return RunRecord.model_validate_json(path.read_text())

    def list_runs(self, report_name: str) -> list[RunRecord]:
        """All committed runs, newest first. Directories without run.json are ignored."""
        runs_dir = self.data_dir / "reports" / report_name / "runs"
        if not runs_dir.is_dir():
            return []
        records = [
            record
            for run_dir in sorted(runs_dir.iterdir(), reverse=True)
            if (record := self.read_record(report_name, run_dir.name)) is not None
        ]
        return records

    def latest_published(self, report_name: str) -> RunRecord | None:
        return next((r for r in self.list_runs(report_name) if r.published), None)

    def artefact_path(self, report_name: str, run_id: str, filename: str) -> Path | None:
        """Resolve an artefact path; refuses anything escaping the artefacts dir."""
        base = (self._run_dir(report_name, run_id) / ARTEFACTS_DIR).resolve()
        candidate = (base / filename).resolve()
        if not candidate.is_relative_to(base) or not candidate.is_file():
            return None
        return candidate
```

- [ ] **Step 4: Run tests to verify pass, then full checks**

```bash
uv run pytest tests/test_store.py -v     # expected: 5 passed
uv run ruff check --fix && uv run ruff format && uv run ty check && uv run pytest
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: filesystem store with run.json commit marker"
```

---

### Task 5: Pipeline

**Files:**
- Create: `src/wkx_beacon/pipeline.py`, `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `ResolvedReport` (Task 3), `Store`, `RunRecord`, `StageOutcome`, `new_run_id` (Task 4), `RunSummary` (Task 2), exceptions.
- Produces: `def execute(report: ResolvedReport, store: Store, base_url: str, now_fn: Callable[[], datetime] | None = None) -> RunRecord`.

Status rules (from the spec and CONTEXT.md):
- collect raises, or every renderer raises, or artefact write raises: status `failed`, nothing published; the run record is still written.
- some renderers fail but at least one artefact is stored: `degraded`.
- any notifier fails: `degraded` at best (a notify failure never unpublishes).
- everything clean: `ok`.
- Notifiers are always called, with a success summary or a failure notice. `report_url` is `{base_url}/reports/{name}/latest` for published runs, `{base_url}/reports/{name}/runs/{run_id}` otherwise.

- [ ] **Step 1: Write the failing tests** in `tests/test_pipeline.py`

```python
from pathlib import Path

from wkx_beacon.config import ReportConfig, ResolvedReport
from wkx_beacon.pipeline import execute
from wkx_beacon.store import Store
from fakes import FakeCollector, FakeConfig, FakeNotifier, FakeRenderer

BASE_URL = "http://beacon.test"


def resolved(
    tmp_path: Path,
    collector_fails: bool = False,
    renderer_fails: bool = False,
    notifier_fails: bool = False,
) -> tuple[ResolvedReport, Store, FakeNotifier]:
    notifier = FakeNotifier(FakeConfig(fail=notifier_fails))
    report = ResolvedReport(
        config=ReportConfig(
            name="platform-cost",
            collector="fake-collector",
            renderers=["fake-renderer"],
            notifiers=["fake-notifier"],
            schedule="0 7 * * *",
            timezone="Pacific/Auckland",
        ),
        collector=FakeCollector(FakeConfig(fail=collector_fails)),
        renderers={"fake-renderer": FakeRenderer(FakeConfig(fail=renderer_fails))},
        notifiers={"fake-notifier": notifier},
    )
    return report, Store(tmp_path), notifier


def test_clean_run_is_ok_and_published(tmp_path: Path) -> None:
    report, store, notifier = resolved(tmp_path)

    record = execute(report, store, BASE_URL)

    assert record.status == "ok"
    assert record.published
    assert record.artefacts == ["report.html"]
    assert store.read_record("platform-cost", record.run_id) is not None
    assert notifier.received[0].report_url == f"{BASE_URL}/reports/platform-cost/latest"


def test_collect_failure_is_failed_but_still_a_run(tmp_path: Path) -> None:
    report, store, notifier = resolved(tmp_path, collector_fails=True)

    record = execute(report, store, BASE_URL)

    assert record.status == "failed"
    assert not record.published
    assert store.read_record("platform-cost", record.run_id) is not None
    summary = notifier.received[0]
    assert summary.failed_stage == "collect"
    assert summary.report_url == f"{BASE_URL}/reports/platform-cost/runs/{record.run_id}"


def test_all_renderers_failing_is_failed(tmp_path: Path) -> None:
    report, store, _ = resolved(tmp_path, renderer_fails=True)

    record = execute(report, store, BASE_URL)

    assert record.status == "failed"


def test_notify_failure_degrades_but_never_unpublishes(tmp_path: Path) -> None:
    report, store, _ = resolved(tmp_path, notifier_fails=True)

    record = execute(report, store, BASE_URL)

    assert record.status == "degraded"
    assert record.published
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_pipeline.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'wkx_beacon.pipeline'`.

- [ ] **Step 3: Write `src/wkx_beacon/pipeline.py`**

```python
"""Run a report end to end. A failed run is still a run."""

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime

from wkx_beacon.config import ResolvedReport
from wkx_beacon.exceptions import BeaconError
from wkx_beacon.plugin import Artefact, ReportData, RunStatus, RunSummary
from wkx_beacon.store import RunRecord, StageOutcome, Store, new_run_id

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


def execute(
    report: ResolvedReport,
    store: Store,
    base_url: str,
    now_fn: Callable[[], datetime] | None = None,
) -> RunRecord:
    """Collect, render, store, notify. The record is written whatever happens."""
    now = now_fn or _utcnow
    name = report.config.name
    started_at = now()
    run_id = new_run_id(started_at)
    stages: list[StageOutcome] = []
    failed_stage: str | None = None
    error: str | None = None
    headline = ""
    artefacts: list[Artefact] = []
    degraded = False

    def run_stage(stage: str, fn: Callable[[], object]) -> object | None:
        nonlocal failed_stage, error
        t0 = time.monotonic()
        try:
            result = fn()
        except BeaconError as e:
            stages.append(
                StageOutcome(
                    stage=stage,
                    ok=False,
                    error=str(e),
                    duration_ms=int((time.monotonic() - t0) * 1000),
                )
            )
            logger.exception("report=%s run_id=%s stage=%s failed", name, run_id, stage)
            if failed_stage is None:
                failed_stage, error = stage, str(e)
            return None
        stages.append(
            StageOutcome(stage=stage, ok=True, duration_ms=int((time.monotonic() - t0) * 1000))
        )
        logger.info("report=%s run_id=%s stage=%s ok", name, run_id, stage)
        return result

    data = run_stage("collect", report.collector.collect)
    if isinstance(data, ReportData):
        headline = data.headline
        template_dir = report.collector.template_dir()
        for renderer_name, renderer in report.renderers.items():
            result = run_stage(
                f"render:{renderer_name}", lambda r=renderer: r.render(data, template_dir)
            )
            if isinstance(result, list):
                artefacts.extend(result)
            else:
                degraded = True

    stored = False
    if artefacts:
        run_stage("store", lambda: store.write_artefacts(name, run_id, artefacts))
        stored = stages[-1].ok  # write_artefacts returns None; the stage outcome is the truth

    if not stored:
        status: RunStatus = "failed"
    elif degraded:
        status = "degraded"
    else:
        status = "ok"
    if not headline:
        headline = f"failed at {failed_stage}" if failed_stage else "no output"

    published = status != "failed"
    report_url = (
        f"{base_url}/reports/{name}/latest"
        if published
        else f"{base_url}/reports/{name}/runs/{run_id}"
    )

    # Notify before finalising the record so notify outcomes are part of it.
    for notifier_name, notifier in report.notifiers.items():
        summary = RunSummary(
            report_name=name,
            run_id=run_id,
            status=status,
            headline=headline,
            failed_stage=failed_stage,
            error=error,
            report_url=report_url,
        )
        run_stage(f"notify:{notifier_name}", lambda n=notifier: n.notify(summary))
        if not stages[-1].ok and status == "ok":
            status = "degraded"

    record = RunRecord(
        report_name=name,
        run_id=run_id,
        status=status,
        started_at=started_at,
        finished_at=now(),
        stages=stages,
        headline=headline,
        artefacts=[a.filename for a in artefacts] if published else [],
    )
    store.write_record(record)
    return record
```

- [ ] **Step 4: Run tests; iterate until the four scenarios pass**

```bash
uv run pytest tests/test_pipeline.py -v     # expected: 4 passed
```
Note the subtlety in the `store` stage: `write_artefacts` returns `None` on success, so success is read from the recorded `StageOutcome`, not the return value. If the tests expose a cleaner structure, refactor while keeping them green.

- [ ] **Step 5: Full checks and commit**

```bash
uv run ruff check --fix && uv run ruff format && uv run ty check && uv run pytest
git add -A
git commit -m "feat: report pipeline with ok/degraded/failed status model"
```

---

### Task 6: Scheduler

**Files:**
- Create: `src/wkx_beacon/scheduler.py`, `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `ResolvedReport`, `Store`, `execute` from earlier tasks.
- Produces:
  - `def needs_catch_up(schedule: str, timezone: str, last_run_started: datetime | None, now: datetime) -> bool` (pure, croniter-based)
  - `def build_scheduler(reports: list[ResolvedReport], store: Store, base_url: str) -> BackgroundScheduler` (one cron job per report, `max_instances=1`, `coalesce=True`; queues an immediate run for reports where `catch_up` is true and `needs_catch_up(...)`)

- [ ] **Step 1: Write the failing tests** in `tests/test_scheduler.py`

```python
from datetime import UTC, datetime

from wkx_beacon.scheduler import needs_catch_up

SCHEDULE = "0 7 * * *"
TZ = "Pacific/Auckland"
# 4 July 2026 09:12 NZST is 3 July 21:12 UTC; the 07:00 NZST fire was missed.
NOW = datetime(2026, 7, 3, 21, 12, tzinfo=UTC)


def test_never_ran_needs_catch_up() -> None:
    assert needs_catch_up(SCHEDULE, TZ, last_run_started=None, now=NOW) is True


def test_missed_fire_needs_catch_up() -> None:
    two_days_ago = datetime(2026, 7, 1, 19, 0, tzinfo=UTC)
    assert needs_catch_up(SCHEDULE, TZ, last_run_started=two_days_ago, now=NOW) is True


def test_recent_run_does_not_need_catch_up() -> None:
    after_last_fire = datetime(2026, 7, 3, 19, 30, tzinfo=UTC)  # 07:30 NZST 4 July
    assert needs_catch_up(SCHEDULE, TZ, last_run_started=after_last_fire, now=NOW) is False
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_scheduler.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'wkx_beacon.scheduler'`.

- [ ] **Step 3: Write `src/wkx_beacon/scheduler.py`**

```python
"""Cron scheduling per report. Catch-up is opt-in and default off."""

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from croniter import croniter

from wkx_beacon.config import ResolvedReport
from wkx_beacon.pipeline import execute
from wkx_beacon.store import Store

logger = logging.getLogger(__name__)


def needs_catch_up(
    schedule: str, timezone: str, last_run_started: datetime | None, now: datetime
) -> bool:
    """True when the last run predates the previous scheduled fire time."""
    if last_run_started is None:
        return True
    local_now = now.astimezone(ZoneInfo(timezone))
    previous_fire = croniter(schedule, local_now).get_prev(datetime)
    return last_run_started.astimezone(ZoneInfo(timezone)) < previous_fire


def build_scheduler(
    reports: list[ResolvedReport], store: Store, base_url: str
) -> BackgroundScheduler:
    """One cron job per report; opt-in catch-up runs queue immediately."""
    scheduler = BackgroundScheduler(timezone=UTC)
    for report in reports:
        config = report.config
        trigger = CronTrigger.from_crontab(config.schedule, timezone=ZoneInfo(config.timezone))
        scheduler.add_job(
            execute,
            trigger=trigger,
            args=(report, store, base_url),
            id=config.name,
            max_instances=1,
            coalesce=True,
        )
        logger.info("scheduled report=%s cron=%r tz=%s", config.name, config.schedule, config.timezone)
        if config.catch_up:
            runs = store.list_runs(config.name)
            last = runs[0].started_at if runs else None
            if needs_catch_up(config.schedule, config.timezone, last, datetime.now(tz=UTC)):
                scheduler.add_job(
                    execute, args=(report, store, base_url), id=f"{config.name}:catch-up"
                )
                logger.info("catch-up run queued for report=%s", config.name)
    return scheduler
```

- [ ] **Step 4: Run tests to verify pass, then full checks**

```bash
uv run pytest tests/test_scheduler.py -v   # expected: 3 passed
uv run ruff check --fix && uv run ruff format && uv run ty check && uv run pytest
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: cron scheduler with opt-in boot catch-up"
```

---

### Task 7: Web viewer

**Files:**
- Create: `src/wkx_beacon/web/__init__.py` (empty), `src/wkx_beacon/web/app.py`, `src/wkx_beacon/web/templates/base.html.j2`, `src/wkx_beacon/web/templates/index.html.j2`, `src/wkx_beacon/web/templates/report.html.j2`, `src/wkx_beacon/web/templates/_runs.html.j2`, `src/wkx_beacon/web/templates/run.html.j2`, `src/wkx_beacon/web/static/htmx.min.js`, `tests/web/test_app.py`

**Interfaces:**
- Consumes: `Store`, `RunRecord` (Task 4); `ReportConfig` (Task 3).
- Produces: `def create_app(store: Store, report_configs: list[ReportConfig], scheduler: Any | None = None) -> FastAPI`. Routes exactly as the spec: `/`, `/reports/{name}`, `/reports/{name}/latest`, `/reports/{name}/runs/{run_id}`, `/reports/{name}/runs/{run_id}/artifacts/{filename}`, `/healthz`, plus the htmx fragment `/reports/{name}/fragments/runs?page=N` and `/static/htmx.min.js`.

- [ ] **Step 1: Vendor htmx** (pin the version; no CDN at runtime per the spec)

```bash
mkdir -p src/wkx_beacon/web/static
curl -sSL https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js -o src/wkx_beacon/web/static/htmx.min.js
```

- [ ] **Step 2: Write the failing tests** in `tests/web/test_app.py`

```python
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from wkx_beacon.config import ReportConfig
from wkx_beacon.plugin import Artefact
from wkx_beacon.store import RunRecord, StageOutcome, Store, new_run_id
from wkx_beacon.web.app import create_app

NOW = datetime(2026, 7, 4, 7, 0, 15, tzinfo=UTC)
CONFIG = ReportConfig(
    name="platform-cost",
    collector="aws-cost",
    renderers=["html"],
    notifiers=["email-ses"],
    schedule="0 7 * * *",
    timezone="Pacific/Auckland",
)


def seeded_client(tmp_path: Path) -> tuple[TestClient, str]:
    store = Store(tmp_path)
    run_id = new_run_id(NOW)
    store.write_artefacts(
        "platform-cost",
        run_id,
        [Artefact(filename="report.html", media_type="text/html", content=b"<html>spend</html>")],
    )
    store.write_record(
        RunRecord(
            report_name="platform-cost",
            run_id=run_id,
            status="ok",
            started_at=NOW,
            finished_at=NOW,
            stages=[StageOutcome(stage="collect", ok=True)],
            headline="$4.65 MTD",
            artefacts=["report.html"],
        )
    )
    return TestClient(create_app(store, [CONFIG])), run_id


def test_index_lists_reports_with_headline(tmp_path: Path) -> None:
    client, _ = seeded_client(tmp_path)

    response = client.get("/")

    assert response.status_code == 200
    assert "platform-cost" in response.text
    assert "$4.65 MTD" in response.text


def test_latest_redirects_to_latest_published_run(tmp_path: Path) -> None:
    client, run_id = seeded_client(tmp_path)

    response = client.get("/reports/platform-cost/latest", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == f"/reports/platform-cost/runs/{run_id}"


def test_artefact_is_served_raw(tmp_path: Path) -> None:
    client, run_id = seeded_client(tmp_path)

    response = client.get(f"/reports/platform-cost/runs/{run_id}/artifacts/report.html")

    assert response.status_code == 200
    assert response.text == "<html>spend</html>"


def test_unknown_report_is_404_and_traversal_is_404(tmp_path: Path) -> None:
    client, run_id = seeded_client(tmp_path)

    assert client.get("/reports/nope").status_code == 404
    bad = client.get(f"/reports/platform-cost/runs/{run_id}/artifacts/..%2Frun.json")
    assert bad.status_code == 404


def test_security_headers_are_set(tmp_path: Path) -> None:
    client, _ = seeded_client(tmp_path)

    response = client.get("/")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_healthz(tmp_path: Path) -> None:
    client, _ = seeded_client(tmp_path)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

- [ ] **Step 3: Run to verify failure**

```bash
uv run pytest tests/web/test_app.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'wkx_beacon.web'`.

- [ ] **Step 4: Write `src/wkx_beacon/web/app.py`**

```python
"""Read-only htmx viewer over the store. No authentication by design (ADR-0002)."""

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from wkx_beacon.config import ReportConfig
from wkx_beacon.store import Store

logger = logging.getLogger(__name__)

PAGE_SIZE = 20
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def create_app(
    store: Store, report_configs: list[ReportConfig], scheduler: Any | None = None
) -> FastAPI:
    app = FastAPI(title="wkx-beacon", docs_url=None, redoc_url=None, openapi_url=None)
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    configured = {c.name: c for c in report_configs}

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Any) -> Response:
        response: Response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        return response

    def _known(name: str) -> ReportConfig:
        if name not in configured:
            raise HTTPException(status_code=404)
        return configured[name]

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        if scheduler is not None and not scheduler.running:
            raise HTTPException(status_code=503, detail="scheduler not running")
        probe = store.data_dir / ".healthz"
        try:
            probe.parent.mkdir(parents=True, exist_ok=True)
            probe.write_text("ok")
        except OSError as e:
            raise HTTPException(status_code=503, detail="data dir not writable") from e
        return {"status": "ok"}

    @app.get("/")
    def index(request: Request) -> Response:
        rows = [
            {"config": config, "latest": runs[0] if (runs := store.list_runs(name)) else None}
            for name, config in configured.items()
        ]
        return templates.TemplateResponse(request, "index.html.j2", {"rows": rows})

    @app.get("/reports/{name}")
    def report(request: Request, name: str, page: int = 1) -> Response:
        config = _known(name)
        runs = store.list_runs(name)
        start = (page - 1) * PAGE_SIZE
        context = {
            "config": config,
            "runs": runs[start : start + PAGE_SIZE],
            "page": page,
            "has_more": len(runs) > start + PAGE_SIZE,
        }
        return templates.TemplateResponse(request, "report.html.j2", context)

    @app.get("/reports/{name}/fragments/runs")
    def runs_fragment(request: Request, name: str, page: int = 1) -> Response:
        config = _known(name)
        runs = store.list_runs(name)
        start = (page - 1) * PAGE_SIZE
        context = {
            "config": config,
            "runs": runs[start : start + PAGE_SIZE],
            "page": page,
            "has_more": len(runs) > start + PAGE_SIZE,
        }
        return templates.TemplateResponse(request, "_runs.html.j2", context)

    @app.get("/reports/{name}/latest")
    def latest(name: str) -> RedirectResponse:
        _known(name)
        record = store.latest_published(name)
        if record is None:
            raise HTTPException(status_code=404, detail="no published runs yet")
        return RedirectResponse(f"/reports/{name}/runs/{record.run_id}")

    @app.get("/reports/{name}/runs/{run_id}")
    def run_detail(request: Request, name: str, run_id: str) -> Response:
        _known(name)
        record = store.read_record(name, run_id)
        if record is None:
            raise HTTPException(status_code=404)
        return templates.TemplateResponse(request, "run.html.j2", {"record": record})

    @app.get("/reports/{name}/runs/{run_id}/artifacts/{filename}")
    def artefact(name: str, run_id: str, filename: str) -> FileResponse:
        _known(name)
        path = store.artefact_path(name, run_id, filename)
        if path is None:
            raise HTTPException(status_code=404)
        return FileResponse(path)

    return app
```

- [ ] **Step 5: Write the viewer templates**

`base.html.j2`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}beacon{% endblock %}</title>
  <script src="/static/htmx.min.js" defer></script>
  <style>
    :root { --ink: #23262c; --muted: #6b7076; --line: #ddd; --amber: #b97a0a; }
    body { margin: 0 auto; max-width: 900px; padding: 24px; color: var(--ink);
           font-family: system-ui, sans-serif; }
    a { color: var(--amber); }
    header { display: flex; gap: 8px; align-items: center; border-bottom: 1px solid var(--line);
             padding-bottom: 12px; margin-bottom: 20px; }
    header .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--amber); }
    header a { font-weight: 600; text-decoration: none; color: var(--ink); }
    table { border-collapse: collapse; width: 100%; }
    td, th { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); }
    .status-ok { color: #0a7a0a; } .status-degraded { color: #b97a0a; } .status-failed { color: #c0392b; }
    .muted { color: var(--muted); font-size: 0.9em; }
    iframe { width: 100%; height: 80vh; border: 1px solid var(--line); }
  </style>
</head>
<body>
  <header><span class="dot"></span><a href="/">beacon</a></header>
  {% block content %}{% endblock %}
</body>
</html>
```

`index.html.j2`:

```html
{% extends "base.html.j2" %}
{% block content %}
<table>
  <tr><th>Report</th><th>Latest</th><th>Status</th></tr>
  {% for row in rows %}
  <tr>
    <td><a href="/reports/{{ row.config.name }}">{{ row.config.name }}</a>
        <div class="muted">{{ row.config.schedule }} · {{ row.config.timezone }}</div></td>
    <td>{{ row.latest.headline if row.latest else "no runs yet" }}</td>
    <td>{% if row.latest %}<span class="status-{{ row.latest.status }}">{{ row.latest.status }}</span>
        {% else %}<span class="muted">-</span>{% endif %}</td>
  </tr>
  {% endfor %}
</table>
{% endblock %}
```

`report.html.j2`:

```html
{% extends "base.html.j2" %}
{% block title %}{{ config.name }} · beacon{% endblock %}
{% block content %}
<h1>{{ config.name }}</h1>
<p class="muted">{{ config.collector }} → {{ config.renderers | join(", ") }} → {{ config.notifiers | join(", ") }}</p>
<table id="runs">{% include "_runs.html.j2" %}</table>
{% endblock %}
```

`_runs.html.j2` (the htmx fragment):

```html
{% for run in runs %}
<tr>
  <td><a href="/reports/{{ config.name }}/runs/{{ run.run_id }}">{{ run.run_id }}</a></td>
  <td>{{ run.headline }}</td>
  <td><span class="status-{{ run.status }}">{{ run.status }}</span></td>
</tr>
{% endfor %}
{% if has_more %}
<tr id="more-row">
  <td colspan="3"><a href="#" hx-get="/reports/{{ config.name }}/fragments/runs?page={{ page + 1 }}"
      hx-target="#more-row" hx-swap="outerHTML">older runs</a></td>
</tr>
{% endif %}
```

`run.html.j2`:

```html
{% extends "base.html.j2" %}
{% block title %}{{ record.run_id }} · beacon{% endblock %}
{% block content %}
<h1>{{ record.report_name }} · {{ record.run_id }}</h1>
<p><span class="status-{{ record.status }}">{{ record.status }}</span> · {{ record.headline }}</p>
<p class="muted">{% for stage in record.stages %}{{ stage.stage }} {{ "ok" if stage.ok else "FAILED" }} ({{ stage.duration_ms }}ms){{ " · " if not loop.last }}{% endfor %}</p>
{% for filename in record.artefacts %}
<iframe src="/reports/{{ record.report_name }}/runs/{{ record.run_id }}/artifacts/{{ filename }}" title="{{ filename }}"></iframe>
{% endfor %}
{% endblock %}
```

- [ ] **Step 6: Run tests to verify pass, then full checks**

```bash
uv run pytest tests/web -v          # expected: 6 passed
uv run ruff check --fix && uv run ruff format && uv run ty check && uv run pytest
```

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: read-only htmx viewer over the store"
```

---

### Task 8: aws-cost collector

**Files:**
- Create: `src/wkx_beacon/plugins/__init__.py` (empty), `src/wkx_beacon/plugins/aws_cost/__init__.py`, `src/wkx_beacon/plugins/aws_cost/collector.py`, `tests/plugins/test_aws_cost.py`

**Interfaces:**
- Consumes: `ReportData`, `CollectError`.
- Produces (consumed by the cost template pack in Task 9):
  - `class AwsCostConfig(BaseModel)`: `budget: Decimal`, `budget_currency: str = "USD"`, `display: Literal["usd", "local-first"] = "usd"`, `fx_usd_to_local: Decimal | None = None`, `day_display: Literal["utc", "local-first"] = "utc"`, `timezone: str = "UTC"`, `group_by_tags: tuple[str, str] = ("Service", "Env")`; validator: `display="local-first"` or non-USD `budget_currency` requires `fx_usd_to_local`
  - `class DailyCost(BaseModel)`: `day: date` (UTC billing day), `label: str` (display label per `day_display`), `usd: Decimal`
  - `class TagCost(BaseModel)`: `key: str` (tag value or `"untagged"`), `usd: Decimal`
  - `class CostReportData(ReportData)`: `generated_at: datetime`, `billing_month: str`, `mtd_usd: Decimal`, `latest_day: date | None`, `latest_day_usd: Decimal`, `projected_usd: Decimal | None`, `budget: Decimal`, `budget_currency: str`, `display: str`, `fx_usd_to_local: Decimal | None`, `day_display: str`, `timezone: str`, `daily: list[DailyCost]`, `by_service: list[TagCost]`, `by_env: list[TagCost]`
  - `class AwsCostCollector`: `name = "aws-cost"`, `report_type = "cost"`, `platform = "aws"`, `config_model = AwsCostConfig`; `__init__(self, config: AwsCostConfig, ce_client: Any | None = None)` (boto3 Cost Explorer client created lazily in `collect()` when not injected); `collect() -> CostReportData`; `template_dir() -> Path`

Behaviour (from the spec §8 and the grill):
- One `GetCostAndUsage` call: `TimePeriod` start = the earlier of (first day of the current UTC month, today minus 30 days), end = today (UTC, exclusive, so only complete billing days); `Granularity="DAILY"`; `Metrics=["UnblendedCost"]`; `GroupBy` two TAG keys from config.
- `latest_day` = the most recent complete billing day (yesterday, UTC); `mtd_usd` = sum of current-UTC-month days; `projected_usd` = `mtd_usd / complete_days_in_month * days_in_month`, `None` when no complete day yet.
- Untagged group keys come back as `"Service$"` (empty after `$`); fold into `key="untagged"`.
- Day labels: `day_display="utc"` uses ISO date; `"local-first"` converts the billing day's midpoint (12:00 UTC) to the configured timezone and uses that date (the local-majority date).
- Headline respects currency display, for example `$7.63 NZD MTD, projected $78.79 of $50.00 NZD` (local-first) or `$4.65 USD MTD, ...` (usd).
- Boundary translation: `botocore.exceptions.BotoCoreError`/`ClientError` become `CollectError` with `raise ... from e`.

- [ ] **Step 1: Write the failing tests** in `tests/plugins/test_aws_cost.py`

```python
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import boto3
import pytest
from botocore.stub import Stubber

from wkx_beacon.exceptions import CollectError
from wkx_beacon.plugins.aws_cost import AwsCostCollector, AwsCostConfig

NOW = datetime(2026, 7, 4, 19, 0, tzinfo=UTC)  # 07:00 NZST on 5 July is 19:00 UTC on 4 July


def ce_response() -> dict[str, Any]:
    def day(start: str, end: str, groups: list[tuple[str, str, str]]) -> dict[str, Any]:
        return {
            "TimePeriod": {"Start": start, "End": end},
            "Groups": [
                {
                    "Keys": [f"Service${service}", f"Env${env}"],
                    "Metrics": {"UnblendedCost": {"Amount": amount, "Unit": "USD"}},
                }
                for service, env, amount in groups
            ],
            "Total": {},
            "Estimated": True,
        }

    return {
        "ResultsByTime": [
            day("2026-07-01", "2026-07-02", [("beacon", "prod", "1.00"), ("", "", "0.50")]),
            day("2026-07-02", "2026-07-03", [("beacon", "prod", "1.55")]),
            day("2026-07-03", "2026-07-04", [("caddy", "prod", "1.58")]),
        ],
        "DimensionValueAttributes": [],
    }


def collector(config: AwsCostConfig) -> tuple[AwsCostCollector, Stubber]:
    client = boto3.client("ce", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="x")
    stubber = Stubber(client)
    stubber.add_response("get_cost_and_usage", ce_response())
    return AwsCostCollector(config, ce_client=client), stubber


def test_collect_parses_totals_and_breakdowns() -> None:
    config = AwsCostConfig(budget=Decimal("30"))
    col, stubber = collector(config)

    with stubber:
        data = col.collect(now_fn=lambda: NOW)

    assert data.mtd_usd == Decimal("4.63")
    assert data.latest_day == date(2026, 7, 3)
    assert data.latest_day_usd == Decimal("1.58")
    # 3 complete days of 31: 4.63 / 3 * 31
    assert data.projected_usd == Decimal("47.84")
    assert {t.key: t.usd for t in data.by_service} == {
        "beacon": Decimal("2.55"),
        "caddy": Decimal("1.58"),
        "untagged": Decimal("0.50"),
    }


def test_local_first_day_labels_shift_to_majority_date() -> None:
    config = AwsCostConfig(
        budget=Decimal("50"),
        budget_currency="NZD",
        display="local-first",
        fx_usd_to_local=Decimal("1.64"),
        day_display="local-first",
        timezone="Pacific/Auckland",
    )
    col, stubber = collector(config)

    with stubber:
        data = col.collect(now_fn=lambda: NOW)

    assert data.daily[0].day == date(2026, 7, 1)
    assert data.daily[0].label == "2026-07-02"  # NZ majority date of UTC 1 July
    assert "NZD" in data.headline


def test_local_first_requires_fx_rate() -> None:
    with pytest.raises(ValueError, match="fx_usd_to_local"):
        AwsCostConfig(budget=Decimal("50"), display="local-first")


def test_client_errors_become_collect_errors() -> None:
    config = AwsCostConfig(budget=Decimal("30"))
    col, stubber = collector(config)
    stubber.add_client_error("get_cost_and_usage", "ThrottlingException")

    with stubber, pytest.raises(CollectError):
        col.collect(now_fn=lambda: NOW)
        col.collect(now_fn=lambda: NOW)  # second call hits the stubbed error
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/plugins/test_aws_cost.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'wkx_beacon.plugins.aws_cost'`.

- [ ] **Step 3: Write `src/wkx_beacon/plugins/aws_cost/collector.py`**

```python
"""aws-cost collector: one Cost Explorer call per run, UTC billing days."""

import calendar
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, model_validator

from wkx_beacon.exceptions import CollectError
from wkx_beacon.plugin import ReportData

logger = logging.getLogger(__name__)

CENTS = Decimal("0.01")


class AwsCostConfig(BaseModel):
    model_config = {"extra": "forbid"}

    budget: Decimal
    budget_currency: str = "USD"
    display: Literal["usd", "local-first"] = "usd"
    fx_usd_to_local: Decimal | None = None
    day_display: Literal["utc", "local-first"] = "utc"
    timezone: str = "UTC"
    group_by_tags: tuple[str, str] = ("Service", "Env")

    @model_validator(mode="after")
    def fx_required_for_local(self) -> "AwsCostConfig":
        needs_fx = self.display == "local-first" or self.budget_currency != "USD"
        if needs_fx and self.fx_usd_to_local is None:
            raise ValueError("fx_usd_to_local is required for local-first display or a non-USD budget")
        return self


class DailyCost(BaseModel):
    day: date
    label: str
    usd: Decimal


class TagCost(BaseModel):
    key: str
    usd: Decimal


class CostReportData(ReportData):
    generated_at: datetime
    billing_month: str
    mtd_usd: Decimal
    latest_day: date | None
    latest_day_usd: Decimal
    projected_usd: Decimal | None
    budget: Decimal
    budget_currency: str
    display: str
    fx_usd_to_local: Decimal | None
    day_display: str
    timezone: str
    daily: list[DailyCost]
    by_service: list[TagCost]
    by_env: list[TagCost]


def _label(day: date, day_display: str, timezone: str) -> str:
    if day_display == "utc":
        return day.isoformat()
    midpoint = datetime.combine(day, time(12, 0), tzinfo=UTC)
    return midpoint.astimezone(ZoneInfo(timezone)).date().isoformat()


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


class AwsCostCollector:
    """Collects the account's spend, grouped by cost-allocation tags."""

    name = "aws-cost"
    report_type = "cost"
    platform = "aws"
    config_model = AwsCostConfig

    def __init__(self, config: AwsCostConfig, ce_client: Any | None = None) -> None:
        self.config = config
        self._ce_client = ce_client

    def template_dir(self) -> Path:
        return Path(__file__).parent / "templates"

    def _client(self) -> Any:
        if self._ce_client is None:
            import boto3

            # Cost Explorer is a global service homed in us-east-1.
            self._ce_client = boto3.client("ce", region_name="us-east-1")
        return self._ce_client

    def collect(self, now_fn: Callable[[], datetime] | None = None) -> CostReportData:
        now = (now_fn or (lambda: datetime.now(tz=UTC)))()
        today = now.date()
        month_start = today.replace(day=1)
        start = min(month_start, today - timedelta(days=30))
        tag_service, tag_env = self.config.group_by_tags

        try:
            response = self._client().get_cost_and_usage(
                TimePeriod={"Start": start.isoformat(), "End": today.isoformat()},
                Granularity="DAILY",
                Metrics=["UnblendedCost"],
                GroupBy=[
                    {"Type": "TAG", "Key": tag_service},
                    {"Type": "TAG", "Key": tag_env},
                ],
            )
        except Exception as e:  # noqa: BLE001 - boundary translation
            raise CollectError(f"Cost Explorer query failed: {e}") from e

        daily: list[DailyCost] = []
        by_service: dict[str, Decimal] = {}
        by_env: dict[str, Decimal] = {}
        mtd = Decimal("0")
        for bucket in response["ResultsByTime"]:
            day = date.fromisoformat(bucket["TimePeriod"]["Start"])
            day_total = Decimal("0")
            for group in bucket["Groups"]:
                amount = Decimal(group["Metrics"]["UnblendedCost"]["Amount"])
                service = group["Keys"][0].split("$", 1)[1] or "untagged"
                env = group["Keys"][1].split("$", 1)[1] or "untagged"
                day_total += amount
                if day >= month_start:
                    by_service[service] = by_service.get(service, Decimal("0")) + amount
                    by_env[env] = by_env.get(env, Decimal("0")) + amount
            daily.append(
                DailyCost(
                    day=day,
                    label=_label(day, self.config.day_display, self.config.timezone),
                    usd=_money(day_total),
                )
            )
            if day >= month_start:
                mtd += day_total

        mtd = _money(mtd)
        complete_days = (today - month_start).days
        days_in_month = calendar.monthrange(today.year, today.month)[1]
        projected = (
            _money(mtd / complete_days * days_in_month) if complete_days > 0 else None
        )
        latest = daily[-1] if daily else None

        headline = self._headline(mtd, projected)
        logger.info(
            "collected cost report: mtd_usd=%s projected_usd=%s complete_days=%d",
            mtd,
            projected,
            complete_days,
        )
        return CostReportData(
            report_type="cost",
            headline=headline,
            generated_at=now,
            billing_month=f"{calendar.month_name[today.month]} {today.year}",
            mtd_usd=mtd,
            latest_day=latest.day if latest else None,
            latest_day_usd=latest.usd if latest else Decimal("0"),
            projected_usd=projected,
            budget=self.config.budget,
            budget_currency=self.config.budget_currency,
            display=self.config.display,
            fx_usd_to_local=self.config.fx_usd_to_local,
            day_display=self.config.day_display,
            timezone=self.config.timezone,
            daily=daily,
            by_service=sorted(
                (TagCost(key=k, usd=_money(v)) for k, v in by_service.items()),
                key=lambda t: t.usd,
                reverse=True,
            ),
            by_env=sorted(
                (TagCost(key=k, usd=_money(v)) for k, v in by_env.items()),
                key=lambda t: t.usd,
                reverse=True,
            ),
        )

    def _headline(self, mtd_usd: Decimal, projected_usd: Decimal | None) -> str:
        if self.config.display == "local-first" and self.config.fx_usd_to_local is not None:
            fx = self.config.fx_usd_to_local
            currency = self.config.budget_currency
            mtd, projected = _money(mtd_usd * fx), None
            if projected_usd is not None:
                projected = _money(projected_usd * fx)
        else:
            currency = "USD"
            mtd, projected = mtd_usd, projected_usd
        if projected is None:
            return f"${mtd} {currency} MTD, no complete billing day yet"
        return f"${mtd} {currency} MTD, projected ${projected} of ${self.config.budget} {currency}"
```

Note: `collect(now_fn=...)` keeps the Protocol satisfied (extra keyword with a default) while making time injectable for tests.

- [ ] **Step 4: Write `src/wkx_beacon/plugins/aws_cost/__init__.py`**

```python
from wkx_beacon.plugins.aws_cost.collector import (
    AwsCostCollector,
    AwsCostConfig,
    CostReportData,
    DailyCost,
    TagCost,
)

__all__ = ["AwsCostCollector", "AwsCostConfig", "CostReportData", "DailyCost", "TagCost"]
```

- [ ] **Step 5: Run tests; check the maths by hand**

```bash
uv run pytest tests/plugins/test_aws_cost.py -v    # expected: 4 passed
```
`mtd = 1.50 + 1.55 + 1.58 = 4.63`; `projected = 4.63 / 3 * 31 = 47.8433... -> 47.84`.

- [ ] **Step 6: Full checks and commit**

```bash
uv run ruff check --fix && uv run ruff format && uv run ty check && uv run pytest
git add -A
git commit -m "feat: aws-cost collector with UTC billing days and display config"
```

---

### Task 9: html renderer and the cost template pack

**Files:**
- Create: `src/wkx_beacon/plugins/html_renderer.py`, `src/wkx_beacon/plugins/aws_cost/templates/cost.html.j2`, `tests/plugins/test_html_renderer.py`

**Interfaces:**
- Consumes: `ReportData`, `Artefact`, `RenderError`; `CostReportData` fixture shape from Task 8.
- Produces: `class HtmlRenderer`: `name = "html"`, `config_model = HtmlRendererConfig` (empty, `extra="forbid"`); `render(data, template_dir) -> list[Artefact]` producing one `report.html` from `{report_type}.html.j2`.

- [ ] **Step 1: Write the failing tests** in `tests/plugins/test_html_renderer.py`

```python
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from wkx_beacon.exceptions import RenderError
from wkx_beacon.plugins.aws_cost import AwsCostCollector, AwsCostConfig, CostReportData, DailyCost, TagCost
from wkx_beacon.plugins.html_renderer import HtmlRenderer, HtmlRendererConfig


def fixture_data() -> CostReportData:
    return CostReportData(
        report_type="cost",
        headline="$7.59 NZD MTD, projected $78.46 of $50.00 NZD",
        generated_at=datetime(2026, 7, 4, 19, 0, tzinfo=UTC),
        billing_month="July 2026",
        mtd_usd=Decimal("4.63"),
        latest_day=date(2026, 7, 3),
        latest_day_usd=Decimal("1.58"),
        projected_usd=Decimal("47.84"),
        budget=Decimal("50.00"),
        budget_currency="NZD",
        display="local-first",
        fx_usd_to_local=Decimal("1.64"),
        day_display="local-first",
        timezone="Pacific/Auckland",
        daily=[
            DailyCost(day=date(2026, 7, 1), label="2026-07-02", usd=Decimal("1.50")),
            DailyCost(day=date(2026, 7, 2), label="2026-07-03", usd=Decimal("1.55")),
            DailyCost(day=date(2026, 7, 3), label="2026-07-04", usd=Decimal("1.58")),
        ],
        by_service=[TagCost(key="beacon", usd=Decimal("2.55")), TagCost(key="untagged", usd=Decimal("0.50"))],
        by_env=[TagCost(key="prod", usd=Decimal("4.13"))],
    )


def test_renders_self_contained_artefact() -> None:
    renderer = HtmlRenderer(HtmlRendererConfig())
    template_dir = AwsCostCollector(AwsCostConfig(budget=Decimal("30"))).template_dir()

    artefacts = renderer.render(fixture_data(), template_dir)

    assert [a.filename for a in artefacts] == ["report.html"]
    html = artefacts[0].content.decode()
    assert "$7.59 NZD MTD" in html
    assert "beacon" in html and "untagged" in html
    assert "1.64 NZD/USD" in html          # fine print carries the fx rate
    assert "billing days are UTC" in html.lower()  # fine print carries the day mapping
    assert "http://" not in html and "https://" not in html  # self-contained


def test_missing_template_dir_is_a_render_error() -> None:
    renderer = HtmlRenderer(HtmlRendererConfig())

    with pytest.raises(RenderError, match="template"):
        renderer.render(fixture_data(), None)
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/plugins/test_html_renderer.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'wkx_beacon.plugins.html_renderer'`.

- [ ] **Step 3: Write `src/wkx_beacon/plugins/html_renderer.py`**

```python
"""html renderer: report data + the collector's template pack -> one self-contained page."""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
from pydantic import BaseModel

from wkx_beacon.exceptions import RenderError
from wkx_beacon.plugin import Artefact, ReportData

logger = logging.getLogger(__name__)


class HtmlRendererConfig(BaseModel):
    model_config = {"extra": "forbid"}


class HtmlRenderer:
    name = "html"
    config_model = HtmlRendererConfig

    def __init__(self, config: HtmlRendererConfig) -> None:
        self.config = config

    def render(self, data: ReportData, template_dir: Path | None) -> list[Artefact]:
        if template_dir is None:
            raise RenderError(
                f"no template pack for report type {data.report_type!r}; "
                "the collector must provide template_dir()"
            )
        env = Environment(
            loader=FileSystemLoader(template_dir), autoescape=select_autoescape(["html"])
        )
        template_name = f"{data.report_type}.html.j2"
        try:
            html = env.get_template(template_name).render(data=data)
        except TemplateNotFound as e:
            raise RenderError(f"template {template_name!r} not found in {template_dir}") from e
        except Exception as e:  # noqa: BLE001 - boundary translation
            raise RenderError(f"rendering {template_name!r} failed: {e}") from e
        logger.info("rendered %s (%d bytes)", template_name, len(html))
        return [Artefact(filename="report.html", media_type="text/html", content=html.encode())]
```

- [ ] **Step 4: Write `src/wkx_beacon/plugins/aws_cost/templates/cost.html.j2`**

The layout follows the viewer mockup from the design session: stat tiles, budget meter, daily bars, breakdowns, table view, fine print. Money macro applies the currency display; labels come precomputed from the collector.

```html
{% macro money(usd) -%}
  {%- if data.display == "local-first" -%}
    ${{ "%.2f" | format(usd * data.fx_usd_to_local) }} {{ data.budget_currency }}
  {%- else -%}
    ${{ "%.2f" | format(usd) }} USD
  {%- endif -%}
{%- endmacro -%}
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ data.billing_month }} cost report</title>
<style>
  body { margin: 0 auto; max-width: 860px; padding: 24px; color: #23262c;
         font-family: system-ui, sans-serif; }
  h1 { font-size: 1.3em; } .muted { color: #6b7076; font-size: 0.85em; }
  .tiles { display: flex; gap: 12px; flex-wrap: wrap; }
  .tile { border: 1px solid #ddd; border-radius: 8px; padding: 10px 14px; flex: 1 1 150px; }
  .tile .v { font-size: 1.5em; font-weight: 600; }
  .meter { position: relative; height: 12px; border-radius: 6px; background: #cde2fb; margin: 18px 0 6px; }
  .meter .fill { position: absolute; inset: 0 auto 0 0; border-radius: 6px; background: #2a78d6; }
  .meter .proj { position: absolute; top: -3px; bottom: -3px; width: 2px; background: #52514e; }
  .bars { display: flex; align-items: flex-end; gap: 2px; height: 120px; margin-top: 18px; }
  .bars div { flex: 1; background: #2a78d6; border-radius: 3px 3px 0 0; }
  table { border-collapse: collapse; margin-top: 14px; width: 100%; }
  td, th { text-align: left; padding: 5px 8px; border-bottom: 1px solid #eee; font-size: 0.9em; }
  td:last-child { text-align: right; font-variant-numeric: tabular-nums; }
</style>
</head>
<body>
<h1>Platform cost · {{ data.billing_month }}</h1>
<p class="muted">Generated {{ data.generated_at.isoformat() }} · grouped by cost-allocation tags</p>

<div class="tiles">
  <div class="tile"><div class="muted">Month-to-date</div><div class="v">{{ money(data.mtd_usd) }}</div></div>
  <div class="tile"><div class="muted">Projected month-end</div>
    <div class="v">{% if data.projected_usd is not none %}{{ money(data.projected_usd) }}{% else %}n/a{% endif %}</div></div>
  <div class="tile"><div class="muted">Latest billing day{% if data.latest_day %} ({{ data.daily[-1].label }}){% endif %}</div>
    <div class="v">{{ money(data.latest_day_usd) }}</div></div>
  <div class="tile"><div class="muted">Budget</div><div class="v">${{ "%.2f" | format(data.budget) }} {{ data.budget_currency }}</div></div>
</div>

{% set budget_usd = data.budget / data.fx_usd_to_local if data.display == "local-first" else data.budget %}
<div class="meter">
  <div class="fill" style="width: {{ [100, (100 * data.mtd_usd / budget_usd) | round(1)] | min }}%"></div>
  {% if data.projected_usd is not none %}
  <div class="proj" style="left: {{ [99, (100 * data.projected_usd / budget_usd) | round(1)] | min }}%"></div>
  {% endif %}
</div>
<p class="muted">Fill is month-to-date; the tick is the projected month-end.</p>

{% set max_usd = data.daily | map(attribute="usd") | max if data.daily else 1 %}
<div class="bars">
  {% for d in data.daily %}<div style="height: {{ (100 * d.usd / max_usd) | round(1) }}%" title="{{ d.label }} · {{ money(d.usd) }}"></div>{% endfor %}
</div>
<p class="muted">Daily spend, last {{ data.daily | length }} billing days.</p>

<table>
  <tr><th>By service</th><th></th></tr>
  {% for t in data.by_service %}<tr><td>{{ t.key }}</td><td>{{ money(t.usd) }}</td></tr>{% endfor %}
</table>
<table>
  <tr><th>By env</th><th></th></tr>
  {% for t in data.by_env %}<tr><td>{{ t.key }}</td><td>{{ money(t.usd) }}</td></tr>{% endfor %}
</table>

<details><summary class="muted">Daily spend as a table</summary>
<table>{% for d in data.daily %}<tr><td>{{ d.label }}</td><td>{{ money(d.usd) }}</td></tr>{% endfor %}</table>
</details>

<p class="muted">
  Source: AWS Cost Explorer, unblended cost, USD.
  {% if data.display == "local-first" %}Displayed in {{ data.budget_currency }} at a configured static rate of {{ data.fx_usd_to_local }} {{ data.budget_currency }}/USD.{% endif %}
  Billing days are UTC{% if data.day_display == "local-first" %}; date labels show the {{ data.timezone }} date covering most of each billing day{% endif %}.
  No account identifiers are rendered.
</p>
</body>
</html>
```

- [ ] **Step 5: Run tests to verify pass, then full checks**

```bash
uv run pytest tests/plugins/test_html_renderer.py -v    # expected: 2 passed
uv run ruff check --fix && uv run ruff format && uv run ty check && uv run pytest
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: html renderer and cost template pack"
```

---

### Task 10: email-ses notifier

**Files:**
- Create: `src/wkx_beacon/plugins/email_ses.py`, `tests/plugins/test_email_ses.py`

**Interfaces:**
- Consumes: `RunSummary`, `NotifyError`.
- Produces: `class EmailSesConfig(BaseModel)`: `to: list[str]` (min length 1), `sender: str`, `region: str = "ap-southeast-2"`; `class EmailSesNotifier`: `name = "email-ses"`, `config_model = EmailSesConfig`, `__init__(self, config, ses_client: Any | None = None)` (lazy boto3 `sesv2` client), `notify(summary) -> None`.

Subject rules: ok `beacon · {report_name} · {headline}`; degraded `beacon · {report_name} · DEGRADED · {headline}`; failed `beacon · {report_name} · FAILED at {failed_stage}`. Body: plain text with the headline, status, error (when present), and `report_url`.

- [ ] **Step 1: Write the failing tests** in `tests/plugins/test_email_ses.py`

```python
from typing import Any

import boto3
import pytest
from botocore.stub import ANY, Stubber

from wkx_beacon.exceptions import NotifyError
from wkx_beacon.plugin import RunSummary
from wkx_beacon.plugins.email_ses import EmailSesConfig, EmailSesNotifier


def notifier() -> tuple[EmailSesNotifier, Stubber]:
    client = boto3.client(
        "sesv2", region_name="ap-southeast-2", aws_access_key_id="x", aws_secret_access_key="x"
    )
    stubber = Stubber(client)
    config = EmailSesConfig(to=["me@example.com"], sender="beacon@example.com")
    return EmailSesNotifier(config, ses_client=client), stubber


def summary(status: str = "ok", failed_stage: str | None = None) -> RunSummary:
    return RunSummary(
        report_name="platform-cost",
        run_id="20260704T070015Z",
        status=status,  # type: ignore[arg-type]
        headline="$7.59 NZD MTD",
        failed_stage=failed_stage,
        report_url="http://beacon.test/reports/platform-cost/latest",
    )


def expected_params(subject: str) -> dict[str, Any]:
    return {
        "FromEmailAddress": "beacon@example.com",
        "Destination": {"ToAddresses": ["me@example.com"]},
        "Content": {"Simple": {"Subject": {"Data": subject}, "Body": ANY}},
    }


def test_ok_email_subject_carries_the_headline() -> None:
    n, stubber = notifier()
    stubber.add_response(
        "send_email",
        {"MessageId": "1"},
        expected_params("beacon · platform-cost · $7.59 NZD MTD"),
    )

    with stubber:
        n.notify(summary())

    stubber.assert_no_pending_responses()


def test_failed_email_subject_names_the_stage() -> None:
    n, stubber = notifier()
    stubber.add_response(
        "send_email",
        {"MessageId": "1"},
        expected_params("beacon · platform-cost · FAILED at collect"),
    )

    with stubber:
        n.notify(summary(status="failed", failed_stage="collect"))

    stubber.assert_no_pending_responses()


def test_ses_errors_become_notify_errors() -> None:
    n, stubber = notifier()
    stubber.add_client_error("send_email", "MessageRejected")

    with stubber, pytest.raises(NotifyError):
        n.notify(summary())
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/plugins/test_email_ses.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'wkx_beacon.plugins.email_ses'`.

- [ ] **Step 3: Write `src/wkx_beacon/plugins/email_ses.py`**

```python
"""email-ses notifier: announce a run by email via Amazon SES v2."""

import logging
from typing import Any

from pydantic import BaseModel, Field

from wkx_beacon.exceptions import NotifyError
from wkx_beacon.plugin import RunSummary

logger = logging.getLogger(__name__)


class EmailSesConfig(BaseModel):
    model_config = {"extra": "forbid"}

    to: list[str] = Field(min_length=1)
    sender: str
    region: str = "ap-southeast-2"


class EmailSesNotifier:
    name = "email-ses"
    config_model = EmailSesConfig

    def __init__(self, config: EmailSesConfig, ses_client: Any | None = None) -> None:
        self.config = config
        self._ses_client = ses_client

    def _client(self) -> Any:
        if self._ses_client is None:
            import boto3

            self._ses_client = boto3.client("sesv2", region_name=self.config.region)
        return self._ses_client

    def _subject(self, summary: RunSummary) -> str:
        base = f"beacon · {summary.report_name}"
        if summary.status == "failed":
            return f"{base} · FAILED at {summary.failed_stage or 'unknown stage'}"
        if summary.status == "degraded":
            return f"{base} · DEGRADED · {summary.headline}"
        return f"{base} · {summary.headline}"

    def notify(self, summary: RunSummary) -> None:
        lines = [summary.headline, f"Status: {summary.status}"]
        if summary.error:
            lines.append(f"Error: {summary.error}")
        if summary.report_url:
            lines.append(f"Report: {summary.report_url}")
        try:
            self._client().send_email(
                FromEmailAddress=self.config.sender,
                Destination={"ToAddresses": self.config.to},
                Content={
                    "Simple": {
                        "Subject": {"Data": self._subject(summary)},
                        "Body": {"Text": {"Data": "\n".join(lines)}},
                    }
                },
            )
        except Exception as e:  # noqa: BLE001 - boundary translation
            raise NotifyError(f"SES send failed: {e}") from e
        logger.info("emailed run %s %s to %d recipients", summary.report_name, summary.run_id, len(self.config.to))
```

- [ ] **Step 4: Run tests to verify pass, then full checks**

```bash
uv run pytest tests/plugins/test_email_ses.py -v    # expected: 3 passed
uv run ruff check --fix && uv run ruff format && uv run ty check && uv run pytest
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: email-ses notifier"
```

---

### Task 11: Bootstrap and CLI

**Files:**
- Create: `src/wkx_beacon/bootstrap.py`, `src/wkx_beacon/__main__.py`, `beacon.toml`, `tests/test_cli.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `@dataclass class AppContext`: `settings: Settings`, `store: Store`, `reports: list[ResolvedReport]`
  - `def bootstrap(settings: Settings | None = None, registry: PluginRegistry | None = None) -> AppContext` (discovers plugins, loads and resolves config; the injectable `registry` keeps tests offline)
  - `def main() -> None` console entry point; commands `serve`, `run REPORT_NAME`, `validate`

- [ ] **Step 1: Write `beacon.toml`** (this deployment's wiring, baked into the image; adjust `to`/`sender` at deploy time)

```toml
[[report]]
name = "platform-cost"
collector = "aws-cost"
renderers = ["html"]
notifiers = ["email-ses"]
schedule = "0 7 * * *"
timezone = "Pacific/Auckland"
catch_up = false

[report.collector_config]
budget = 50.0
budget_currency = "NZD"
display = "local-first"
fx_usd_to_local = 1.64
day_display = "local-first"
timezone = "Pacific/Auckland"

[report.notifier_config.email-ses]
to = ["you@example.com"]
sender = "beacon@wingkongexchange.dev"
```

- [ ] **Step 2: Write the failing tests** in `tests/test_cli.py`

```python
from pathlib import Path

import pytest
from typer.testing import CliRunner

from wkx_beacon.__main__ import app
from wkx_beacon.bootstrap import bootstrap
from wkx_beacon.config import Settings
from wkx_beacon.plugin import PluginRegistry
from fakes import FakeCollector, FakeNotifier, FakeRenderer

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
```

Note `test_validate_succeeds_against_the_committed_config` exercises real entry-point discovery against the committed `beacon.toml`: this is the boot-validation path end to end, offline (plugin clients are lazy, so no AWS call happens).

- [ ] **Step 3: Run to verify failure**

```bash
uv run pytest tests/test_cli.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'wkx_beacon.bootstrap'`.

- [ ] **Step 4: Write `src/wkx_beacon/bootstrap.py`**

```python
"""Assemble the app: settings, plugin discovery, config resolution."""

import logging
from dataclasses import dataclass

from wkx_beacon.config import ResolvedReport, Settings, load_config, resolve
from wkx_beacon.plugin import PluginRegistry, discover
from wkx_beacon.store import Store

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    settings: Settings
    store: Store
    reports: list[ResolvedReport]


def bootstrap(
    settings: Settings | None = None, registry: PluginRegistry | None = None
) -> AppContext:
    """Fail here, at boot, not at 07:00."""
    settings = settings or Settings()
    registry = registry or discover()
    config = load_config(settings.config_file)
    reports = resolve(config, registry)
    logger.info("bootstrapped %d report(s)", len(reports))
    return AppContext(settings=settings, store=Store(settings.data_dir), reports=reports)
```

- [ ] **Step 5: Write `src/wkx_beacon/__main__.py`**

```python
"""CLI entry point. Run with `uv run beacon` or `python -m wkx_beacon`."""

import logging

import typer

from wkx_beacon._logging import configure as configure_logging

app = typer.Typer(help="Reports about the platform beacon runs on.", no_args_is_help=True)
logger = logging.getLogger(__name__)


@app.callback()
def _root() -> None:
    configure_logging()


@app.command()
def serve() -> None:
    """Run the scheduler and the web viewer. The container entrypoint."""
    import uvicorn

    from wkx_beacon.bootstrap import bootstrap
    from wkx_beacon.scheduler import build_scheduler
    from wkx_beacon.web.app import create_app

    context = bootstrap()
    scheduler = build_scheduler(context.reports, context.store, context.settings.base_url)
    scheduler.start()
    web_app = create_app(
        context.store, [r.config for r in context.reports], scheduler=scheduler
    )
    try:
        uvicorn.run(web_app, host=context.settings.host, port=context.settings.port, log_config=None)
    finally:
        scheduler.shutdown(wait=False)


@app.command()
def run(report_name: str) -> None:
    """One-shot pipeline run, for development and debugging."""
    from wkx_beacon.bootstrap import bootstrap
    from wkx_beacon.pipeline import execute

    context = bootstrap()
    matches = [r for r in context.reports if r.config.name == report_name]
    if not matches:
        names = ", ".join(r.config.name for r in context.reports)
        typer.echo(f"unknown report {report_name!r}; configured: {names}", err=True)
        raise typer.Exit(code=1)
    record = execute(matches[0], context.store, context.settings.base_url)
    typer.echo(f"{record.run_id} {record.status} {record.headline}")
    if record.status == "failed":
        raise typer.Exit(code=1)


@app.command()
def validate() -> None:
    """Validate config and plugin discovery; usable in CI."""
    from wkx_beacon.bootstrap import bootstrap

    context = bootstrap()
    for report in context.reports:
        config = report.config
        typer.echo(
            f"{config.name}: {config.collector} -> {', '.join(config.renderers)}"
            f" -> {', '.join(config.notifiers)} ({config.schedule} {config.timezone})"
        )
    typer.echo("configuration valid")


def main() -> None:
    """Console-script entry point referenced from pyproject.toml."""
    app()


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run tests, verify the CLI by hand, full checks**

```bash
uv run pytest tests/test_cli.py -v      # expected: 3 passed
BEACON_DATA_DIR=./data uv run beacon validate   # expected: platform-cost line + "configuration valid"
uv run ruff check --fix && uv run ruff format && uv run ty check && uv run pytest
```

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: bootstrap, Typer CLI, and deployment beacon.toml"
```

---

### Task 12: Built-in discovery end to end and the conformance kit

**Files:**
- Create: `src/wkx_beacon/plugin/conformance.py`, `tests/plugin/test_conformance.py`, `tests/test_end_to_end.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `def check_collector(cls: type) -> None`, `def check_renderer(cls: type) -> None`, `def check_notifier(cls: type) -> None` in `wkx_beacon.plugin.conformance`, each raising `AssertionError` with a reason when the class breaks the plugin conventions. Third parties run these against their own plugins.

- [ ] **Step 1: Write the failing tests** in `tests/plugin/test_conformance.py`

```python
import pytest

from wkx_beacon.plugin import discover
from wkx_beacon.plugin.conformance import check_collector, check_notifier, check_renderer
from fakes import FakeCollector, FakeNotifier, FakeRenderer


def test_builtins_are_discoverable_via_real_entry_points() -> None:
    registry = discover()

    assert "aws-cost" in registry.collectors
    assert "html" in registry.renderers
    assert "email-ses" in registry.notifiers


def test_builtins_and_fakes_pass_conformance() -> None:
    registry = discover()
    for cls in (*registry.collectors.values(), FakeCollector):
        check_collector(cls)
    for cls in (*registry.renderers.values(), FakeRenderer):
        check_renderer(cls)
    for cls in (*registry.notifiers.values(), FakeNotifier):
        check_notifier(cls)


def test_conformance_rejects_a_broken_plugin() -> None:
    class Broken:
        name = "broken"

    with pytest.raises(AssertionError, match="config_model"):
        check_collector(Broken)
```

- [ ] **Step 2: Write `src/wkx_beacon/plugin/conformance.py`**

```python
"""Conformance checks for plugin authors. The plugin API is the product; these are its tests."""

from pydantic import BaseModel


def _check_common(cls: type, kind: str) -> None:
    assert isinstance(getattr(cls, "name", None), str) and cls.name, f"{kind} needs a str name"
    model = getattr(cls, "config_model", None)
    assert isinstance(model, type) and issubclass(model, BaseModel), (
        f"{kind} {cls.__name__} needs a config_model (pydantic BaseModel subclass)"
    )
    assert model.model_config.get("extra") == "forbid", (
        f"{kind} {cls.__name__} config_model must set extra='forbid' so config typos fail at boot"
    )


def check_collector(cls: type) -> None:
    _check_common(cls, "collector")
    assert isinstance(getattr(cls, "report_type", None), str), "collector needs a report_type"
    assert isinstance(getattr(cls, "platform", None), str), "collector needs a platform"
    assert callable(getattr(cls, "collect", None)), "collector needs collect()"
    assert callable(getattr(cls, "template_dir", None)), "collector needs template_dir()"


def check_renderer(cls: type) -> None:
    _check_common(cls, "renderer")
    assert callable(getattr(cls, "render", None)), "renderer needs render()"


def check_notifier(cls: type) -> None:
    _check_common(cls, "notifier")
    assert callable(getattr(cls, "notify", None)), "notifier needs notify()"
```

- [ ] **Step 3: Write `tests/test_end_to_end.py`** (the whole pipeline with the real aws-cost collector and html renderer, stubbed AWS, fake notifier)

```python
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import boto3
from botocore.stub import Stubber

from wkx_beacon.config import ReportConfig, ResolvedReport
from wkx_beacon.pipeline import execute
from wkx_beacon.plugins.aws_cost import AwsCostCollector, AwsCostConfig
from wkx_beacon.plugins.html_renderer import HtmlRenderer, HtmlRendererConfig
from wkx_beacon.store import Store
from fakes import FakeConfig, FakeNotifier


def ce_stub() -> tuple[Any, Stubber]:
    client = boto3.client(
        "ce", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="x"
    )
    stubber = Stubber(client)
    stubber.add_response(
        "get_cost_and_usage",
        {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2026-07-01", "End": "2026-07-02"},
                    "Groups": [
                        {
                            "Keys": ["Service$beacon", "Env$prod"],
                            "Metrics": {"UnblendedCost": {"Amount": "1.50", "Unit": "USD"}},
                        }
                    ],
                    "Total": {},
                    "Estimated": True,
                }
            ],
            "DimensionValueAttributes": [],
        },
    )
    return client, stubber


def test_cost_report_end_to_end(tmp_path: Path) -> None:
    client, stubber = ce_stub()
    config = AwsCostConfig(
        budget=Decimal("50"),
        budget_currency="NZD",
        display="local-first",
        fx_usd_to_local=Decimal("1.64"),
        day_display="local-first",
        timezone="Pacific/Auckland",
    )
    notifier = FakeNotifier(FakeConfig())
    report = ResolvedReport(
        config=ReportConfig(
            name="platform-cost",
            collector="aws-cost",
            renderers=["html"],
            notifiers=["email-ses"],
            schedule="0 7 * * *",
            timezone="Pacific/Auckland",
        ),
        collector=AwsCostCollector(config, ce_client=client),
        renderers={"html": HtmlRenderer(HtmlRendererConfig())},
        notifiers={"email-ses": notifier},
    )
    store = Store(tmp_path)

    with stubber:
        record = execute(report, store, "http://beacon.test")

    assert record.status == "ok"
    assert record.artefacts == ["report.html"]
    artefact = store.artefact_path("platform-cost", record.run_id, "report.html")
    assert artefact is not None
    html = artefact.read_text()
    assert "NZD" in html and "https://" not in html
    assert notifier.received[0].headline == record.headline
```

Note: the collector's `collect()` is called by the pipeline without `now_fn`, so this test depends on the real date only through "the stubbed day falls inside the current month or the 30-day window"; the assertions avoid date-sensitive figures. If the suite ever runs after August 2026, regenerate the stub dates.

- [ ] **Step 4: Run tests, full checks, commit**

```bash
uv run pytest tests/plugin/test_conformance.py tests/test_end_to_end.py -v   # expected: 4 passed
uv run ruff check --fix && uv run ruff format && uv run ty check && uv run pytest
git add -A
git commit -m "feat: plugin conformance kit and end-to-end pipeline test"
```

---

### Task 13: Container, platform files, CI, README

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `compose.yml`, `caddy.snippet`, `.github/workflows/ci.yml`, `README.md`

- [ ] **Step 1: Write `Dockerfile`** (arm64 first, multi-arch capable)

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS build
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY . .
RUN uv sync --locked --no-dev

FROM python:3.14-slim-bookworm
WORKDIR /app
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH" LOG_FORMAT=json
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')" || exit 1
ENTRYPOINT ["beacon"]
CMD ["serve"]
```

- [ ] **Step 2: Write `.dockerignore`**

```
.git
.venv
.pytest_cache
.ruff_cache
data
docs
tests
.env
```

- [ ] **Step 3: Write `compose.yml`** (local development; the platform contract from the wkx-platform reference project supersedes this at deploy time)

```yaml
services:
  beacon:
    build: .
    ports:
      - "8000:8000"
    environment:
      BEACON_DATA_DIR: /data
      BEACON_BASE_URL: ${BEACON_BASE_URL:-http://localhost:8000}
    volumes:
      - ./data:/data
```

- [ ] **Step 4: Write `caddy.snippet`** (the host block beacon contributes to the WKX Platform)

```
beacon.wingkongexchange.dev {
	reverse_proxy beacon-prod:8000
}
```

- [ ] **Step 5: Write `.github/workflows/ci.yml`** (PROJECT.md §14c plus the container build)

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true

      - name: Set up Python
        run: uv python install

      - name: Install dependencies
        run: uv sync --locked

      - name: Ruff lint
        run: uv run ruff check

      - name: Ruff format check
        run: uv run ruff format --check

      - name: ty type check
        run: uv run ty check

      - name: pytest
        run: uv run pytest --cov=wkx_beacon --cov-report=term-missing

      - name: Validate configuration
        run: BEACON_DATA_DIR=/tmp/beacon uv run beacon validate

  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-qemu-action@v3
      - uses: docker/setup-buildx-action@v3
      - name: Build arm64 image
        uses: docker/build-push-action@v6
        with:
          context: .
          platforms: linux/arm64
          push: false
```

- [ ] **Step 6: Write `README.md`** covering, in NZ English with no em dashes: what beacon is (one paragraph, the CONTEXT.md framing); the MVP slice; quickstart (`uv sync`, `cp .env.example .env`, `uv run beacon validate`, `uv run beacon run platform-cost` needs AWS credentials, `uv run beacon serve`); configuration (env vars table and `beacon.toml` with the display/day_display options); plugin authoring (the three entry-point groups, `cls(config)` convention, conformance kit import path); deployment notes (WKX Platform prerequisites from spec §12); links to the spec, `CONTEXT.md`, and the ADRs. Include the container Mermaid diagram from spec §4.

- [ ] **Step 7: Verify the container locally** (requires Docker; skip on CI-only environments)

```bash
docker build -t wkx-beacon:dev .
docker run --rm -p 8000:8000 -e BEACON_DATA_DIR=/data wkx-beacon:dev &
sleep 3 && curl -fsS http://localhost:8000/healthz && echo OK
docker stop $(docker ps -q --filter ancestor=wkx-beacon:dev)
```
Expected: `{"status":"ok"}OK`.

- [ ] **Step 8: Full checks and commit**

```bash
uv run ruff check --fix && uv run ruff format && uv run ty check && uv run pytest
git add -A
git commit -m "feat: container, platform files, CI, and README"
```

---

## Out of scope for this plan

Deferred by the spec: other collectors, renderers, and notifiers; retention; metrics; authn (ADR-0002); the deploy workflow (inherited from the wkx-platform reference project); the wkx-platform Terraform prerequisites (SES domain identity, IAM permissions, SSM parameters, DNS), which are tracked in the platform repo, not here.

