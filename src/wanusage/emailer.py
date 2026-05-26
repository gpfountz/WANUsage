from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from wanusage.config import EmailConfig


class EmailError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmailSender:
    config: EmailConfig
    timeout_seconds: int = 30

    def send_report(self, recipient: str, subject: str, body: str) -> None:
        self._validate_config()

        message: EmailMessage = EmailMessage()
        message["From"] = self.config.from_address
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)

        try:
            with smtplib.SMTP(
                self.config.smtp_host,
                self.config.smtp_port,
                timeout=self.timeout_seconds,
            ) as smtp:
                if self.config.use_tls:
                    smtp.starttls()
                if self.config.username:
                    smtp.login(self.config.username, self.config.password)
                smtp.send_message(message)
        except OSError as error:
            raise EmailError(f"Could not send email: {error}") from error
        except smtplib.SMTPException as error:
            raise EmailError(f"Could not send email: {error}") from error

    def _validate_config(self) -> None:
        missing_values: list[str] = []
        if not self.config.smtp_host:
            missing_values.append("email.smtp_host")
        if not self.config.from_address:
            missing_values.append("email.from_address")
        if self.config.username and not self.config.password:
            missing_values.append("email.password")

        if missing_values:
            joined_values: str = ", ".join(missing_values)
            raise EmailError(f"Missing email config value(s): {joined_values}")
