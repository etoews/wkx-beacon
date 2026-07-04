"""CLI entry point. Run with `uv run beacon` or `python -m wkx_beacon`."""

import logging

import typer

from wkx_beacon._logging import configure as configure_logging

app = typer.Typer(help="Reports about the platform beacon runs on.", no_args_is_help=True)
logger = logging.getLogger(__name__)


@app.callback()
def _root() -> None:
    configure_logging()


@app.command()
def serve() -> None:
    """Run the scheduler and the web viewer. The container entrypoint."""
    import uvicorn

    from wkx_beacon.bootstrap import bootstrap
    from wkx_beacon.scheduler import build_scheduler
    from wkx_beacon.web.app import create_app

    context = bootstrap()
    scheduler = build_scheduler(context.reports, context.store, context.settings.base_url)
    scheduler.start()
    web_app = create_app(context.store, [r.config for r in context.reports], scheduler=scheduler)
    try:
        uvicorn.run(
            web_app,
            host=context.settings.host,
            port=context.settings.port,
            log_config=None,
        )
    finally:
        scheduler.shutdown(wait=False)


@app.command()
def run(report_name: str) -> None:
    """One-shot pipeline run, for development and debugging."""
    from wkx_beacon.bootstrap import bootstrap
    from wkx_beacon.pipeline import execute

    context = bootstrap()
    matches = [r for r in context.reports if r.config.name == report_name]
    if not matches:
        names = ", ".join(r.config.name for r in context.reports)
        typer.echo(f"unknown report {report_name!r}; configured: {names}", err=True)
        raise typer.Exit(code=1)
    record = execute(matches[0], context.store, context.settings.base_url)
    typer.echo(f"{record.run_id} {record.status} {record.headline}")
    if record.status == "failed":
        raise typer.Exit(code=1)


@app.command()
def validate() -> None:
    """Validate config and plugin discovery; usable in CI."""
    from wkx_beacon.bootstrap import bootstrap

    context = bootstrap()
    for report in context.reports:
        config = report.config
        typer.echo(
            f"{config.name}: {config.collector} -> {', '.join(config.renderers)}"
            f" -> {', '.join(config.notifiers)} ({config.schedule} {config.timezone})"
        )
    typer.echo("configuration valid")


def main() -> None:
    """Console-script entry point referenced from pyproject.toml."""
    app()


if __name__ == "__main__":
    main()
