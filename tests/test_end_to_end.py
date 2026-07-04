from decimal import Decimal
from pathlib import Path
from typing import Any

import boto3
from botocore.stub import Stubber
from fakes import FakeConfig, FakeNotifier

from wkx_beacon.config import ReportConfig, ResolvedReport
from wkx_beacon.pipeline import execute
from wkx_beacon.plugins.aws_cost import AwsCostCollector, AwsCostConfig
from wkx_beacon.plugins.html_renderer import HtmlRenderer, HtmlRendererConfig
from wkx_beacon.store import Store


def ce_stub() -> tuple[Any, Stubber]:
    client = boto3.client(
        "ce", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="x"
    )
    stubber = Stubber(client)
    stubber.add_response(
        "get_cost_and_usage",
        {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2026-07-01", "End": "2026-07-02"},
                    "Groups": [
                        {
                            "Keys": ["Service$beacon", "Env$prod"],
                            "Metrics": {"UnblendedCost": {"Amount": "1.50", "Unit": "USD"}},
                        }
                    ],
                    "Total": {},
                    "Estimated": True,
                }
            ],
            "DimensionValueAttributes": [],
        },
    )
    return client, stubber


def test_cost_report_end_to_end(tmp_path: Path) -> None:
    client, stubber = ce_stub()
    config = AwsCostConfig(
        budget=Decimal("50"),
        budget_currency="NZD",
        display="local-first",
        fx_usd_to_local=Decimal("1.64"),
        day_display="local-first",
        timezone="Pacific/Auckland",
    )
    notifier = FakeNotifier(FakeConfig())
    report = ResolvedReport(
        config=ReportConfig(
            name="platform-cost",
            collector="aws-cost",
            renderers=["html"],
            notifiers=["email-ses"],
            schedule="0 7 * * *",
            timezone="Pacific/Auckland",
        ),
        collector=AwsCostCollector(config, ce_client=client),
        renderers={"html": HtmlRenderer(HtmlRendererConfig())},
        notifiers={"email-ses": notifier},
    )
    store = Store(tmp_path)

    with stubber:
        record = execute(report, store, "http://beacon.test")

    assert record.status == "ok"
    assert record.artefacts == ["report.html"]
    artefact = store.artefact_path("platform-cost", record.run_id, "report.html")
    assert artefact is not None
    html = artefact.read_text()
    assert "NZD" in html and "https://" not in html
    assert notifier.received[0].headline == record.headline
