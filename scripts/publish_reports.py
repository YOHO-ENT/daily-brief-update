#!/usr/bin/env python3
"""Publish DailyBrief static report artifacts to the Research Hub mount."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dailybrief.runtime.safety import redact_url  # noqa: E402
from dailybrief.storage.artifacts import latest_report_date, paths_for_date  # noqa: E402

SKIP_NAMES = {".DS_Store"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish DailyBrief static reports.")
    parser.add_argument("--source", default="daily_reports", help="Source daily_reports directory.")
    parser.add_argument(
        "--target",
        default="/opt/research-stack/runtime/dailybrief-reports",
        help="Target directory served by Research Hub Caddy.",
    )
    parser.add_argument("--public-url", default="", help="Public base URL for the report mount.")
    parser.add_argument("--health-file", default="health.json", help="Health JSON filename written in target.")
    args = parser.parse_args(argv)

    source = Path(args.source).expanduser().resolve()
    target = Path(args.target).expanduser().resolve()
    public_url = args.public_url.strip()

    if not source.is_dir():
        raise FileNotFoundError(f"source report directory not found: {source}")
    latest = latest_report_date(source)
    if not latest:
        raise FileNotFoundError(f"no dated DailyBrief reports found in {source}")

    sync_static_reports(source, target)
    health = build_health_payload(source=source, target=target, latest=latest, public_url=public_url)
    write_json_atomic(target / args.health_file, health)
    normalize_permissions(target)
    print(json.dumps(health, ensure_ascii=False, sort_keys=True))
    return 0


def sync_static_reports(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for item in source.rglob("*"):
        relative = item.relative_to(source)
        if any(part in SKIP_NAMES for part in relative.parts):
            continue
        destination = target / relative
        if item.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)


def build_health_payload(*, source: Path, target: Path, latest: str, public_url: str) -> dict:
    target_paths = paths_for_date(latest, target)
    source_paths = paths_for_date(latest, source)
    artifacts = {
        "index": (target / "index.html").exists(),
        "archive": (target / "archive.html").exists(),
        "html": target_paths.html.exists(),
        "json": target_paths.report_json.exists(),
        "articles": target_paths.articles_json.exists(),
    }
    missing = [name for name, exists in artifacts.items() if not exists]
    status = "ok" if not missing else "warning"
    base_url = public_url.rstrip("/") + "/" if public_url else ""
    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latest_report_date": latest,
        "latest_report_url": urljoin(base_url, f"{latest}/{latest}.html") if base_url else "",
        "public_url": redact_url(base_url) or "",
        "source_dir": str(source),
        "target_dir": str(target),
        "artifacts": artifacts,
        "source_latest_html_bytes": source_paths.html.stat().st_size if source_paths.html.exists() else 0,
        "missing": missing,
    }


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def normalize_permissions(root: Path) -> None:
    root.chmod(0o755)
    for item in root.rglob("*"):
        if item.is_dir():
            item.chmod(0o755)
        elif item.is_file():
            item.chmod(0o644)


if __name__ == "__main__":
    raise SystemExit(main())
