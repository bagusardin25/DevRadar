"""Email delivery providers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EmailMessage:
    to_hash: str  # never log raw email
    subject: str
    body_text: str
    idempotency_key: str


class EmailProvider(Protocol):
    async def send(self, message: EmailMessage) -> str:
        """Return provider message id."""
        ...


class ConsoleEmailProvider:
    """Dev provider: log redacted delivery only."""

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> str:
        self.sent.append(message)
        # Never log email ciphertext/token content
        logger.info(
            "email_console_send",
            extra={
                "to_hash_prefix": message.to_hash[:8],
                "subject": message.subject,
                "idempotency_key": message.idempotency_key,
            },
        )
        return f"console-{message.idempotency_key[:12]}"
