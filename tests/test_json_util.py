import json

from dailybrief.ai.json_util import extract_json, repair_json_text


def test_extract_json_from_fence_and_preamble():
    raw = "Here:\n```json\n{\"ok\": true}\n```\nthanks"
    assert extract_json(raw) == '{"ok": true}'


def test_repair_json_text_is_parseable_for_simple_json():
    text = repair_json_text('{"items":[1,2,]}')
    assert json.loads(text)["items"] == [1, 2]
