from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import webbrowser
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from dailybrief.models import ArticleInput, RawArticle
from dailybrief.utils import CONFIG_FILE, LOG_DIR, OUTPUT_DIR, REPO_ROOT, ensure_dirs, json_default, load_env, parse_dt, read_json, today_key, write_json

load_env()


def _article_to_input(raw: RawArticle, source_name: str) -> ArticleInput:
    return ArticleInput(
        sourceId=raw.sourceId,
        title=raw.title,
        url=raw.url,
        excerpt=raw.excerpt,
        publishedAt=raw.publishedAt,
        category=raw.category,
        summary=raw.summary,
        meta=raw.meta,
        source=source_name,
    )


def _article_from_json(data: dict) -> ArticleInput:
    return ArticleInput(
        sourceId=data["sourceId"],
        title=data["title"],
        url=data["url"],
        excerpt=data.get("excerpt"),
        publishedAt=parse_dt(data.get("publishedAt")),
        category=data["category"],
        summary=data.get("summary") or data.get("cnSummary"),
        meta=data.get("meta"),
        source=data.get("source", ""),
    )


def _load_articles(date: str) -> list[ArticleInput]:
    sidecar = OUTPUT_DIR / date / f"{date}-articles.json"
    if not sidecar.exists():
        raise FileNotFoundError(f"Articles sidecar not found: {sidecar}")
    data = read_json(sidecar)
    return [_article_from_json(a) for a in data.get("articles", [])]


def _load_report(date: str) -> dict:
    path = OUTPUT_DIR / date / f"{date}.json"
    if not path.exists():
        raise FileNotFoundError(f"Report JSON not found: {path}")
    return read_json(path)


def _write_report_outputs(date: str, report: dict, articles: list[ArticleInput]) -> None:
    from dailybrief.output.render import group_raw, render_html, render_markdown
    from dailybrief.sources.registry import sources

    date_dir = OUTPUT_DIR / date
    date_dir.mkdir(parents=True, exist_ok=True)
    base = date_dir / date
    raw = group_raw(articles, sources)
    write_json(base.with_suffix(".json"), report)
    write_json(Path(f"{base}-articles.json"), {"date": date, "articles": articles})
    base.with_suffix(".html").write_text(render_html(report, raw, date), encoding="utf-8")
    if os.environ.get("OUTPUT_MARKDOWN") == "true":
        base.with_suffix(".md").write_text(render_markdown(report, date), encoding="utf-8")


def fetch_all() -> list[ArticleInput]:
    from dailybrief.sources.dispatch import fetch_source
    from dailybrief.sources.registry import sources

    articles: list[ArticleInput] = []
    enabled = [s for s in sources if s.enabled is not False]
    for source in enabled:
        try:
            items = fetch_source(source)
            print(f"  {source.id.ljust(20)} {len(items)}")
            articles.extend(_article_to_input(item, source.name) for item in items)
        except Exception as exc:
            print(f"  {source.id.ljust(20)} FAILED - {exc}", file=sys.stderr)
    return articles


def _enrich_merged_subgroup(articles: list[ArticleInput], category: str, subcategory: str) -> None:
    from dailybrief.ai.enrich import enrich_news_summaries
    from dailybrief.output.render import MERGED_SUBGROUP_LIMITS, is_sports_article
    from dailybrief.sources.registry import report_locale, sources

    sub_sources = [
        s for s in sources if s.category == category and s.subcategory == subcategory and s.enabled is not False
    ]
    enabled_ids = {s.id for s in sub_sources}
    same_locale_ids = {s.id for s in sub_sources if (s.lang or "en") == report_locale()}
    limit = MERGED_SUBGROUP_LIMITS.get(f"{category}:{subcategory}", 12)
    top = [
        a
        for a in articles
        if a.sourceId in enabled_ids and (category != "politics" or not is_sports_article(a.title))
    ]
    top.sort(key=lambda a: a.publishedAt.timestamp() if a.publishedAt else 0, reverse=True)
    top = top[:limit]
    to_enrich = [a for a in top if a.sourceId not in same_locale_ids]
    if not to_enrich:
        return
    print(f"[daily] enriching {len(to_enrich)}/{len(top)} {category}:{subcategory} items...")
    summaries = enrich_news_summaries(to_enrich)
    for article in to_enrich:
        if article.url in summaries:
            article.summary = summaries[article.url]


