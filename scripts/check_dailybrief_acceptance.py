#!/usr/bin/env python3
"""Read-only DailyBrief artifact acceptance checks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dailybrief.runtime.safety import contains_secret, redact  # noqa: E402
from dailybrief.storage.artifacts import paths_for_date  # noqa: E402


REQUIRED_REPORT_KEYS = {
    "hero_headline",
    "daily_overview",
    "tech_briefs",
    "finance_briefs",
    "politics_briefs",
    "editor_note",
    "keywords",
}
REQUIRED_ARTICLE_KEYS = {"sourceId", "title", "url", "category", "source"}
ADVICE_RE = re.compile(
    r"(?<!不构成)投资建议|建议(?:买入|卖出|持有)|目标价|"
    r"\b(?:strong\s+buy|strong\s+sell|should\s+buy|should\s+sell|price\s+target)\b",
    re.I,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check DailyBrief artifact acceptance.")
    parser.add_argument("--days", type=int, default=5, help="Required passing report days.")
    parser.add_argument("--output-dir", default="daily_reports", help="DailyBrief output directory.")
    parser.add_argument("--output-json", action="store_true", help="Print JSON output.")
    args = parser.parse_args(argv)
    payload = check_dailybrief_acceptance(output_dir=Path(args.output_dir), required_days=args.days)
    if args.output_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"status={payload['status']}")
        print(f"observed_report_days={payload['observed_report_days']}")
        print(f"required_days={payload['required_days']}")
        for warning in payload["warnings"]:
            print(f"warning={warning}")
    return 0 if payload["status"] in {"passed", "pending"} else 2


def check_dailybrief_acceptance(*, output_dir: Path, required_days: int = 5) -> dict[str, Any]:
    required_days = max(1, int(required_days))
    dates = _report_dates(output_dir)
    selected = dates[-required_days:]
    checks = [_check_day(date, output_dir) for date in selected]
    warnings: list[str] = []
    if len(checks) < required_days:
        warnings.append("acceptance_window_incomplete")
    failed_dates = [item["date"] for item in checks if item["status"] != "passed"]
    if failed_dates:
        warnings.append(f"dailybrief_report_failures={','.join(failed_dates)}")
    if failed_dates:
        status = "failed"
    elif len(checks) < required_days:
        status = "pending"
    else:
        status = "passed"
    return {
        "status": status,
        "required_days": required_days,
        "observed_report_days": len(checks),
        "output_dir": str(output_dir),
        "daily_checks": checks,
        "warnings": warnings,
    }


def _report_dates(output_dir: Path) -> list[str]:
    if not output_dir.exists():
        return []
    return sorted(
        item.name
        for item in output_dir.iterdir()
        if item.is_dir() and len(item.name) == 10 and (item / f"{item.name}.html").exists()
    )


def _check_day(date: str, output_dir: Path) -> dict[str, Any]:
    paths = paths_for_date(date, output_dir)
    artifacts = {
        "html": paths.html.exists(),
        "json": paths.report_json.exists(),
        "articles": paths.articles_json.exists(),
    }
    warnings: list[str] = []
    missing = [name for name, exists in artifacts.items() if not exists]
    if missing:
        warnings.append(f"missing_artifacts={','.join(missing)}")
    report = _read_json(paths.report_json)
    articles_payload = _read_json(paths.articles_json)
    schema_valid, schema_error = _validate_report_schema(report)
    articles_valid, articles_error, article_count = _validate_articles(articles_payload)
    if not schema_valid:
        warnings.append("report_schema_invalid")
    if not articles_valid:
        warnings.append("articles_schema_invalid")
    brief_count = _brief_count(report)
    if brief_count <= 0:
        warnings.append("brief_count_zero")
    if article_count <= 0:
        warnings.append("article_count_zero")
    text_blob = _artifact_text(paths)
    if contains_secret(text_blob):
        warnings.append("secret_pattern_detected")
    if ADVICE_RE.search(text_blob):
        warnings.append("investment_advice_language_detected")
    return {
        "date": date,
        "status": "passed" if not warnings else "failed",
        "artifacts": artifacts,
        "hero_headline": str(report.get("hero_headline") or "") if isinstance(report, dict) else "",
        "brief_count": brief_count,
        "article_count": article_count,
        "report_contract": {
            "schema_valid": schema_valid,
            "schema_error": schema_error,
            "articles_valid": articles_valid,
            "articles_error": articles_error,
            "secret_scan_pass": "secret_pattern_detected" not in warnings,
            "no_advice_terms": "investment_advice_language_detected" not in warnings,
        },
        "warnings": warnings,
    }


def _read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_error": redact(exc)}


def _validate_report_schema(report: Any) -> tuple[bool, str | None]:
    if not isinstance(report, dict):
        return False, "report_json_not_object"
    missing = sorted(REQUIRED_REPORT_KEYS - set(report))
    if missing:
        return False, f"missing_keys={','.join(missing)}"
    for key in ("tech_briefs", "finance_briefs", "politics_briefs", "keywords"):
        if not isinstance(report.get(key), list):
            return False, f"{key}_not_list"
    return True, None


def _validate_articles(payload: Any) -> tuple[bool, str | None, int]:
    if not isinstance(payload, dict):
        return False, "articles_json_not_object", 0
    articles = payload.get("articles")
    if not isinstance(articles, list):
        return False, "articles_not_list", 0
    for i, article in enumerate(articles):
        if not isinstance(article, dict):
            return False, f"articles[{i}]_not_object", len(articles)
        missing = REQUIRED_ARTICLE_KEYS - set(article)
        if missing:
            return False, f"articles[{i}]_missing={','.join(sorted(missing))}", len(articles)
    return True, None, len(articles)


def _brief_count(report: Any) -> int:
    if not isinstance(report, dict):
        return 0
    return sum(len(report.get(key) or []) for key in ("tech_briefs", "finance_briefs", "politics_briefs"))


def _artifact_text(paths) -> str:
    chunks = []
    for path in (paths.html, paths.report_json, paths.articles_json, paths.markdown):
        if path.exists():
            try:
                chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                pass
    return "\n".join(chunks)


if __name__ == "__main__":
    raise SystemExit(main())

