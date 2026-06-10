from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit


SECRET_REPLACEMENT = "[REDACTED]"

SECRET_PATTERNS = (
    re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/_-]+"),
    re.compile(r"https://api\.telegram\.org/bot[^\s/]+"),
    re.compile(r"Authorization:\s*Bearer\s+[A-Za-z0-9._~+/=-]+", re.I),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.I),
    re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)\b(token|password|api[_-]?key|apikey|secret)=([^&\s]+)"),
    re.compile(r"(?i)\b([A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|WEBHOOK)[A-Z0-9_]*)=([^\s]+)"),
)

URL_WITH_PASSWORD_RE = re.compile(
    r"(?P<scheme>[a-z][a-z0-9+.-]*://)(?P<user>[^:/@\s]+):(?P<password>[^@\s]+)@(?P<host>[^\s]+)",
    re.I,
)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def redact(value: Any, extra_secrets: list[str | None] | tuple[str | None, ...] = ()) -> str:
    text = "" if value is None else str(value)
    for secret in extra_secrets:
        if secret:
            text = text.replace(secret, SECRET_REPLACEMENT)
    text = URL_WITH_PASSWORD_RE.sub(_redact_url_password_match, text)
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(_replace_secret_match, text)
    return text


def contains_secret(value: Any) -> bool:
    text = "" if value is None else str(value)
    if URL_WITH_PASSWORD_RE.search(text):
        return True
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def redact_url(value: str | None) -> str | None:
    if not value:
        return value
    try:
        parsed = urlsplit(value)
    except Exception:
        return redact(value)
    if parsed.username or parsed.password:
        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        netloc = f"{parsed.username or 'user'}:{SECRET_REPLACEMENT}@{host}{port}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
    return redact(value)


def safe_error(error: Exception | str) -> str:
    return redact(str(error))


def _redact_url_password_match(match: re.Match[str]) -> str:
    return f"{match.group('scheme')}{match.group('user')}:{SECRET_REPLACEMENT}@{match.group('host')}"


def _replace_secret_match(match: re.Match[str]) -> str:
    if match.lastindex and match.lastindex >= 2:
        key = match.group(1)
        if key:
            return f"{key}={SECRET_REPLACEMENT}"
    return SECRET_REPLACEMENT

