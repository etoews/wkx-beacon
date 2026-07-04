from datetime import UTC, datetime
from pathlib import Path

import pytest

from wkx_beacon.exceptions import StoreError
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


def test_write_artefacts_refuses_traversal(tmp_path: Path) -> None:
    store = Store(tmp_path)
    artefact = Artefact(filename="../evil.html", media_type="text/html", content=b"pwned")

    with pytest.raises(StoreError):
        store.write_artefacts("platform-cost", "20260704T070015Z", [artefact])

    assert not (tmp_path / "reports" / "platform-cost" / "evil.html").exists()
    assert not (tmp_path / "evil.html").exists()


def test_read_record_raises_store_error_on_corrupt_json(tmp_path: Path) -> None:
    store = Store(tmp_path)
    run_dir = store._run_dir("platform-cost", "20260704T070015Z")
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text("{not json")

    with pytest.raises(StoreError):
        store.read_record("platform-cost", "20260704T070015Z")


def test_list_runs_skips_corrupt_record_and_returns_valid_ones(tmp_path: Path) -> None:
    store = Store(tmp_path)
    store.write_record(record("20260703T070015Z"))
    corrupt_dir = store._run_dir("platform-cost", "20260704T070015Z")
    corrupt_dir.mkdir(parents=True)
    (corrupt_dir / "run.json").write_text("{not json")

    runs = store.list_runs("platform-cost")

    assert [r.run_id for r in runs] == ["20260703T070015Z"]
