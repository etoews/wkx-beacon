"""Read-only htmx viewer over the store. No authentication by design (ADR-0002)."""

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader

from wkx_beacon.config import ReportConfig
from wkx_beacon.exceptions import StoreError
from wkx_beacon.store import Store

logger = logging.getLogger(__name__)

PAGE_SIZE = 20
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def create_app(
    store: Store, report_configs: list[ReportConfig], scheduler: Any | None = None
) -> FastAPI:
    app = FastAPI(title="wkx-beacon", docs_url=None, redoc_url=None, openapi_url=None)
    # Templates are named *.html.j2, so Starlette's default select_autoescape()
    # (which keys off the final extension) would see ".j2" and leave
    # autoescape OFF. Force it on explicitly, matching the artefact renderer.
    template_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
    templates = Jinja2Templates(env=template_env)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    configured = {c.name: c for c in report_configs}

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Any) -> Response:
        response: Response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> Response:
        logger.exception("unhandled exception while serving %s", request.url.path)
        return PlainTextResponse("internal server error", status_code=500, headers=SECURITY_HEADERS)

    def _known(name: str) -> ReportConfig:
        if name not in configured:
            raise HTTPException(status_code=404)
        return configured[name]

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        if scheduler is not None and not scheduler.running:
            logger.warning("healthz failed: scheduler not running")
            raise HTTPException(status_code=503, detail="scheduler not running")
        probe = store.data_dir / ".healthz"
        try:
            probe.parent.mkdir(parents=True, exist_ok=True)
            probe.write_text("ok")
        except OSError as e:
            logger.warning("healthz failed: data dir %s not writable: %s", store.data_dir, e)
            raise HTTPException(status_code=503, detail="data dir not writable") from e
        return {"status": "ok"}

    @app.get("/")
    def index(request: Request) -> Response:
        rows = [
            {"config": config, "latest": runs[0] if (runs := store.list_runs(name)) else None}
            for name, config in configured.items()
        ]
        return templates.TemplateResponse(request, "index.html.j2", {"rows": rows})

    @app.get("/reports/{name}")
    def report(request: Request, name: str, page: int = Query(1, ge=1)) -> Response:
        config = _known(name)
        runs = store.list_runs(name)
        start = (page - 1) * PAGE_SIZE
        context = {
            "config": config,
            "runs": runs[start : start + PAGE_SIZE],
            "page": page,
            "has_more": len(runs) > start + PAGE_SIZE,
        }
        return templates.TemplateResponse(request, "report.html.j2", context)

    @app.get("/reports/{name}/fragments/runs")
    def runs_fragment(request: Request, name: str, page: int = Query(1, ge=1)) -> Response:
        config = _known(name)
        runs = store.list_runs(name)
        start = (page - 1) * PAGE_SIZE
        context = {
            "config": config,
            "runs": runs[start : start + PAGE_SIZE],
            "page": page,
            "has_more": len(runs) > start + PAGE_SIZE,
        }
        return templates.TemplateResponse(request, "_runs.html.j2", context)

    @app.get("/reports/{name}/latest")
    def latest(name: str) -> RedirectResponse:
        _known(name)
        record = store.latest_published(name)
        if record is None:
            raise HTTPException(status_code=404, detail="no published runs yet")
        return RedirectResponse(f"/reports/{name}/runs/{record.run_id}")

    @app.get("/reports/{name}/runs/{run_id}")
    def run_detail(request: Request, name: str, run_id: str) -> Response:
        _known(name)
        try:
            record = store.read_record(name, run_id)
        except StoreError as e:
            logger.warning("corrupt run record %s/%s: %s", name, run_id, e)
            raise HTTPException(status_code=404) from e
        if record is None:
            raise HTTPException(status_code=404)
        return templates.TemplateResponse(request, "run.html.j2", {"record": record})

    @app.get("/reports/{name}/runs/{run_id}/artifacts/{filename}")
    def artefact(name: str, run_id: str, filename: str) -> FileResponse:
        _known(name)
        path = store.artefact_path(name, run_id, filename)
        if path is None:
            raise HTTPException(status_code=404)
        return FileResponse(path)

    return app
