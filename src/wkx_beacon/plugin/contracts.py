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
