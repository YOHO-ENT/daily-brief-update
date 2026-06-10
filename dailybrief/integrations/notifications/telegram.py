from __future__ import annotations

import os
from time import perf_counter

import httpx

from dailybrief.integrations.notifications.common import DeliveryResult, disabled_result, elapsed_ms, preview, truncate
from dailybrief.runtime.safety import env_bool, redact


def send_telegram(message: str, *, dry_run: bool = True) -> DeliveryResult:
    payload_text, truncated = truncate(message, int(os.environ.get("TELEGRAM_MESSAGE_MAX_CHARS") or 3500))
    if dry_run:
        return DeliveryResult("telegram", "dry_run", True, preview(payload_text), len(payload_text), truncated=truncated)
    if not env_bool("TELEGRAM_ENABLED", False):
        return disabled_result("telegram", payload_text, False, "TELEGRAM_ENABLED is false")
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not bot_token or not chat_id:
        return DeliveryResult(
            "telegram",
            "failed",
            False,
            preview(payload_text),
            len(payload_text),
            error_message="TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required.",
            truncated=truncated,
            error_category="config",
        )
    payload = {
        "chat_id": chat_id,
        "text": payload_text,
        "disable_web_page_preview": False,
    }
    parse_mode = os.environ.get("TELEGRAM_PARSE_MODE", "").strip()
    if parse_mode:
        payload["parse_mode"] = parse_mode
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    started = perf_counter()
    try:
        response = httpx.post(url, json=payload, timeout=float(os.environ.get("TELEGRAM_TIMEOUT_SECONDS") or 10))
        response.raise_for_status()
    except Exception as exc:
        return DeliveryResult(
            "telegram",
            "failed",
            False,
            preview(payload_text),
            len(payload_text),
            error_message=redact(str(exc), (bot_token,)),
            truncated=truncated,
            latency_ms=elapsed_ms(started),
            error_category="http",
        )
    return DeliveryResult("telegram", "sent", False, preview(payload_text), len(payload_text), truncated=truncated, latency_ms=elapsed_ms(started))

