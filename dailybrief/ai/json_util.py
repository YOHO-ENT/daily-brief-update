from __future__ import annotations


def extract_json(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last > first:
        return text[first : last + 1]
    return text


def repair_json_text(text: str) -> str:
    try:
        from json_repair import repair_json

        return repair_json(text)
    except Exception:
        return text
