from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from dailybrief.runtime.safety import redact

from .log import LlmCallRecord, classify_error, log_llm_call


@dataclass
class LlmRunResult:
    text: str
    durationMs: int


VALID_BACKENDS = {"claude-cli", "anthropic", "openai", "deepseek", "minimax", "zhipu"}

OPENAI_PRESETS = {
    "openai": {
        "default_base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
        "base_url_env": "OPENAI_BASE_URL",
    },
    "deepseek": {
        "default_base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-v4-flash",
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url_env": "DEEPSEEK_BASE_URL",
    },
    "minimax": {
        "default_base_url": "https://api.minimax.io/v1",
        "default_model": "MiniMax-M2.7",
        "api_key_env": "MINIMAX_API_KEY",
        "base_url_env": "MINIMAX_BASE_URL",
    },
}

ANTHROPIC_PRESETS = {
    "anthropic": {
        "default_base_url": None,
        "default_model": "claude-sonnet-4-6",
        "api_key_env": "ANTHROPIC_API_KEY",
        "base_url_env": "ANTHROPIC_BASE_URL",
    },
    "zhipu": {
        "default_base_url": "https://open.bigmodel.cn/api/anthropic",
        "default_model": "claude-sonnet-4-6",
        "api_key_env": "ZHIPU_API_KEY",
        "base_url_env": "ZHIPU_BASE_URL",
    },
}


def get_backend() -> str:
    raw = (os.environ.get("LLM_BACKEND") or "claude-cli").strip().lower()
    if raw not in VALID_BACKENDS:
        raise ValueError(f"Unknown LLM_BACKEND='{raw}'. Valid values: {', '.join(sorted(VALID_BACKENDS))}")
    return raw


def _claude_model() -> str:
    return os.environ.get("CLAUDE_MODEL", "").strip() or "sonnet"


def _active_model(backend: str) -> str:
    if backend == "claude-cli":
        return _claude_model()
    if backend in OPENAI_PRESETS:
        return os.environ.get("LLM_MODEL", "").strip() or OPENAI_PRESETS[backend]["default_model"]
    if backend in ANTHROPIC_PRESETS:
        return os.environ.get("LLM_MODEL", "").strip() or ANTHROPIC_PRESETS[backend]["default_model"]
    raise ValueError(backend)


def get_model_tag() -> str:
    backend = get_backend()
    return f"{backend}-{_active_model(backend)}"


def validate_backend_credentials() -> None:
    backend = get_backend()
    if backend == "claude-cli":
        return
    required = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "minimax": "MINIMAX_API_KEY",
        "zhipu": "ZHIPU_API_KEY",
    }
    required_var = required[backend]
    if os.environ.get(required_var) or os.environ.get("LLM_API_KEY"):
        return
    other = [(b, v) for b, v in required.items() if b != backend and os.environ.get(v)]
    lines = [f"LLM_BACKEND={backend} but {required_var} (and generic LLM_API_KEY) are both unset."]
    if other:
        lines.append("")
        lines.append("Other API keys ARE present in the environment — likely you meant to use one of those:")
        lines.extend([f"  - {var} is set -> switch to LLM_BACKEND={b}" for b, var in other])
    else:
        lines.append(f"Fix: set {required_var} (or generic LLM_API_KEY).")
    raise RuntimeError("\n".join(lines))


def _record_started() -> tuple[float, str]:
    started = time.time()
    return started, datetime.fromtimestamp(started, tz=timezone.utc).isoformat()


def _log(
    *,
    started: float,
    ts: str,
    backend: str,
    model: str,
    success: bool,
    system_prompt: str,
    user_prompt: str,
    text: str = "",
    error: str = "",
) -> None:
    log_llm_call(
        LlmCallRecord(
            ts=ts,
            backend=backend,
            model=model,
            durationMs=int((time.time() - started) * 1000),
            success=success,
            inputChars=len(system_prompt) + len(user_prompt),
            outputChars=len(text),
            errorCategory=None if success else classify_error(error),
            errorSnippet=None if success else redact(error)[:200],
        )
    )


def _resolve_claude_cli() -> str:
    override = os.environ.get("CLAUDE_CLI_PATH", "").strip()
    if override:
        return override
    appdata = os.environ.get("APPDATA")
    if appdata:
        return os.path.join(appdata, "npm", "claude.cmd")
    return "claude"


