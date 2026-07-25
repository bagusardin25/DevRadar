"""Email delivery providers (console, Resend, SMTP)."""

from __future__ import annotations

import asyncio
import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage as StdEmailMessage
from typing import Protocol

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EmailMessage:
    to_hash: str  # never log raw email
    subject: str
    body_text: str
    idempotency_key: str
    # Plaintext recipient — only for real providers; never log this field.
    to_address: str | None = None
    body_html: str | None = None


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
        logger.info(
            "email_console_send",
            extra={
                "to_hash_prefix": message.to_hash[:8],
                "subject": message.subject,
                "idempotency_key": message.idempotency_key,
            },
        )
        return f"console-{message.idempotency_key[:12]}"


class ResendEmailProvider:
    """Send via Resend HTTP API (https://resend.com)."""

    def __init__(self, *, api_key: str, from_address: str) -> None:
        self._api_key = api_key
        self._from = from_address

    async def send(self, message: EmailMessage) -> str:
        if not message.to_address:
            raise ValueError("ResendEmailProvider requires to_address")
        payload: dict[str, object] = {
            "from": self._from,
            "to": [message.to_address],
            "subject": message.subject,
            "text": message.body_text,
        }
        if message.body_html:
            payload["html"] = message.body_html
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": message.idempotency_key[:256],
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                json=payload,
                headers=headers,
            )
            if resp.status_code >= 400:
                logger.error(
                    "email_resend_failed",
                    extra={
                        "status": resp.status_code,
                        "to_hash_prefix": message.to_hash[:8],
                    },
                )
                resp.raise_for_status()
            data = resp.json()
            msg_id = str(data.get("id") or f"resend-{message.idempotency_key[:12]}")
            logger.info(
                "email_resend_send",
                extra={
                    "to_hash_prefix": message.to_hash[:8],
                    "provider_id": msg_id,
                    "idempotency_key": message.idempotency_key,
                },
            )
            return msg_id


class SmtpEmailProvider:
    """Send via SMTP (stdlib smtplib in a worker thread)."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        from_address: str,
        use_tls: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from = from_address
        self._use_tls = use_tls

    def _send_sync(self, message: EmailMessage) -> str:
        if not message.to_address:
            raise ValueError("SmtpEmailProvider requires to_address")
        msg = StdEmailMessage()
        msg["From"] = self._from
        msg["To"] = message.to_address
        msg["Subject"] = message.subject
        msg.set_content(message.body_text)
        if message.body_html:
            msg.add_alternative(message.body_html, subtype="html")

        if self._use_tls:
            with smtplib.SMTP(self._host, self._port, timeout=30) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                if self._username:
                    smtp.login(self._username, self._password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(self._host, self._port, timeout=30) as smtp:
                if self._username:
                    smtp.login(self._username, self._password)
                smtp.send_message(msg)
        return f"smtp-{message.idempotency_key[:12]}"

    async def send(self, message: EmailMessage) -> str:
        msg_id = await asyncio.to_thread(self._send_sync, message)
        logger.info(
            "email_smtp_send",
            extra={
                "to_hash_prefix": message.to_hash[:8],
                "provider_id": msg_id,
                "idempotency_key": message.idempotency_key,
            },
        )
        return msg_id


def build_email_provider(settings: Settings) -> EmailProvider:
    """Factory from EMAIL_PROVIDER env (console | resend | smtp)."""
    provider = (settings.email_provider or "console").strip().lower()
    if provider == "resend":
        if not (settings.resend_api_key or "").strip():
            logger.warning("EMAIL_PROVIDER=resend but RESEND_API_KEY empty; using console")
            return ConsoleEmailProvider()
        return ResendEmailProvider(
            api_key=settings.resend_api_key.strip(),
            from_address=settings.email_from,
        )
    if provider == "smtp":
        if not (settings.smtp_host or "").strip():
            logger.warning("EMAIL_PROVIDER=smtp but SMTP_HOST empty; using console")
            return ConsoleEmailProvider()
        return SmtpEmailProvider(
            host=settings.smtp_host.strip(),
            port=int(settings.smtp_port or 587),
            username=(settings.smtp_user or "").strip(),
            password=(settings.smtp_password or "").strip(),
            from_address=settings.email_from,
            use_tls=bool(settings.smtp_tls),
        )
    return ConsoleEmailProvider()
