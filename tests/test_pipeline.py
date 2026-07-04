from pathlib import Path

from fakes import FakeCollector, FakeConfig, FakeNotifier, FakeRenderer

from wkx_beacon.config import ReportConfig, ResolvedReport
from wkx_beacon.exceptions import CollectError
from wkx_beacon.pipeline import execute
from wkx_beacon.store import Store

BASE_URL = "http://beacon.test"


class TemplateDirFailingCollector(FakeCollector):
    """A collector whose collect() succeeds but template_dir() raises."""

    def template_dir(self) -> Path | None:
        raise CollectError("fake collector template dir blew up")


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


def test_template_dir_failure_is_failed_but_still_a_run(tmp_path: Path) -> None:
    notifier = FakeNotifier(FakeConfig())
    report = ResolvedReport(
        config=ReportConfig(
            name="platform-cost",
            collector="fake-collector",
            renderers=["fake-renderer"],
            notifiers=["fake-notifier"],
            schedule="0 7 * * *",
            timezone="Pacific/Auckland",
        ),
        collector=TemplateDirFailingCollector(FakeConfig()),
        renderers={"fake-renderer": FakeRenderer(FakeConfig())},
        notifiers={"fake-notifier": notifier},
    )
    store = Store(tmp_path)

    record = execute(report, store, BASE_URL)

    assert record.status == "failed"
    assert not record.published
    assert store.read_record("platform-cost", record.run_id) is not None
    assert notifier.received[0].failed_stage == "template-dir"


def test_all_renderers_failing_is_failed(tmp_path: Path) -> None:
    report, store, _ = resolved(tmp_path, renderer_fails=True)

    record = execute(report, store, BASE_URL)

    assert record.status == "failed"


def test_notify_failure_degrades_but_never_unpublishes(tmp_path: Path) -> None:
    report, store, _ = resolved(tmp_path, notifier_fails=True)

    record = execute(report, store, BASE_URL)

    assert record.status == "degraded"
    assert record.published
