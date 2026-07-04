"""Run a report end to end. A failed run is still a run."""

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

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
        dir_result = run_stage("template-dir", report.collector.template_dir)
        if stages[-1].ok:  # template_dir() legitimately returns None on success too
            template_dir = cast(Path | None, dir_result)
            for renderer_name, renderer in report.renderers.items():
                result = run_stage(
                    f"render:{renderer_name}", lambda r=renderer: r.render(data, template_dir)
                )
                if isinstance(result, list):
                    artefacts.extend(cast(list[Artefact], result))
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
        run_stage(f"notify:{notifier_name}", lambda n=notifier, s=summary: n.notify(s))
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
