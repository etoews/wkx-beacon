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


def test_artefact_path_refuses_run_id_traversal(tmp_path: Path) -> None:
    """A run_id that walks out of the runs dir must not resolve an artefact.

    The runs dir is made real so the ".." segments resolve through real
    directories to a planted file just outside the runs tree; without the
    run_id guard, a bare filename would then resolve against that escaped dir.
    """
    store = Store(tmp_path)
    artefact = Artefact(filename="report.html", media_type="text/html", content=b"<html/>")
    store.write_artefacts("platform-cost", "legit-run", [artefact])  # makes the runs dir real
    escaped = tmp_path / "escaped" / "artifacts"
    escaped.mkdir(parents=True)
    (escaped / "secret.html").write_text("secret")

    assert store.artefact_path("platform-cost", "../../../escaped", "secret.html") is None


def test_write_artefacts_refuses_traversal(tmp_path: Path) -> None:
    store = Store(tmp_path)
    artefact = Artefact(filename="../evil.html", media_type="text/html", content=b"pwned")

    with pytest.raises(StoreError):
        store.write_artefacts("platform-cost", "20260704T070015Z", [artefact])

    assert not (tmp_path / "reports" / "platform-cost" / "evil.html").exists()
    assert not (tmp_path / "evil.html").exists()
    assert not list(tmp_path.rglob("evil.html"))


def test_read_record_raises_store_error_on_corrupt_json(tmp_path: Path) -> None:
    store = Store(tmp_path)
    run_dir = store._run_dir("platform-cost", "20260704T070015Z")
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text("{not json")

    with pytest.raises(StoreError):
        store.read_record("platform-cost", "20260704T070015Z")


def test_write_record_is_atomic_via_tmp_file_and_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """write_record must write run.json.tmp then Path.replace it onto run.json.

    A crash between those two steps leaves run.json untouched (still the
    previous commit) or absent, never a half-written file.
    """
    store = Store(tmp_path)
    run_id = new_run_id(NOW)
    run_dir = store._run_dir("platform-cost", run_id)
    replace_calls: list[Path] = []
    original_replace = Path.replace

    def spy_replace(self: Path, target: str) -> Path:
        replace_calls.append(self)
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", spy_replace)

    store.write_record(record(run_id))

    assert replace_calls == [run_dir / "run.json.tmp"]
    assert not (run_dir / "run.json.tmp").exists()
    assert (run_dir / "run.json").is_file()
    read = store.read_record("platform-cost", run_id)
    assert read is not None and read.headline == "fine"


def test_list_runs_skips_corrupt_record_and_returns_valid_ones(tmp_path: Path) -> None:
    store = Store(tmp_path)
    store.write_record(record("20260703T070015Z"))
    corrupt_dir = store._run_dir("platform-cost", "20260704T070015Z")
    corrupt_dir.mkdir(parents=True)
    (corrupt_dir / "run.json").write_text("{not json")

    runs = store.list_runs("platform-cost")

    assert [r.run_id for r in runs] == ["20260703T070015Z"]


def test_read_record_refuses_run_id_traversal(tmp_path: Path) -> None:
    """A run_id that walks out of the report's runs dir must not be read.

    The runs dir must exist for real (as it would for any onboarded report)
    so the ".." segments resolve through real directories to a real run.json
    sitting just outside the runs tree; without the guard this would succeed.
    """
    store = Store(tmp_path)
    store.write_record(record("legit-run"))  # makes reports/platform-cost/runs real
    escaped = tmp_path / "etc"
    escaped.mkdir()
    (escaped / "run.json").write_text(record("escaped").model_dump_json())

    assert store.read_record("platform-cost", "../../../etc") is None


def test_read_record_refuses_traversal_in_report_name_and_run_id(tmp_path: Path) -> None:
    store = Store(tmp_path)

    assert store.read_record("../../etc", "../../passwd") is None


def test_read_record_refuses_report_name_escape_with_clean_run_id(tmp_path: Path) -> None:
    """A report_name that escapes the reports root must be refused even when

    run_id is clean, so the guard holds without relying on config-layer slug
    validation. A run.json is planted where an unguarded base would land.
    """
    store = Store(tmp_path)
    # report_name "../escaped" makes the unguarded base data_dir/escaped/runs;
    # plant a real run.json there so only the reports-root anchor refuses it.
    escaped = tmp_path / "escaped" / "runs" / "run"
    escaped.mkdir(parents=True)
    (escaped / "run.json").write_text(record("run").model_dump_json())

    assert store.read_record("../escaped", "run") is None
