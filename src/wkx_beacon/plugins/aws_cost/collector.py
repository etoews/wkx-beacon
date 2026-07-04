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
    def fx_required_for_local(self) -> AwsCostConfig:
        needs_fx = self.display == "local-first" or self.budget_currency != "USD"
        if needs_fx and self.fx_usd_to_local is None:
            msg = "fx_usd_to_local required for local-first display or non-USD budget"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def local_first_needs_a_non_usd_budget_currency(self) -> AwsCostConfig:
        if self.display == "local-first" and self.budget_currency == "USD":
            msg = (
                "display 'local-first' with budget_currency 'USD' would mislabel "
                "USD converted by fx as USD; use display='usd' or a non-USD budget_currency"
            )
            raise ValueError(msg)
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
        except Exception as e:
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
        projected = _money(mtd / complete_days * days_in_month) if complete_days > 0 else None
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
        """Render the headline in the single currency selected by ``display``.

        ``local-first`` expresses mtd, projected and budget in
        ``budget_currency`` (mtd/projected are converted from USD via
        ``fx``; the budget is already in that currency). ``usd`` expresses
        everything in USD, converting the budget via ``fx`` when it is not
        already denominated in USD.
        """
        budget = self.config.budget
        if self.config.display == "local-first" and self.config.fx_usd_to_local is not None:
            fx = self.config.fx_usd_to_local
            currency = self.config.budget_currency
            mtd, projected = _money(mtd_usd * fx), None
            if projected_usd is not None:
                projected = _money(projected_usd * fx)
        else:
            currency = "USD"
            mtd, projected = mtd_usd, projected_usd
            if self.config.budget_currency != "USD" and self.config.fx_usd_to_local is not None:
                budget = _money(budget / self.config.fx_usd_to_local)
        if projected is None:
            return f"${mtd} {currency} MTD, no complete billing day yet"
        return f"${mtd} {currency} MTD, projected ${projected} of ${budget} {currency}"
