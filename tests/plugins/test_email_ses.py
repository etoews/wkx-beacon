from typing import Any

import boto3
import pytest
from botocore.stub import ANY, Stubber

from wkx_beacon.exceptions import NotifyError
from wkx_beacon.plugin import RunSummary
from wkx_beacon.plugins.email_ses import EmailSesConfig, EmailSesNotifier


def notifier() -> tuple[EmailSesNotifier, Stubber]:
    client = boto3.client(
        "sesv2", region_name="ap-southeast-2", aws_access_key_id="x", aws_secret_access_key="x"
    )
    stubber = Stubber(client)
    config = EmailSesConfig(to=["me@example.com"], sender="beacon@example.com")
    return EmailSesNotifier(config, ses_client=client), stubber


def summary(status: str = "ok", failed_stage: str | None = None) -> RunSummary:
    return RunSummary(
        report_name="platform-cost",
        run_id="20260704T070015Z",
        status=status,  # type: ignore[arg-type]
        headline="$7.59 NZD MTD",
        failed_stage=failed_stage,
        report_url="http://beacon.test/reports/platform-cost/latest",
    )


def expected_params(subject: str) -> dict[str, Any]:
    return {
        "FromEmailAddress": "beacon@example.com",
        "Destination": {"ToAddresses": ["me@example.com"]},
        "Content": {"Simple": {"Subject": {"Data": subject, "Charset": "UTF-8"}, "Body": ANY}},
    }


def test_ok_email_subject_carries_the_headline() -> None:
    n, stubber = notifier()
    stubber.add_response(
        "send_email",
        {"MessageId": "1"},
        expected_params("beacon · platform-cost · $7.59 NZD MTD"),
    )

    with stubber:
        n.notify(summary())

    stubber.assert_no_pending_responses()


def test_failed_email_subject_names_the_stage() -> None:
    n, stubber = notifier()
    stubber.add_response(
        "send_email",
        {"MessageId": "1"},
        expected_params("beacon · platform-cost · FAILED at collect"),
    )

    with stubber:
        n.notify(summary(status="failed", failed_stage="collect"))

    stubber.assert_no_pending_responses()


def test_degraded_email_subject_carries_the_headline() -> None:
    n, stubber = notifier()
    stubber.add_response(
        "send_email",
        {"MessageId": "1"},
        expected_params("beacon · platform-cost · DEGRADED · $7.59 NZD MTD"),
    )

    with stubber:
        n.notify(summary(status="degraded"))

    stubber.assert_no_pending_responses()


def test_failed_email_subject_falls_back_to_unknown_stage() -> None:
    n, stubber = notifier()
    stubber.add_response(
        "send_email",
        {"MessageId": "1"},
        expected_params("beacon · platform-cost · FAILED at unknown stage"),
    )

    with stubber:
        n.notify(summary(status="failed", failed_stage=None))

    stubber.assert_no_pending_responses()


def test_ses_errors_become_notify_errors() -> None:
    n, stubber = notifier()
    stubber.add_client_error(
        "send_email",
        "MessageRejected",
        expected_params=expected_params("beacon · platform-cost · $7.59 NZD MTD"),
    )

    with stubber, pytest.raises(NotifyError):
        n.notify(summary())
