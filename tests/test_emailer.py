from __future__ import annotations

import ssl
from collections.abc import Iterator
from email.message import EmailMessage

import pytest

from wanusage.config import EmailConfig
from wanusage.emailer import EmailError, EmailSender


class FakeSmtp:
    instances: list[FakeSmtp] = []

    def __init__(self, host: str, port: int, *, timeout: int) -> None:
        self.host: str = host
        self.port: int = port
        self.timeout: int = timeout
        self.started_tls: bool = False
        self.tls_context: ssl.SSLContext | None = None
        self.login_args: tuple[str, str] | None = None
        self.sent_message: EmailMessage | None = None
        FakeSmtp.instances.append(self)

    def __enter__(self) -> FakeSmtp:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def starttls(self, *, context: ssl.SSLContext) -> None:
        self.started_tls = True
        self.tls_context = context

    def login(self, username: str, password: str) -> None:
        self.login_args = (username, password)

    def send_message(self, message: EmailMessage) -> None:
        self.sent_message = message


@pytest.fixture(autouse=True)
def reset_fake_smtp() -> Iterator[None]:
    FakeSmtp.instances = []
    yield
    FakeSmtp.instances = []


def test_send_report_uses_smtp_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("smtplib.SMTP", FakeSmtp)
    sender = EmailSender(
        EmailConfig(
            smtp_host="smtp.example.com",
            smtp_port=587,
            username="mailer",
            password="secret",
            from_address="wan@example.com",
            to_address="recipient@example.com",
            use_tls=True,
        )
    )

    sender.send_report(
        subject="WAN report",
        body="Report body",
    )

    instance: FakeSmtp = FakeSmtp.instances[0]
    assert instance.host == "smtp.example.com"
    assert instance.port == 587
    assert instance.started_tls is True
    assert instance.tls_context is not None
    assert instance.tls_context.verify_mode == ssl.CERT_REQUIRED
    assert instance.tls_context.check_hostname is True
    assert instance.login_args == ("mailer", "secret")
    assert instance.sent_message is not None
    assert instance.sent_message["From"] == "wan@example.com"
    assert instance.sent_message["To"] == "recipient@example.com"
    assert instance.sent_message["Subject"] == "WAN report"
    assert instance.sent_message.get_content() == "Report body\n"


def test_send_report_rejects_missing_smtp_host() -> None:
    sender = EmailSender(
        EmailConfig(
            smtp_host="",
            smtp_port=587,
            username="",
            password="",
            from_address="wan@example.com",
            to_address="recipient@example.com",
            use_tls=True,
        )
    )

    with pytest.raises(EmailError, match="email.smtp_host"):
        sender.send_report(
            subject="WAN report",
            body="Report body",
        )


def test_send_report_without_username_skips_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("smtplib.SMTP", FakeSmtp)
    sender = EmailSender(
        EmailConfig(
            smtp_host="smtp.example.com",
            smtp_port=25,
            username="",
            password="",
            from_address="wan@example.com",
            to_address="recipient@example.com",
            use_tls=False,
        )
    )

    sender.send_report(
        subject="WAN report",
        body="Report body",
    )

    instance: FakeSmtp = FakeSmtp.instances[0]
    assert instance.started_tls is False
    assert instance.login_args is None


def test_send_report_rejects_authenticated_smtp_without_tls() -> None:
    sender = EmailSender(
        EmailConfig(
            smtp_host="smtp.example.com",
            smtp_port=25,
            username="mailer",
            password="secret",
            from_address="wan@example.com",
            to_address="recipient@example.com",
            use_tls=False,
        )
    )

    with pytest.raises(EmailError, match="Authenticated SMTP requires"):
        sender.send_report(
            subject="WAN report",
            body="Report body",
        )


def test_send_report_rejects_missing_to_address() -> None:
    sender = EmailSender(
        EmailConfig(
            smtp_host="smtp.example.com",
            smtp_port=587,
            username="",
            password="",
            from_address="wan@example.com",
            to_address="",
            use_tls=True,
        )
    )

    with pytest.raises(EmailError, match="email.to_address"):
        sender.send_report(
            subject="WAN report",
            body="Report body",
        )
