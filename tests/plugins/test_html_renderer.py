from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from wkx_beacon.exceptions import RenderError
from wkx_beacon.plugins.aws_cost import (
    AwsCostCollector,
    AwsCostConfig,
    CostReportData,
    DailyCost,
    TagCost,
)
from wkx_beacon.plugins.html_renderer import HtmlRenderer, HtmlRendererConfig


def fixture_data() -> CostReportData:
    return CostReportData(
        report_type="cost",
        headline="$7.59 NZD MTD, projected $78.46 of $50.00 NZD",
        generated_at=datetime(2026, 7, 4, 19, 0, tzinfo=UTC),
        billing_month="July 2026",
        mtd_usd=Decimal("4.63"),
        latest_day=date(2026, 7, 3),
        latest_day_usd=Decimal("1.58"),
        projected_usd=Decimal("47.84"),
        budget=Decimal("50.00"),
        budget_currency="NZD",
        display="local-first",
        fx_usd_to_local=Decimal("1.64"),
        day_display="local-first",
        timezone="Pacific/Auckland",
        daily=[
            DailyCost(day=date(2026, 7, 1), label="2026-07-02", usd=Decimal("1.50")),
            DailyCost(day=date(2026, 7, 2), label="2026-07-03", usd=Decimal("1.55")),
            DailyCost(day=date(2026, 7, 3), label="2026-07-04", usd=Decimal("1.58")),
        ],
        by_service=[
            TagCost(key="beacon", usd=Decimal("2.55")),
            TagCost(key="untagged", usd=Decimal("0.50")),
        ],
        by_env=[TagCost(key="prod", usd=Decimal("4.13"))],
    )


def test_renders_self_contained_artefact() -> None:
    renderer = HtmlRenderer(HtmlRendererConfig())
    template_dir = AwsCostCollector(AwsCostConfig(budget=Decimal("30"))).template_dir()

    artefacts = renderer.render(fixture_data(), template_dir)

    assert [a.filename for a in artefacts] == ["report.html"]
    html = artefacts[0].content.decode()
    assert "$7.59 NZD MTD" in html
    assert "beacon" in html and "untagged" in html
    assert "1.64 NZD/USD" in html  # fine print carries the fx rate
    assert "billing days are utc" in html.lower()  # fine print carries the day mapping
    assert "http://" not in html and "https://" not in html  # self-contained


def test_missing_template_dir_is_a_render_error() -> None:
    renderer = HtmlRenderer(HtmlRendererConfig())

    with pytest.raises(RenderError, match="template"):
        renderer.render(fixture_data(), None)


def test_template_not_found_is_a_render_error(tmp_path: Path) -> None:
    renderer = HtmlRenderer(HtmlRendererConfig())

    with pytest.raises(RenderError, match="not found"):
        renderer.render(fixture_data(), tmp_path)


def test_generic_render_failure_is_a_render_error(tmp_path: Path) -> None:
    renderer = HtmlRenderer(HtmlRendererConfig())
    (tmp_path / "cost.html.j2").write_text("{% if %}")

    with pytest.raises(RenderError):
        renderer.render(fixture_data(), tmp_path)


def test_zero_spend_days_do_not_crash_the_daily_bars() -> None:
    renderer = HtmlRenderer(HtmlRendererConfig())
    template_dir = AwsCostCollector(AwsCostConfig(budget=Decimal("30"))).template_dir()
    data = fixture_data().model_copy(
        update={
            "daily": [
                DailyCost(day=date(2026, 7, 1), label="2026-07-01", usd=Decimal("0.00")),
                DailyCost(day=date(2026, 7, 2), label="2026-07-02", usd=Decimal("0.00")),
            ],
            "latest_day_usd": Decimal("0.00"),
            "mtd_usd": Decimal("0.00"),
        }
    )

    artefacts = renderer.render(data, template_dir)

    assert artefacts[0].content


def test_escapes_untrusted_strings_in_tag_cost_keys() -> None:
    renderer = HtmlRenderer(HtmlRendererConfig())
    template_dir = AwsCostCollector(AwsCostConfig(budget=Decimal("30"))).template_dir()

    data = fixture_data().model_copy(
        update={"by_service": [TagCost(key="<script>alert(1)</script>", usd=Decimal("1.00"))]}
    )

    artefacts = renderer.render(data, template_dir)
    html = artefacts[0].content.decode()

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
