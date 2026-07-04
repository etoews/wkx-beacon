"""Filesystem store (ADR-0003). run.json is written last, as the commit marker."""

import logging
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ValidationError

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

    def write_artefacts(self, report_name: str, run_id: str, artefacts: Sequence[Artefact]) -> None:
        target = self._run_dir(report_name, run_id) / ARTEFACTS_DIR
        try:
            target.mkdir(parents=True, exist_ok=True)
            base = target.resolve()
            for artefact in artefacts:
                candidate = (target / artefact.filename).resolve()
                if not candidate.is_relative_to(base):
                    msg = f"artefact filename escapes artefacts dir: {artefact.filename}"
                    raise StoreError(msg)
                candidate.write_bytes(artefact.content)
        except OSError as e:
            raise StoreError(f"cannot write artefacts for {report_name}/{run_id}: {e}") from e

    def write_record(self, record: RunRecord) -> None:
        """Write run.json atomically: write a tmp file, then replace onto the real name.

        A crash between the two steps leaves the previous commit (or nothing),
        never a half-written run.json.
        """
        run_dir = self._run_dir(record.report_name, record.run_id)
        tmp_path = run_dir / f"{RECORD_FILE}.tmp"
        try:
            run_dir.mkdir(parents=True, exist_ok=True)
            tmp_path.write_text(record.model_dump_json(indent=2))
            tmp_path.replace(run_dir / RECORD_FILE)
        except OSError as e:
            raise StoreError(f"cannot write run record {record.run_id}: {e}") from e
        logger.info("stored run %s %s status=%s", record.report_name, record.run_id, record.status)

    def read_record(self, report_name: str, run_id: str) -> RunRecord | None:
        path = self._run_dir(report_name, run_id) / RECORD_FILE
        if not path.is_file():
            return None
        try:
            return RunRecord.model_validate_json(path.read_text())
        except (ValidationError, OSError, ValueError) as e:
            raise StoreError(f"corrupt run record {report_name}/{run_id}: {e}") from e

    def list_runs(self, report_name: str) -> list[RunRecord]:
        """All committed runs, newest first. Directories without run.json are ignored."""
        runs_dir = self.data_dir / "reports" / report_name / "runs"
        if not runs_dir.is_dir():
            return []
        records = []
        for run_dir in sorted(runs_dir.iterdir(), reverse=True):
            try:
                record = self.read_record(report_name, run_dir.name)
            except StoreError as e:
                logger.warning(
                    "skipping corrupt run record %s/%s: %s", report_name, run_dir.name, e
                )
                continue
            if record is not None:
                records.append(record)
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
