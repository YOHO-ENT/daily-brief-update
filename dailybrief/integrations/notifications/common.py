from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any

from dailybrief.runtime.safety import redact


@dataclass(frozen=True)
class DeliveryResult:
    channel: str
    status: str
    dry_run: bool
    message_preview: str
    payload_chars: int
    error_message: str | None = None
    truncated: bool = False
    latency_ms: int = 0
    error_category: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


def preview(message: str, limit: int = 240) -> str:
    return redact(message[:limit])


def truncate(message: str, limit: int) -> tuple[str, bool]:
    limit = max(1, int(limit))
    if len(message) <= limit:
        return message, False
    suffix = "\n\n[truncated] Open the HTML report for full context."
    if limit <= len(suffix):
        return message[:limit], True
    return f"{message[: limit - len(suffix)]}{suffix}", True


def elapsed_ms(started: float) -> int:
    return max(0, int((perf_counter() - started) * 1000))


def disabled_result(channel: str, message: str, dry_run: bool, reason: str) -> DeliveryResult:
    return DeliveryResult(
        channel=channel,
        status="disabled",
        dry_run=dry_run,
        message_preview=preview(message),
        payload_chars=len(message),
        error_message=redact(reason),
        error_category="gate",
    )

