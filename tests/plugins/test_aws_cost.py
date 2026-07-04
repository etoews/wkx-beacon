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
    client = boto3.client(
        "ce",
        region_name="us-east-1",
        aws_access_key_id="x",
        aws_secret_access_key="x",
    )
    stubber = Stubber(client)
    # NOW is 2026-07-04 UTC: month_start is 2026-07-01, today-30d is 2026-06-04,
    # so Start is the earlier of the two and End is today (exclusive).
    expected_params = {
        "TimePeriod": {"Start": "2026-06-04", "End": "2026-07-04"},
        "Granularity": "DAILY",
        "Metrics": ["UnblendedCost"],
        "GroupBy": [{"Type": "TAG", "Key": "Service"}, {"Type": "TAG", "Key": "Env"}],
    }
    stubber.add_response("get_cost_and_usage", ce_response(), expected_params)
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


def test_usd_display_converts_non_usd_budget() -> None:
    config = AwsCostConfig(
        budget=Decimal("50"),
        budget_currency="NZD",
        fx_usd_to_local=Decimal("1.64"),
    )
    col, stubber = collector(config)

    with stubber:
        data = col.collect(now_fn=lambda: NOW)

    assert data.headline.endswith("of $30.49 USD")
    assert "NZD" not in data.headline


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