def enrich_articles(articles: list[ArticleInput]) -> None:
    from dailybrief.ai.enrich import enrich_github_trending_summaries, enrich_papers_summaries, enrich_xviral_summaries

    gh = [a for a in articles if a.sourceId == "github-trending"]
    if gh:
        print(f"[daily] enriching {len(gh)} GitHub Trending repos...")
        summaries = enrich_github_trending_summaries(gh)
        for a in gh:
            if a.url in summaries:
                a.summary = summaries[a.url]

    papers = [a for a in articles if a.sourceId == "huggingface-papers"][:20]
    if papers:
        print(f"[daily] enriching {len(papers)} trending papers...")
        summaries = enrich_papers_summaries(papers)
        for a in papers:
            if a.url in summaries:
                a.summary = summaries[a.url]

    _enrich_merged_subgroup(articles, "finance", "news")
    _enrich_merged_subgroup(articles, "politics", "world")
    _enrich_merged_subgroup(articles, "tech", "ai-news")

    x_posts = [a for a in articles if a.sourceId == "attentionvc-ai"][:20]
    if x_posts:
        print(f"[daily] enriching {len(x_posts)} X posts...")
        summaries = enrich_xviral_summaries(x_posts)
        for a in x_posts:
            if a.url in summaries:
                a.summary = summaries[a.url]


def run_trading() -> dict | None:
    from dailybrief.ai.llm import get_model_tag
    from dailybrief.ai.trading_commentary import generate_trading_commentary
    from dailybrief.trading.coingecko import fetch_crypto_global
    from dailybrief.trading.fear_greed import fetch_crypto_fear_greed
    from dailybrief.trading.runner import analyze_watchlist

    print("[daily] analyzing watchlist + crypto context...")
    tickers = analyze_watchlist()
    fg = fetch_crypto_fear_greed()
    cg = fetch_crypto_global()
    print(f"[daily] indicators ready - {len(tickers)} tickers")
    if not tickers:
        return None
    print(f"[daily] generating trading commentary with {get_model_tag()}...")
    commentary = generate_trading_commentary({"tickers": tickers, "cryptoFearGreed": fg, "cryptoGlobal": cg})
    return {
        **commentary,
        "tickers": tickers,
        "crypto_fear_greed": fg,
        "crypto_global": cg,
        "generated_at": datetime.utcnow().isoformat(),
    }


def cmd_daily(_args: argparse.Namespace) -> None:
    from dailybrief.ai.llm import get_model_tag, validate_backend_credentials
    from dailybrief.ai.pipeline import generate_daily_report

    ensure_dirs()
    validate_backend_credentials()
    date = today_key()
    print(f"[daily] {date} - fetching sources...\n")
    articles = fetch_all()
    print(f"\n[daily] total articles: {len(articles)}")
    if not articles:
        raise RuntimeError("no articles fetched - aborting")
    enrich_articles(articles)
    trading = None
    try:
        trading = run_trading()
    except Exception as exc:
        print(f"[daily] trading section failed: {exc}")
    print(f"[daily] generating digest with {get_model_tag()}...")
    report = generate_daily_report(articles)
    if trading:
        report["trading"] = trading
    _write_report_outputs(date, report, articles)
    print(f"[daily] wrote {OUTPUT_DIR / date / date}.{{json,html,articles.json}}")


