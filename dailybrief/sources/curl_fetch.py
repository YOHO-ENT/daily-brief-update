from __future__ import annotations

import subprocess


def curl_fetch(url: str, headers: dict[str, str] | None = None, timeout_sec: int = 20) -> str:
    args = ["curl", "-sSL", "-m", str(timeout_sec), "--compressed"]
    for key, value in (headers or {}).items():
        args.extend(["-H", f"{key}: {value}"])
    args.append(url)
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    return result.stdout
