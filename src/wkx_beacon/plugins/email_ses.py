"""email-ses notifier: announce a run by email via Amazon SES v2."""

import logging
from typing import Any

from pydantic import BaseModel, Field

from wkx_beacon.exceptions import NotifyError
from wkx_beacon.plugin import RunSummary

logger = logging.getLogger(__name__)


class EmailSesConfig(BaseModel):
    model_config = {"extra": "forbid"}

    to: list[str] = Field(min_length=1)
    sender: str
    region: str = "ap-southeast-2"


class EmailSesNotifier:
    name = "email-ses"
    config_model = EmailSesConfig

    def __init__(self, config: EmailSesConfig, ses_client: Any | None = None) -> None:
        self.config = config
        self._ses_client = ses_client

    def _client(self) -> Any:
        if self._ses_client is None:
            import boto3

            self._ses_client = boto3.client("sesv2", region_name=self.config.region)
        return self._ses_client

    def _subject(self, summary: RunSummary) -> str:
        base = f"beacon · {summary.report_name}"
        if summary.status == "failed":
            return f"{base} · FAILED at {summary.failed_stage or 'unknown stage'}"
        if summary.status == "degraded":
            return f"{base} · DEGRADED · {summary.headline}"
        return f"{base} · {summary.headline}"

    def notify(self, summary: RunSummary) -> None:
        lines = [summary.headline, f"Status: {summary.status}"]
        if summary.error:
            lines.append(f"Error: {summary.error}")
        if summary.report_url:
            lines.append(f"Report: {summary.report_url}")
        try:
            self._client().send_email(
                FromEmailAddress=self.config.sender,
                Destination={"ToAddresses": self.config.to},
                Content={
                    "Simple": {
                        "Subject": {"Data": self._subject(summary)},
                        "Body": {"Text": {"Data": "\n".join(lines)}},
                    }
                },
            )
        except Exception as e:
            raise NotifyError(f"SES send failed: {e}") from e
        num_recipients = len(self.config.to)
        logger.info(
            "emailed run %s %s to %d recipients",
            summary.report_name,
            summary.run_id,
            num_recipients,
        )
