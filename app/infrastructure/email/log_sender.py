import logging

logger = logging.getLogger(__name__)


class LogEmailSender:
    def send_request_status_email(self, to_email: str, subject: str, body: str) -> None:
        logger.info("EMAIL to=%s subject=%s body=%s", to_email, subject, body)