def cmd_dry_run(_args: argparse.Namespace) -> None:
    print("Fetching from sources...\n")
    articles = fetch_all()
    print(f"\nTotal articles: {len(articles)}")
    print("\nTop 10 articles:")
    for i, article in enumerate(articles[:10], 1):
        print(f"  {i}. [{article.category}] {article.title}")


def cmd_render(args: argparse.Namespace) -> None:
    from dailybrief.output.render import group_raw, render_html, render_markdown
    from dailybrief.sources.registry import sources

    date = args.date or today_key()
    report = _load_report(date)
    articles = _load_articles(date)
    raw = group_raw(articles, sources)
    base = OUTPUT_DIR / date / date
    Path(f"{base}.html").write_text(render_html(report, raw, date), encoding="utf-8")
    if os.environ.get("OUTPUT_MARKDOWN") == "true":
        Path(f"{base}.md").write_text(render_markdown(report, date), encoding="utf-8")
    print(f"[render] wrote {base}.html")


def cmd_regen_trading(args: argparse.Namespace) -> None:
    from dailybrief.ai.llm import validate_backend_credentials

    validate_backend_credentials()
    date = args.date or today_key()
    report = _load_report(date)
    trading = run_trading()
    if not trading:
        raise RuntimeError("trading returned no data")
    report["trading"] = trading
    write_json(OUTPUT_DIR / date / f"{date}.json", report)
    print(f"[regen-trading] patched {OUTPUT_DIR / date / f'{date}.json'}")


def cmd_regen_enrich(args: argparse.Namespace) -> None:
    from dailybrief.ai.enrich import enrich_news_summaries
    from dailybrief.ai.llm import validate_backend_credentials
    from dailybrief.output.render import MERGED_SUBGROUP_LIMITS, is_sports_article
    from dailybrief.sources.registry import report_locale, sources

    validate_backend_credentials()
    if ":" not in args.target:
        raise ValueError("Usage: regen-enrich <category:subcategory> [date]")
    category, subcategory = args.target.split(":", 1)
    date = args.date or today_key()
    sidecar = OUTPUT_DIR / date / f"{date}-articles.json"
    data = read_json(sidecar)
    articles = [_article_from_json(a) for a in data.get("articles", [])]
    sub_sources = [s for s in sources if s.category == category and s.subcategory == subcategory and s.enabled is not False]
    enabled_ids = {s.id for s in sub_sources}
    same_locale_ids = {s.id for s in sub_sources if (s.lang or "en") == report_locale()}
    limit = MERGED_SUBGROUP_LIMITS.get(f"{category}:{subcategory}", 12)
    top = [
        a
        for a in articles
        if a.sourceId in enabled_ids and (category != "politics" or not is_sports_article(a.title))
    ]
    top.sort(key=lambda a: a.publishedAt.timestamp() if a.publishedAt else 0, reverse=True)
    missing = [a for a in top[:limit] if a.sourceId not in same_locale_ids and not a.summary]
    print(f"[regen-enrich] {args.target}: top {len(top[:limit])}, missing summary on {len(missing)}")
    if not missing:
        return
    summaries = enrich_news_summaries(missing)
    patched = 0
    for article in articles:
        if article.url in summaries and not article.summary:
            article.summary = summaries[article.url]
            patched += 1
    write_json(sidecar, {"date": date, "articles": articles})
    print(f"[regen-enrich] patched {patched} articles in {sidecar}")


def cmd_sources(args: argparse.Namespace) -> None:
    from dailybrief.sources.registry import load_all_sources, report_locale

    all_sources = load_all_sources()
    if args.action == "check":
        print(f"OK sources.config.json ({len(all_sources)} sources)")
        return
    locale = report_locale()
    print(f"\nSource registry (REPORT_LOCALE={locale})\n")
    print("  active = enabled and included in current locale; filtered = enabled but locale-filtered\n")
    for cat in sorted({s.category for s in all_sources}):
        print(f"-- {cat} --")
        for s in [x for x in all_sources if x.category == cat]:
            locales = s.locales or ["zh", "en"]
            if s.enabled is False:
                status = "disabled"
            elif locale in locales:
                status = "active"
            else:
                status = "filtered"
            print(f"{status:9} {s.id:24} {s.name:24} {s.subcategory or '':18} {s.type}")
        print()


