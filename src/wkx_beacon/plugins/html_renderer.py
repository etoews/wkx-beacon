"""html renderer: report data + the collector's template pack -> one self-contained page."""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from pydantic import BaseModel

from wkx_beacon.exceptions import RenderError
from wkx_beacon.plugin import Artefact, ReportData

logger = logging.getLogger(__name__)


class HtmlRendererConfig(BaseModel):
    model_config = {"extra": "forbid"}


class HtmlRenderer:
    name = "html"
    config_model = HtmlRendererConfig

    def __init__(self, config: HtmlRendererConfig) -> None:
        self.config = config

    def render(self, data: ReportData, template_dir: Path | None) -> list[Artefact]:
        if template_dir is None:
            raise RenderError(
                f"no template pack for report type {data.report_type!r}; "
                "the collector must provide template_dir()"
            )
        env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
        template_name = f"{data.report_type}.html.j2"
        try:
            html = env.get_template(template_name).render(data=data)
        except TemplateNotFound as e:
            raise RenderError(f"template {template_name!r} not found in {template_dir}") from e
        except Exception as e:
            raise RenderError(f"rendering {template_name!r} failed: {e}") from e
        logger.info("rendered %s (%d bytes)", template_name, len(html))
        return [Artefact(filename="report.html", media_type="text/html", content=html.encode())]
