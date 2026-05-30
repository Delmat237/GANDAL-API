from typing import Protocol


class EmailPort(Protocol):
    def send_request_status_email(
        self,
        to_email: str,
        subject: str,
        body: str,
    ) -> None: ...