def cmd_quota_report(_args: argparse.Namespace) -> None:
    log_paths = [REPO_ROOT / "logs" / "claude-calls.jsonl", REPO_ROOT / "logs" / "llm-calls.jsonl"]
    calls = []
    for path in log_paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                item.setdefault("backend", "claude-cli")
                calls.append(item)
            except Exception:
                pass
    if not calls:
        print("No LLM call records found.")
        return
    by_backend: dict[str, list[dict]] = {}
    for call in calls:
        by_backend.setdefault(call.get("backend") or "?", []).append(call)
    print(f"\n=== LLM usage ({len(calls)} calls) ===")
    for backend, records in sorted(by_backend.items()):
        failures = [r for r in records if not r.get("success")]
        input_chars = sum(int(r.get("inputChars") or 0) for r in records)
        output_chars = sum(int(r.get("outputChars") or 0) for r in records)
        print(f"\nbackend: {backend} ({len(records)} calls)")
        print(f"  input chars:  {input_chars}")
        print(f"  output chars: {output_chars}")
        print(f"  failures:     {len(failures)}")


def cmd_build_site(_args: argparse.Namespace) -> None:
    if not OUTPUT_DIR.exists():
        raise FileNotFoundError(f"{OUTPUT_DIR} doesn't exist - run daily first")
    dates = sorted(
        [
            p.name
            for p in OUTPUT_DIR.iterdir()
            if p.is_dir() and len(p.name) == 10 and (p / f"{p.name}.html").exists()
        ],
        reverse=True,
    )
    if not dates:
        raise FileNotFoundError(f"no <YYYY-MM-DD>/<YYYY-MM-DD>.html found in {OUTPUT_DIR}")
    latest = dates[0]
    latest_html = (OUTPUT_DIR / latest / f"{latest}.html").read_text(encoding="utf-8").replace('href="../archive.html"', 'href="./archive.html"')
    (OUTPUT_DIR / "index.html").write_text(latest_html, encoding="utf-8")
    rows = "\n".join(
        f'      <li><a href="./{d}/{d}.html">{d}</a> <span>{((OUTPUT_DIR / d / f"{d}.html").stat().st_size / 1024):.0f} KB</span></li>'
        for d in dates
    )
    archive = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>daily-brief archive</title><style>body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:720px;margin:3rem auto;padding:0 1.5rem;line-height:1.5}}li{{display:flex;justify-content:space-between;border-bottom:1px solid #eee;padding:.5rem 0}}</style></head><body><h1>daily-brief archive</h1><p>{len(dates)} reports · newest first</p><p><a href="./index.html">Latest report ({latest})</a></p><ul>{rows}</ul></body></html>"""
    (OUTPUT_DIR / "archive.html").write_text(archive, encoding="utf-8")
    (OUTPUT_DIR / ".nojekyll").write_text("", encoding="utf-8")
    print(f"[build-site] index.html <- {latest}/{latest}.html")


def cmd_deploy(args: argparse.Namespace) -> None:
    host = os.environ.get("DEPLOY_HOST")
    remote_path = os.environ.get("DEPLOY_PATH")
    if not host or not remote_path:
        print("[deploy] DEPLOY_HOST / DEPLOY_PATH not set in .env.local - skipping")
        return
    date = args.date
    if date:
        local_file = OUTPUT_DIR / date / f"{date}.html"
        if not local_file.exists():
            raise FileNotFoundError(f"[deploy] local file missing: {local_file}")
    else:
        local_file = _pick_report(None)
        date = local_file.parent.name
    tmp_path = f"/tmp/daily-deploy-{date}.html"
    print(f"[deploy] uploading {local_file} -> {host}:{remote_path}/")
    scp = subprocess.run(["scp", "-q", str(local_file), f"{host}:{tmp_path}"])
    if scp.returncode != 0:
        raise RuntimeError(f"scp failed (exit {scp.returncode})")
    remote_cmd = " && ".join(
        [
            f"sudo mv {tmp_path} {remote_path}/{date}.html",
            f"sudo cp {remote_path}/{date}.html {remote_path}/index.html",
            f"sudo chown www-data:www-data {remote_path}/{date}.html {remote_path}/index.html",
        ]
    )
    ssh = subprocess.run(["ssh", host, remote_cmd])
    if ssh.returncode != 0:
        raise RuntimeError(f"ssh failed (exit {ssh.returncode})")
    print(f"[deploy] OK - {date}.html deployed")


def _pick_report(date: str | None) -> Path:
    if date:
        target = OUTPUT_DIR / date / f"{date}.html"
        if not target.exists():
            raise FileNotFoundError(f"No report for {date}: {target}")
        return target
    dirs = sorted(
        [p for p in OUTPUT_DIR.iterdir() if p.is_dir() and (p / f"{p.name}.html").exists()],
        key=lambda p: p.name,
        reverse=True,
    )
    if not dirs:
        raise FileNotFoundError(f"No HTML reports in {OUTPUT_DIR}. Run daily first.")
    return dirs[0] / f"{dirs[0].name}.html"


def cmd_open(args: argparse.Namespace) -> None:
    target = _pick_report(args.date)
    webbrowser.open(target.resolve().as_uri())
    print(f"Opened: {target}")


def _dailybrief_module_cmd(*args: str) -> list[str]:
    return [sys.executable, "-m", "dailybrief", *args]


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    env["DAILYBRIEF_ROOT"] = str(REPO_ROOT)
    return env


def _validate_at(value: str) -> tuple[int, int]:
    try:
        hour_s, minute_s = value.split(":", 1)
        hour = int(hour_s)
        minute = int(minute_s)
    except Exception as exc:
        raise ValueError("--at must be HH:MM, for example 08:00") from exc
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError("--at must be a valid 24-hour local time")
    return hour, minute


def _symlink_or_copy(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        if dst.is_dir() and not dst.is_symlink():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        target_is_directory = src.is_dir()
        os.symlink(src, dst, target_is_directory=target_is_directory)
        print(f"[OK] link: {dst} -> {src}")
    except Exception:
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        print(f"[OK] copy: {dst}")


def _install_user_level_skill() -> None:
    user_claude = Path.home() / ".claude"
    items = [
        (REPO_ROOT / ".claude" / "skills" / "daily-brief", user_claude / "skills" / "daily-brief"),
        (REPO_ROOT / ".claude" / "commands" / "run-daily.md", user_claude / "commands" / "run-daily.md"),
        (REPO_ROOT / ".claude" / "commands" / "check-daily.md", user_claude / "commands" / "check-daily.md"),
    ]
    for src, dst in items:
        if not src.exists():
            raise FileNotFoundError(f"Missing project file: {src}")
        _symlink_or_copy(src, dst)


def cmd_install(args: argparse.Namespace) -> None:
    hour, minute = _validate_at(args.at)
    ensure_dirs()
    cfg_path = Path.home() / CONFIG_FILE
    cfg_path.write_text(str(REPO_ROOT), encoding="utf-8")

    print("=== daily-brief install ===")
    print(f"Project root: {REPO_ROOT}")
    print(f"Python:       {sys.executable}")
    print(f"Trigger:      Daily at {args.at} local time")
    print(f"Config:       {cfg_path}")

    if sys.platform == "win32":
        ps_script = f"""
$action = New-ScheduledTaskAction `
    -Execute '{sys.executable}' `
    -Argument '-m dailybrief run-scheduled' `
    -WorkingDirectory '{REPO_ROOT}'
$trigger = New-ScheduledTaskTrigger -Daily -At "{args.at}"
$settings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited
Register-ScheduledTask `
    -TaskName "DailyBrief" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Generate daily AI news and markets digest" `
    -Force | Out-Null
Write-Host "[OK] Task 'DailyBrief' registered"
"""
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as fh:
            fh.write(ps_script)
            tmp = fh.name
        try:
            subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", tmp], check=True)
        finally:
            Path(tmp).unlink(missing_ok=True)
    elif sys.platform == "darwin":
        plist_path = Path.home() / "Library" / "LaunchAgents" / "com.daily-brief.plist"
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        log_out = LOG_DIR / "launchd.out.log"
        log_err = LOG_DIR / "launchd.err.log"
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.daily-brief</string>
  <key>ProgramArguments</key>
  <array>
    <string>{sys.executable}</string>
    <string>-m</string>
    <string>dailybrief</string>
    <string>run-scheduled</string>
  </array>
  <key>WorkingDirectory</key><string>{REPO_ROOT}</string>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>{hour}</integer><key>Minute</key><integer>{minute}</integer></dict>
  <key>StandardOutPath</key><string>{log_out}</string>
  <key>StandardErrorPath</key><string>{log_err}</string>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
"""
        plist_path.write_text(plist, encoding="utf-8")
        subprocess.run(["launchctl", "unload", str(plist_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["launchctl", "load", str(plist_path)], check=True)
        print(f"[OK] launchd job installed: {plist_path}")
    elif sys.platform.startswith("linux"):
        marker = "# daily-brief"
        cron_log = LOG_DIR / "cron.log"
        cron_line = (
            f'{minute} {hour} * * * cd "{REPO_ROOT}" && "{sys.executable}" '
            f'-m dailybrief run-scheduled >> "{cron_log}" 2>&1 {marker}'
        )
        existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        current = existing.stdout if existing.returncode == 0 else ""
        kept = "\n".join(line for line in current.splitlines() if marker not in line).strip()
        new_cron = (kept + "\n" if kept else "") + cron_line + "\n"
        subprocess.run(["crontab", "-"], input=new_cron, text=True, check=True)
        print("[OK] cron entry installed")
    else:
        raise RuntimeError(f"Unsupported platform for scheduler install: {sys.platform}")

    if args.global_install:
        print("\n=== Installing user-level Claude skill + commands ===")
        _install_user_level_skill()
    print("\nInstalled. Try: dailybrief run-scheduled")


def _append_log(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(path.read_text(encoding="utf-8") + text if path.exists() else text, encoding="utf-8")


def _run_logged(log_file: Path, cmd: list[str]) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=_child_env(),
        capture_output=True,
        text=True,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    if output:
        _append_log(log_file, output)
    return proc


def cmd_run_scheduled(_args: argparse.Namespace) -> None:
    ensure_dirs()
    date = today_key()
    log_file = LOG_DIR / f"daily-{date}.log"
    now = lambda: datetime.now().strftime("%H:%M:%S")

    _append_log(log_file, f"[{now()}] running dailybrief daily\n")
    daily = _run_logged(log_file, _dailybrief_module_cmd("daily"))
    if daily.returncode != 0:
        _append_log(log_file, f"\n[{now()}] FAILED: dailybrief daily exited {daily.returncode}\n")
        raise SystemExit(daily.returncode)

    _append_log(log_file, f"\n[{now()}] OK\n")
    _append_log(log_file, f"[{now()}] deploying...\n")
    deploy = _run_logged(log_file, _dailybrief_module_cmd("deploy"))
    if deploy.returncode == 0:
        _append_log(log_file, f"[{now()}] deploy OK\n")
    else:
        _append_log(log_file, f"[{now()}] deploy FAILED (exit {deploy.returncode}) - non-fatal\n")

    try:
        subprocess.Popen(
            _dailybrief_module_cmd("open"),
            cwd=REPO_ROOT,
            env=_child_env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=(os.name != "nt"),
        )
    except Exception as exc:
        _append_log(log_file, f"[{now()}] open skipped: {exc}\n")
    print(f"[run-scheduled] OK - log: {log_file}")


def _safe_rm(path: Path) -> None:
    if path.exists() or path.is_symlink():
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
        print(f"[OK] removed {path}")


def cmd_uninstall(_args: argparse.Namespace) -> None:
    if sys.platform == "win32":
        ps_script = """
$task = Get-ScheduledTask -TaskName DailyBrief -ErrorAction SilentlyContinue
if ($task) {
  try { Stop-ScheduledTask -TaskName DailyBrief -ErrorAction SilentlyContinue } catch {}
  Unregister-ScheduledTask -TaskName DailyBrief -Confirm:$false
  Write-Host "[OK] Task 'DailyBrief' unregistered"
} else {
  Write-Host "[skip] Task 'DailyBrief' was not registered"
}
"""
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as fh:
            fh.write(ps_script)
            tmp = fh.name
        try:
            subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", tmp], check=True)
        finally:
            Path(tmp).unlink(missing_ok=True)
    elif sys.platform == "darwin":
        plist_path = Path.home() / "Library" / "LaunchAgents" / "com.daily-brief.plist"
        subprocess.run(["launchctl", "unload", str(plist_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _safe_rm(plist_path)
    elif sys.platform.startswith("linux"):
        marker = "# daily-brief"
        existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if existing.returncode == 0:
            kept = "\n".join(line for line in existing.stdout.splitlines() if marker not in line).strip()
            subprocess.run(["crontab", "-"], input=(kept + "\n" if kept else ""), text=True, check=True)
            print("[OK] removed daily-brief cron entry")
    else:
        print(f"[skip] unsupported scheduler cleanup for {sys.platform}")

    user_claude = Path.home() / ".claude"
    _safe_rm(user_claude / "skills" / "daily-brief")
    _safe_rm(user_claude / "commands" / "run-daily.md")
    _safe_rm(user_claude / "commands" / "check-daily.md")
    _safe_rm(Path.home() / CONFIG_FILE)
    print("Done. Project files, daily_reports, and logs were not touched.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dailybrief")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("daily").set_defaults(func=cmd_daily)
    sub.add_parser("dry-run").set_defaults(func=cmd_dry_run)
    p = sub.add_parser("render")
    p.add_argument("date", nargs="?")
    p.set_defaults(func=cmd_render)
    p = sub.add_parser("regen-trading")
    p.add_argument("date", nargs="?")
    p.set_defaults(func=cmd_regen_trading)
    p = sub.add_parser("regen-enrich")
    p.add_argument("target")
    p.add_argument("date", nargs="?")
    p.set_defaults(func=cmd_regen_enrich)
    p = sub.add_parser("sources")
    p.add_argument("action", nargs="?", choices=["check", "list"], default="list")
    p.set_defaults(func=cmd_sources)
    sub.add_parser("quota-report").set_defaults(func=cmd_quota_report)
    sub.add_parser("build-site").set_defaults(func=cmd_build_site)
    p = sub.add_parser("deploy")
    p.add_argument("date", nargs="?")
    p.set_defaults(func=cmd_deploy)
    p = sub.add_parser("open")
    p.add_argument("date", nargs="?")
    p.set_defaults(func=cmd_open)
    p = sub.add_parser("install")
    p.add_argument("--at", default="08:00", help="Daily trigger time, HH:MM local time")
    p.add_argument("--global", dest="global_install", action="store_true", help="Install user-level Claude skill and commands")
    p.set_defaults(func=cmd_install)
    sub.add_parser("run-scheduled").set_defaults(func=cmd_run_scheduled)
    sub.add_parser("uninstall").set_defaults(func=cmd_uninstall)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
