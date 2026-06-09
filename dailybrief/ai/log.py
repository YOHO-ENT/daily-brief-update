from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from typing import Literal, Optional

from dailybrief.utils import LOG_DIR

LlmErrorCategory = Optional[Literal["timeout", "quota", "auth", "other"]]


@dataclass
class LlmCallRecord:
    ts: str
    backend: str
    model: str
    durationMs: int
    success: bool
    inputChars: int
    outputChars: int
    errorCategory: LlmErrorCategory
    errorSnippet: str | None


def classify_error(blob: str) -> LlmErrorCategory:
    if not blob.strip():
        return None
    if re.search(r"timeout|timed out|etimedout", blob, re.I):
        return "timeout"
    if re.search(r"rate.?limit|usage.?limit|quota|429|too many requests|credit.?balance|insufficient.?balance", blob, re.I):
        return "quota"
    if re.search(r"401|403|unauthorized|invalid.?api.?key|authentication|forbidden", blob, re.I):
        return "auth"
    return "other"


def log_llm_call(record: LlmCallRecord) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with (LOG_DIR / "llm-calls.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    except Exception:
        pass
