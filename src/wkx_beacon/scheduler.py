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
        logger.info(
            "scheduled report=%s cron=%r tz=%s", config.name, config.schedule, config.timezone
        )
        if config.catch_up:
            runs = store.list_runs(config.name)
            last = runs[0].started_at if runs else None
            if needs_catch_up(config.schedule, config.timezone, last, datetime.now(tz=UTC)):
                scheduler.add_job(
                    execute, args=(report, store, base_url), id=f"{config.name}:catch-up"
                )
                logger.info("catch-up run queued for report=%s", config.name)
    return scheduler
