import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class SmtpEmailSender:
    def send_request_status_email(self, to_email: str, subject: str, body: str) -> None:
        settings = get_settings()
        msg = EmailMessage()
        msg["From"] = settings.email_from
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)

        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                if settings.smtp_user:
                    server.starttls()
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
        except Exception:
            logger.exception("Failed to send email to %s", to_email)
            raise
