from __future__ import annotations

import os
from typing import Any

from dailybrief.integrations.notifications.common import DeliveryResult
from dailybrief.integrations.notifications.email import send_email
from dailybrief.integrations.notifications.slack import send_slack
from dailybrief.integrations.notifications.telegram import send_telegram
from dailybrief.storage.artifacts import load_report, report_url


DEFAULT_CHANNELS = ("slack", "telegram", "email")


def build_notification_message(report: dict[str, Any], date: str, html_link: str) -> str:
    hero = str(report.get("hero_headline") or "").strip()
    overview = str(report.get("daily_overview") or "").strip()
    top_items = _top_briefs(report)
    lines = [f"DailyBrief {date}"]
    if hero:
        lines.append(hero)
    if overview:
        lines.extend(["", overview])
    if top_items:
        lines.extend(["", "Top 3"])
        for i, item in enumerate(top_items, 1):
            title = str(item.get("title") or "").strip()
            source = str(item.get("source") or "").strip()
            summary = str(item.get("summary") or "").strip()
            label = f"{title} ({source})" if source else title
            lines.append(f"{i}. {label}")
            if summary:
                lines.append(f"   {summary}")
    lines.extend(["", f"HTML: {html_link}"])
    return "\n".join(lines)


def notify_report(
    date: str,
    *,
    channels: tuple[str, ...] = DEFAULT_CHANNELS,
    dry_run: bool = True,
    confirm_send: bool = False,
) -> list[DeliveryResult]:
    if not dry_run and not confirm_send:
        raise RuntimeError("Live notification requires --confirm-send.")
    report = load_report(date)
    html_link = report_url(date, base_url=os.environ.get("DAILYBRIEF_REPORT_BASE_URL"))
    message = build_notification_message(report, date, html_link)
    results: list[DeliveryResult] = []
    for channel in channels:
        normalized = channel.strip().lower()
        if normalized == "slack":
            results.append(send_slack(message, dry_run=dry_run))
        elif normalized == "telegram":
            results.append(send_telegram(message, dry_run=dry_run))
        elif normalized == "email":
            results.append(send_email(date, message, dry_run=dry_run))
        elif normalized:
            results.append(
                DeliveryResult(
                    channel=normalized,
                    status="failed",
                    dry_run=dry_run,
                    message_preview="",
                    payload_chars=0,
                    error_message=f"Unknown notification channel: {normalized}",
                    error_category="config",
                )
            )
    return results


def _top_briefs(report: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    items: list[tuple[int, int, dict[str, Any]]] = []
    order = 0
    for key in ("tech_briefs", "finance_briefs", "politics_briefs"):
        for item in report.get(key) or []:
            if isinstance(item, dict):
                importance = _importance(item.get("importance"))
                items.append((importance, order, item))
                order += 1
    items.sort(key=lambda row: (-row[0], row[1]))
    return [item for _, _, item in items[:limit]]


def _importance(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0

