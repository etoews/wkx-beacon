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
