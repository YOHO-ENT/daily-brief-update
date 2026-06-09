#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path


REPO_DEFAULT = "https://github.com/leiting-eric/DailyBrief.git"
TARGET_DEFAULT = Path.home() / "daily-brief"


def require_command(name: str, hint: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"Missing prerequisite: {name}. {hint}")


def run(cmd: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def venv_python(target: Path) -> Path:
    if os.name == "nt":
        return target / ".venv" / "Scripts" / "python.exe"
    return target / ".venv" / "bin" / "python"


def main() -> None:
    parser = argparse.ArgumentParser(description="Install daily-brief Python version")
    parser.add_argument("--repo", default=REPO_DEFAULT)
    parser.add_argument("--target", default=str(TARGET_DEFAULT))
    parser.add_argument("--at", default="08:00")
    parser.add_argument("--skip-scheduler", action="store_true")
    args = parser.parse_args()

    target = Path(args.target).expanduser().resolve()
    print("=== daily-brief bootstrap ===")
    print(f"Repo:    {args.repo}")
    print(f"Target:  {target}")
    print(f"Trigger: {args.at}")

    require_command("git", "Install Git: https://git-scm.com/downloads")

    if target.exists():
        if not (target / ".git").exists():
            raise RuntimeError(f"{target} exists but is not a git repository")
        run(["git", "pull", "--ff-only"], cwd=target)
    else:
        run(["git", "clone", args.repo, str(target)])

    print("\n=== Creating virtual environment ===")
    venv.create(target / ".venv", with_pip=True)
    py = venv_python(target)

    print("\n=== Installing package ===")
    run([str(py), "-m", "pip", "install", "-U", "pip"], cwd=target)
    run([str(py), "-m", "pip", "install", "-e", ".[test]"], cwd=target)

    if not args.skip_scheduler:
        print("\n=== Registering scheduler + user-level skill ===")
        run([str(py), "-m", "dailybrief", "install", "--at", args.at, "--global"], cwd=target)

    print("\n=== Smoke test ===")
    run([str(py), "-m", "dailybrief", "dry-run"], cwd=target)

    print("\nInstalled.")
    print(f"Run manually: cd \"{target}\" && {py} -m dailybrief daily")


if __name__ == "__main__":
    main()
