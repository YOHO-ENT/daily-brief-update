from __future__ import annotations

import os
from time import perf_counter

import httpx

from dailybrief.integrations.notifications.common import DeliveryResult, disabled_result, elapsed_ms, preview, truncate
from dailybrief.runtime.safety import env_bool, redact


def send_slack(message: str, *, dry_run: bool = True) -> DeliveryResult:
    limit = int(os.environ.get("SLACK_MESSAGE_MAX_CHARS") or 3500)
    payload_text, truncated = truncate(message, min(max(limit, 1), 4000))
    if dry_run:
        return DeliveryResult("slack", "dry_run", True, preview(payload_text), len(payload_text), truncated=truncated)
    if not env_bool("SLACK_ENABLED", False):
        return disabled_result("slack", payload_text, False, "SLACK_ENABLED is false")
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return DeliveryResult(
            "slack",
            "failed",
            False,
            preview(payload_text),
            len(payload_text),
            error_message="SLACK_WEBHOOK_URL is required.",
            truncated=truncated,
            error_category="config",
        )
    payload = {"text": payload_text}
    channel = os.environ.get("SLACK_CHANNEL", "").strip()
    if channel:
        payload["channel"] = channel
    started = perf_counter()
    try:
        response = httpx.post(webhook_url, json=payload, timeout=float(os.environ.get("SLACK_TIMEOUT_SECONDS") or 10))
        response.raise_for_status()
    except Exception as exc:
        return DeliveryResult(
            "slack",
            "failed",
            False,
            preview(payload_text),
            len(payload_text),
            error_message=redact(str(exc), (webhook_url,)),
            truncated=truncated,
            latency_ms=elapsed_ms(started),
            error_category="http",
        )
    return DeliveryResult("slack", "sent", False, preview(payload_text), len(payload_text), truncated=truncated, latency_ms=elapsed_ms(started))