def _run_claude_cli(system_prompt: str, user_prompt: str, timeout_ms: int) -> LlmRunResult:
    backend = "claude-cli"
    model = _claude_model()
    started, ts = _record_started()
    args = [_resolve_claude_cli(), "--print", "--model", model, "--append-system-prompt", system_prompt]
    try:
        proc = subprocess.run(
            args,
            input=user_prompt,
            capture_output=True,
            text=True,
            timeout=timeout_ms / 1000,
        )
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        if stderr:
            print(f"[claude-cli] stderr (non-fatal): {redact(stderr)}")
        if proc.returncode != 0 and not stdout:
            raise RuntimeError(f"claude CLI exited {proc.returncode} with empty stdout\n{stderr}")
        _log(started=started, ts=ts, backend=backend, model=model, success=True, system_prompt=system_prompt, user_prompt=user_prompt, text=stdout)
        return LlmRunResult(stdout, int((time.time() - started) * 1000))
    except Exception as exc:
        _log(started=started, ts=ts, backend=backend, model=model, success=False, system_prompt=system_prompt, user_prompt=user_prompt, error=str(exc))
        raise


def _run_openai_compat(backend: str, system_prompt: str, user_prompt: str, timeout_ms: int) -> LlmRunResult:
    from openai import OpenAI

    cfg = OPENAI_PRESETS[backend]
    api_key = os.environ.get(cfg["api_key_env"]) or os.environ.get("LLM_API_KEY")
    if not api_key:
        raise RuntimeError(f"{cfg['api_key_env']} (or generic LLM_API_KEY) is required for LLM_BACKEND={backend}.")
    base_url = os.environ.get(cfg["base_url_env"], "").strip() or os.environ.get("LLM_BASE_URL", "").strip() or cfg["default_base_url"]
    model = os.environ.get("LLM_MODEL", "").strip() or cfg["default_model"]
    started, ts = _record_started()
    try:
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_ms / 1000)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            max_tokens=8192,
        )
        text = (resp.choices[0].message.content or "").strip()
        _log(started=started, ts=ts, backend=backend, model=model, success=True, system_prompt=system_prompt, user_prompt=user_prompt, text=text)
        return LlmRunResult(text, int((time.time() - started) * 1000))
    except Exception as exc:
        _log(started=started, ts=ts, backend=backend, model=model, success=False, system_prompt=system_prompt, user_prompt=user_prompt, error=str(exc))
        raise


def _run_anthropic_compat(backend: str, system_prompt: str, user_prompt: str, timeout_ms: int) -> LlmRunResult:
    from anthropic import Anthropic

    cfg = ANTHROPIC_PRESETS[backend]
    api_key = os.environ.get(cfg["api_key_env"]) or os.environ.get("LLM_API_KEY")
    if not api_key:
        raise RuntimeError(f"{cfg['api_key_env']} (or generic LLM_API_KEY) is required for LLM_BACKEND={backend}.")
    base_url = os.environ.get(cfg["base_url_env"], "").strip() or os.environ.get("LLM_BASE_URL", "").strip() or cfg["default_base_url"]
    model = os.environ.get("LLM_MODEL", "").strip() or cfg["default_model"]
    started, ts = _record_started()
    try:
        client = Anthropic(api_key=api_key, base_url=base_url, timeout=timeout_ms / 1000)
        resp = client.messages.create(
            model=model,
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(getattr(block, "text", "") for block in resp.content if getattr(block, "type", "") == "text").strip()
        _log(started=started, ts=ts, backend=backend, model=model, success=True, system_prompt=system_prompt, user_prompt=user_prompt, text=text)
        return LlmRunResult(text, int((time.time() - started) * 1000))
    except Exception as exc:
        _log(started=started, ts=ts, backend=backend, model=model, success=False, system_prompt=system_prompt, user_prompt=user_prompt, error=str(exc))
        raise


def run_llm(system_prompt: str, user_prompt: str, timeout_ms: int = 180_000) -> LlmRunResult:
    backend = get_backend()
    if backend == "claude-cli":
        return _run_claude_cli(system_prompt, user_prompt, timeout_ms)
    if backend in OPENAI_PRESETS:
        return _run_openai_compat(backend, system_prompt, user_prompt, timeout_ms)
    if backend in ANTHROPIC_PRESETS:
        return _run_anthropic_compat(backend, system_prompt, user_prompt, timeout_ms)
    raise ValueError(backend)
