from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from time import perf_counter

from dailybrief.integrations.notifications.common import DeliveryResult, disabled_result, elapsed_ms, preview
from dailybrief.runtime.safety import env_bool, redact


def send_email(date: str, message: str, *, dry_run: bool = True) -> DeliveryResult:
    if dry_run:
        return DeliveryResult("email", "dry_run", True, preview(message), len(message))
    if not env_bool("EMAIL_ENABLED", False):
        return disabled_result("email", message, False, "EMAIL_ENABLED is false")

    host = os.environ.get("SMTP_HOST", "").strip()
    port = int(os.environ.get("SMTP_PORT") or 587)
    sender = os.environ.get("EMAIL_FROM", "").strip()
    recipients = _split_recipients(os.environ.get("EMAIL_TO", ""))
    if not host or not sender or not recipients:
        return DeliveryResult(
            "email",
            "failed",
            False,
            preview(message),
            len(message),
            error_message="SMTP_HOST, EMAIL_FROM, and EMAIL_TO are required.",
            error_category="config",
        )

    msg = EmailMessage()
    msg["Subject"] = f"DailyBrief {date}"
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    cc = _split_recipients(os.environ.get("EMAIL_CC", ""))
    bcc = _split_recipients(os.environ.get("EMAIL_BCC", ""))
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg.set_content(message)

    username = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    started = perf_counter()
    try:
        with smtplib.SMTP(host, port, timeout=float(os.environ.get("SMTP_TIMEOUT_SECONDS") or 15)) as smtp:
            if env_bool("SMTP_USE_TLS", True):
                smtp.starttls()
            if username or password:
                smtp.login(username, password)
            smtp.send_message(msg, to_addrs=recipients + cc + bcc)
    except Exception as exc:
        return DeliveryResult(
            "email",
            "failed",
            False,
            preview(message),
            len(message),
            error_message=redact(str(exc), (password,)),
            latency_ms=elapsed_ms(started),
            error_category="smtp",
        )
    return DeliveryResult("email", "sent", False, preview(message), len(message), latency_ms=elapsed_ms(started))


def _split_recipients(raw: str) -> list[str]:
    return [item.strip() for item in raw.replace(";", ",").split(",") if item.strip()]

