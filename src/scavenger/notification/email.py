"""Email notification for Scavenger."""

import logging
import os
import smtplib
from dataclasses import dataclass
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from scavenger.core.config import Config, ConfigStorage, NotificationConfig
from scavenger.notification.report import ReportGenerator

logger = logging.getLogger("scavenger.email")


@dataclass
class EmailResult:
    """Result of email sending."""

    success: bool
    message: str


class EmailSender:
    """Send email notifications."""

    def __init__(self, config: Optional[NotificationConfig] = None):
        if config is None:
            config_storage = ConfigStorage()
            full_config = config_storage.load()
            config = full_config.notification
        self.config = config

    def _get_smtp_password(self) -> Optional[str]:
        """Get SMTP password from environment variable."""
        env_var = self.config.smtp.password_env
        return os.environ.get(env_var)

    def is_configured(self) -> bool:
        """Check if email is properly configured."""
        if not self.config.email:
            return False
        if not self.config.smtp.host:
            return False
        if not self.config.smtp.username:
            return False
        if not self._get_smtp_password():
            return False
        return True

    def send_email(
        self,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        to_email: Optional[str] = None,
    ) -> EmailResult:
        """Send an email.

        Args:
            subject: Email subject
            body_text: Plain text body
            body_html: Optional HTML body
            to_email: Recipient email (default: configured email)

        Returns:
            EmailResult indicating success or failure
        """
        to_email = to_email or self.config.email

        if not to_email:
            return EmailResult(False, "No recipient email configured")

        password = self._get_smtp_password()
        if not password:
            return EmailResult(False, f"SMTP password not found in {self.config.smtp.password_env}")

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.config.smtp.username
            msg["To"] = to_email

            # Attach plain text
            msg.attach(MIMEText(body_text, "plain", "utf-8"))

            # Attach HTML if provided
            if body_html:
                msg.attach(MIMEText(body_html, "html", "utf-8"))

            # Connect and send
            logger.info(f"Connecting to SMTP server {self.config.smtp.host}:{self.config.smtp.port}")

            with smtplib.SMTP(self.config.smtp.host, self.config.smtp.port) as server:
                server.starttls()
                server.login(self.config.smtp.username, password)
                server.sendmail(
                    self.config.smtp.username,
                    [to_email],
                    msg.as_string(),
                )

            logger.info(f"Email sent successfully to {to_email}")
            return EmailResult(True, f"Email sent to {to_email}")

        except smtplib.SMTPAuthenticationError:
            # Check if using Gmail
            is_gmail = "gmail" in self.config.smtp.host.lower()
            if is_gmail:
                error_msg = (
                    "SMTP authentication failed. "
                    "Gmail requires an App Password (not your regular password). "
                    "Generate one at: https://myaccount.google.com/apppasswords"
                )
            else:
                error_msg = "SMTP authentication failed. Check username and password."
            logger.error(error_msg)
            return EmailResult(False, error_msg)
        except smtplib.SMTPException as e:
            error_msg = f"SMTP error: {str(e)}"
            logger.error(error_msg)
            return EmailResult(False, error_msg)
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            logger.exception(error_msg)
            return EmailResult(False, error_msg)

    def send_daily_report(self, target_date: Optional[date] = None) -> EmailResult:
        """Send the daily report email.

        Args:
            target_date: Date for the report (default: today)

        Returns:
            EmailResult indicating success or failure
        """
        if not self.is_configured():
            return EmailResult(False, "Email not configured")

        if target_date is None:
            target_date = date.today()

        report_generator = ReportGenerator()

        subject = f"[Scavenger] Daily Report - {target_date.isoformat()}"
        body_text = report_generator.generate_text_report(target_date)
        body_html = report_generator.generate_html_report(target_date)

        return self.send_email(subject, body_text, body_html)

    def send_test_email(self) -> EmailResult:
        """Send a test email to verify configuration."""
        if not self.is_configured():
            return EmailResult(False, "Email not configured")

        subject = "[Scavenger] Test Email"
        body_text = """
This is a test email from Scavenger.

If you received this email, your email configuration is working correctly.

---
Scavenger - Automated task runner for Claude Code
"""
        body_html = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: sans-serif; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; }
        h1 { color: #4CAF50; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Scavenger Test Email</h1>
        <p>This is a test email from Scavenger.</p>
        <p>If you received this email, your email configuration is working correctly.</p>
        <hr>
        <p style="color: #666; font-size: 12px;">
            Scavenger - Automated task runner for Claude Code
        </p>
    </div>
</body>
</html>
"""
        return self.send_email(subject, body_text, body_html)
