from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from wkx_beacon.config import ReportConfig
from wkx_beacon.plugin import Artefact
from wkx_beacon.store import RunRecord, StageOutcome, Store, new_run_id
from wkx_beacon.web.app import create_app

NOW = datetime(2026, 7, 4, 7, 0, 15, tzinfo=UTC)
CONFIG = ReportConfig(
    name="platform-cost",
    collector="aws-cost",
    renderers=["html"],
    notifiers=["email-ses"],
    schedule="0 7 * * *",
    timezone="Pacific/Auckland",
)


def seeded_client(tmp_path: Path) -> tuple[TestClient, str]:
    store = Store(tmp_path)
    run_id = new_run_id(NOW)
    store.write_artefacts(
        "platform-cost",
        run_id,
        [Artefact(filename="report.html", media_type="text/html", content=b"<html>spend</html>")],
    )
    store.write_record(
        RunRecord(
            report_name="platform-cost",
            run_id=run_id,
            status="ok",
            started_at=NOW,
            finished_at=NOW,
            stages=[StageOutcome(stage="collect", ok=True)],
            headline="$4.65 MTD",
            artefacts=["report.html"],
        )
    )
    return TestClient(create_app(store, [CONFIG])), run_id


def test_index_lists_reports_with_headline(tmp_path: Path) -> None:
    client, _ = seeded_client(tmp_path)

    response = client.get("/")

    assert response.status_code == 200
    assert "platform-cost" in response.text
    assert "$4.65 MTD" in response.text


def test_latest_redirects_to_latest_published_run(tmp_path: Path) -> None:
    client, run_id = seeded_client(tmp_path)

    response = client.get("/reports/platform-cost/latest", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == f"/reports/platform-cost/runs/{run_id}"


def test_artefact_is_served_raw(tmp_path: Path) -> None:
    client, run_id = seeded_client(tmp_path)

    response = client.get(f"/reports/platform-cost/runs/{run_id}/artifacts/report.html")

    assert response.status_code == 200
    assert response.text == "<html>spend</html>"


def test_unknown_report_is_404_and_traversal_is_404(tmp_path: Path) -> None:
    client, run_id = seeded_client(tmp_path)

    assert client.get("/reports/nope").status_code == 404
    bad = client.get(f"/reports/platform-cost/runs/{run_id}/artifacts/..%2Frun.json")
    assert bad.status_code == 404


def test_security_headers_are_set(tmp_path: Path) -> None:
    client, _ = seeded_client(tmp_path)

    response = client.get("/")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_report_page_must_be_at_least_one(tmp_path: Path) -> None:
    client, _ = seeded_client(tmp_path)

    assert client.get("/reports/platform-cost?page=0").status_code == 422
    assert client.get("/reports/platform-cost?page=1").status_code == 200


def test_fragment_runs_page_must_be_at_least_one(tmp_path: Path) -> None:
    client, _ = seeded_client(tmp_path)

    assert client.get("/reports/platform-cost/fragments/runs?page=0").status_code == 422
    assert client.get("/reports/platform-cost/fragments/runs?page=1").status_code == 200


def test_healthz(tmp_path: Path) -> None:
    client, _ = seeded_client(tmp_path)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_corrupt_run_record_is_404_with_security_headers(tmp_path: Path) -> None:
    client, run_id = seeded_client(tmp_path)
    run_json = tmp_path / "reports" / "platform-cost" / "runs" / run_id / "run.json"
    run_json.write_text("{not json")

    response = client.get(f"/reports/platform-cost/runs/{run_id}")

    assert response.status_code == 404
    assert response.headers["x-content-type-options"] == "nosniff"


XSS_HEADLINE = '<script>alert(1)</script>"><img src=x>'


def _seed_xss_run(tmp_path: Path) -> tuple[Store, str]:
    store = Store(tmp_path)
    run_id = new_run_id(NOW)
    store.write_record(
        RunRecord(
            report_name="platform-cost",
            run_id=run_id,
            status="ok",
            started_at=NOW,
            finished_at=NOW,
            stages=[StageOutcome(stage="collect", ok=True)],
            headline=XSS_HEADLINE,
            artefacts=[],
        )
    )
    return store, run_id


def test_run_detail_escapes_headline_html(tmp_path: Path) -> None:
    store, run_id = _seed_xss_run(tmp_path)
    client = TestClient(create_app(store, [CONFIG]))

    response = client.get(f"/reports/platform-cost/runs/{run_id}")

    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.text


def test_index_escapes_latest_headline_html(tmp_path: Path) -> None:
    store, _ = _seed_xss_run(tmp_path)
    client = TestClient(create_app(store, [CONFIG]))

    response = client.get("/")

    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.text


def test_unhandled_exception_returns_500_with_security_headers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from wkx_beacon.store import Store

    client, run_id = seeded_client(tmp_path)

    def boom(self: Store, report_name: str, run_id: str) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(Store, "read_record", boom)
    raising_client = TestClient(client.app, raise_server_exceptions=False)

    response = raising_client.get(f"/reports/platform-cost/runs/{run_id}")

    assert response.status_code == 500
    assert response.headers["x-content-type-options"] == "nosniff"
