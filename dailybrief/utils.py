from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - dependency is declared, fallback is defensive
    load_dotenv = None


CONFIG_FILE = ".daily-brief-config"
TZ_ALIASES = {
    "China/Shanghai": "Asia/Shanghai",
    "China/Beijing": "Asia/Shanghai",
    "Asia/Beijing": "Asia/Shanghai",
    "PRC": "Asia/Shanghai",
}


def _is_repo_root(path: Path) -> bool:
    return (path / "sources.config.json").exists()


def _walk_for_repo_root(start: Path) -> Path | None:
    start = start.resolve()
    candidates = [start, *start.parents]
    for candidate in candidates:
        if _is_repo_root(candidate):
            return candidate
    return None


def resolve_repo_root() -> Path:
    env_root = os.environ.get("DAILYBRIEF_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()

    cwd_root = _walk_for_repo_root(Path.cwd())
    if cwd_root is not None:
        return cwd_root

    cfg_path = Path.home() / CONFIG_FILE
    if cfg_path.exists():
        cfg_root = Path(cfg_path.read_text(encoding="utf-8").strip()).expanduser().resolve()
        if _is_repo_root(cfg_root):
            return cfg_root

    package_root = Path(__file__).resolve().parents[1]
    package_repo = _walk_for_repo_root(package_root)
    if package_repo is not None:
        return package_repo

    return package_root


REPO_ROOT = resolve_repo_root()
OUTPUT_DIR = REPO_ROOT / "daily_reports"
LOG_DIR = REPO_ROOT / "logs"


def load_env() -> None:
    env_path = REPO_ROOT / ".env.local"
    if load_dotenv is not None:
        load_dotenv(env_path, override=False)
        return
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def report_locale() -> str:
    return "en" if os.environ.get("REPORT_LOCALE", "").strip() == "en" else "zh"


def get_report_tz() -> str | None:
    tz_name = os.environ.get("REPORT_TZ", "").strip()
    if not tz_name:
        return None
    return TZ_ALIASES.get(tz_name, tz_name)


def today_key(d: datetime | None = None) -> str:
    d = d or datetime.now()
    tz_name = get_report_tz()
    if tz_name:
        d = d.astimezone(ZoneInfo(tz_name))
    return d.strftime("%Y-%m-%d")


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=json_default),
        encoding="utf-8",
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    if isinstance(value, str):
        text = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    import re

    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip()


def compact_number(n: float) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(int(n))
