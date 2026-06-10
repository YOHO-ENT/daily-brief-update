#!/usr/bin/env python3
"""Read-only VPS production readiness checks for DailyBrief."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dailybrief.runtime.safety import env_bool, redact  # noqa: E402
from dailybrief.storage.artifacts import latest_report_date, paths_for_date  # noqa: E402
from dailybrief.utils import load_env  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check DailyBrief VPS production readiness.")
    parser.add_argument("--output-dir", default="daily_reports", help="DailyBrief output directory.")
    parser.add_argument("--service", default="dailybrief.service", help="systemd service name.")
    parser.add_argument("--timer", default="dailybrief.timer", help="systemd timer name.")
    parser.add_argument("--env-file", default="/etc/dailybrief/dailybrief.env", help="Private VPS env file.")
    parser.add_argument("--output-json", action="store_true", help="Print JSON output.")
    args = parser.parse_args(argv)
    load_env()
    payload = check_vps_production(
        output_dir=Path(args.output_dir),
        service=args.service,
        timer=args.timer,
        env_file=Path(args.env_file),
    )
    if args.output_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"status={payload['status']}")
        print(f"git_revision={payload['git']['revision']}")
        print(f"latest_report_date={payload['artifacts']['latest_report_date']}")
        for warning in payload["warnings"]:
            print(f"warning={warning}")
    return 0 if payload["status"] in {"ready", "warning"} else 2


def check_vps_production(*, output_dir: Path, service: str, timer: str, env_file: Path) -> dict[str, Any]:
    git = _git_health()
    artifacts = _artifact_health(output_dir)
    env = _env_health(env_file)
    systemd = _systemd_health(service=service, timer=timer)
    warnings = []
    warnings.extend(git["warnings"])
    warnings.extend(artifacts["warnings"])
    warnings.extend(env["warnings"])
    warnings.extend(systemd["warnings"])
    status = "ready" if not warnings else "warning"
    return {
        "status": status,
        "git": git,
        "env": env,
        "artifacts": artifacts,
        "systemd": systemd,
        "warnings": warnings,
    }


def _git_health() -> dict[str, Any]:
    rev = _run_cmd(["git", "rev-parse", "--short", "HEAD"])
    status = _run_cmd(["git", "status", "--short"])
    warnings: list[str] = []
    if rev["returncode"] != 0:
        warnings.append("git_revision_unavailable")
    return {
        "revision": rev["stdout"].strip() if rev["returncode"] == 0 else None,
        "dirty": bool(status["stdout"].strip()) if status["returncode"] == 0 else None,
        "warnings": warnings,
    }


def _artifact_health(output_dir: Path) -> dict[str, Any]:
    latest = latest_report_date(output_dir)
    warnings: list[str] = []
    artifact_status: dict[str, bool] = {}
    if not latest:
        warnings.append("no_dailybrief_artifacts")
    else:
        paths = paths_for_date(latest, output_dir)
        artifact_status = {
            "html": paths.html.exists(),
            "json": paths.report_json.exists(),
            "articles": paths.articles_json.exists(),
        }
        missing = [name for name, exists in artifact_status.items() if not exists]
        if missing:
            warnings.append(f"latest_artifacts_missing={','.join(missing)}")
    return {
        "output_dir": str(output_dir),
        "latest_report_date": latest,
        "latest_artifacts": artifact_status,
        "warnings": warnings,
    }


def _env_health(env_file: Path) -> dict[str, Any]:
    env_file_exists = env_file.exists()
    file_gate = _env_file_has_live_gate(env_file) if env_file_exists else False
    process_gate = env_bool("DAILYBRIEF_LIVE_ALLOWED", False)
    warnings: list[str] = []
    if not (file_gate or process_gate):
        warnings.append("dailybrief_live_gate_not_enabled")
    return {
        "env_file": str(env_file),
        "env_file_exists": env_file_exists,
        "dailybrief_live_allowed": bool(file_gate or process_gate),
        "warnings": warnings,
    }


def _systemd_health(*, service: str, timer: str) -> dict[str, Any]:
    if not shutil.which("systemctl"):
        return {
            "available": False,
            "service": service,
            "timer": timer,
            "service_active": None,
            "timer_active": None,
            "timer_enabled": None,
            "journal_tail": "",
            "warnings": ["systemd_unavailable"],
        }
    service_active = _run_cmd(["systemctl", "is-active", service])
    timer_active = _run_cmd(["systemctl", "is-active", timer])
    timer_enabled = _run_cmd(["systemctl", "is-enabled", timer])
    journal = _run_cmd(["journalctl", "-u", service, "-n", "40", "--no-pager"])
    warnings: list[str] = []
    if service_active["returncode"] not in (0, 3):
        warnings.append("service_status_unavailable")
    if timer_active["stdout"].strip() != "active":
        warnings.append(f"{timer}_not_active")
    if timer_enabled["stdout"].strip() != "enabled":
        warnings.append(f"{timer}_not_enabled")
    return {
        "available": True,
        "service": service,
        "timer": timer,
        "service_active": service_active["stdout"].strip() or service_active["stderr"].strip(),
        "timer_active": timer_active["stdout"].strip() or timer_active["stderr"].strip(),
        "timer_enabled": timer_enabled["stdout"].strip() or timer_enabled["stderr"].strip(),
        "journal_tail": journal["stdout"][-4000:],
        "warnings": warnings,
    }


def _env_file_has_live_gate(path: Path) -> bool:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            if key.strip() == "DAILYBRIEF_LIVE_ALLOWED":
                return value.strip().strip("\"'").lower() in {"1", "true", "yes", "on"}
    except Exception:
        return False
    return False


def _run_cmd(cmd: list[str]) -> dict[str, Any]:
    try:
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10)
        return {
            "returncode": proc.returncode,
            "stdout": redact(proc.stdout or ""),
            "stderr": redact(proc.stderr or ""),
        }
    except Exception as exc:
        return {"returncode": 127, "stdout": "", "stderr": redact(exc)}


if __name__ == "__main__":
    raise SystemExit(main())

