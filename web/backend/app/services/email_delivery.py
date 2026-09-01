from __future__ import annotations

import logging
from typing import Protocol


LOGGER = logging.getLogger(__name__)


class EmailDelivery(Protocol):
    def send_password_reset(self, *, email: str, reset_url: str) -> None: ...


class DevelopmentEmailDelivery:
    """Development sink. It deliberately never logs or returns the reset URL."""

    def send_password_reset(self, *, email: str, reset_url: str) -> None:
        del reset_url
        LOGGER.info("AUTH_PASSWORD_RESET_DELIVERY_SKIPPED", extra={"email_domain": email.rpartition("@")[2]})


def get_email_delivery() -> EmailDelivery:
    return DevelopmentEmailDelivery()
