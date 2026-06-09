from __future__ import annotations

from typing import Any

from dailybrief.models import SourceDef
from dailybrief.utils import REPO_ROOT, report_locale

import json

CONFIG_PATH = REPO_ROOT / "sources.config.json"


def _validate(raw: Any) -> list[SourceDef]:
    if not isinstance(raw, list):
        raise ValueError(f"{CONFIG_PATH}: top-level must be an array of sources")

    valid_types = {"rss", "api", "scrape"}
    valid_categories = {"tech", "finance", "politics"}
    seen: set[str] = set()
    out: list[SourceDef] = []
    for i, item in enumerate(raw):
        at = f"sources.config.json[{i}]"
        if not isinstance(item, dict):
            raise ValueError(f"{at}: source must be an object")
        source_id = item.get("id")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError(f"{at}: missing string 'id'")
        if source_id in seen:
            raise ValueError(f"{at}: duplicate id '{source_id}'")
        seen.add(source_id)
        if not isinstance(item.get("name"), str):
            raise ValueError(f"{at} ({source_id}): missing 'name'")
        if not isinstance(item.get("url"), str):
            raise ValueError(f"{at} ({source_id}): missing 'url'")
        if item.get("type") not in valid_types:
            raise ValueError(f"{at} ({source_id}): invalid 'type' '{item.get('type')}'")
        if item.get("category") not in valid_categories:
            raise ValueError(
                f"{at} ({source_id}): invalid 'category' '{item.get('category')}'"
            )
        locales = item.get("locales")
        if locales is not None:
            if not isinstance(locales, list) or any(x not in ("zh", "en") for x in locales):
                raise ValueError(
                    f"{at} ({source_id}): 'locales' must be an array of 'zh' | 'en'"
                )
        out.append(SourceDef(**item))
    return out


def load_all_sources() -> list[SourceDef]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Source config missing: {CONFIG_PATH}")
    return _validate(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))


def filter_by_locale(all_sources: list[SourceDef]) -> list[SourceDef]:
    locale = report_locale()
    return [s for s in all_sources if locale in (s.locales or ["zh", "en"])]


sources = filter_by_locale(load_all_sources())
