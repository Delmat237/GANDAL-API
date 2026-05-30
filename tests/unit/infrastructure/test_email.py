from app.infrastructure.email.log_sender import LogEmailSender


def test_log_email_sender_does_not_raise():
    sender = LogEmailSender()
    sender.send_request_status_email("a@b.com", "Subject", "Body")
