import json

import pytest

from chatbot.services.assistant_blocks import normalize_assistant_output, try_parse_blocks


def test_normalize_wraps_plain_text() -> None:
    out = normalize_assistant_output("hello")
    data = json.loads(out)
    assert data == {"blocks": [{"type": "paragraph", "text": "hello"}]}


def test_normalize_passthrough_valid_json() -> None:
    raw = json.dumps(
        {
            "blocks": [
                {"type": "heading", "text": "Hi"},
                {"type": "paragraph", "text": "Body."},
            ]
        }
    )
    out = normalize_assistant_output(raw)
    assert json.loads(out) == json.loads(raw)


def test_try_parse_strips_fence() -> None:
    raw = """```json
{"blocks": [{"type": "paragraph", "text": "x"}]}
```"""
    parsed = try_parse_blocks(raw)
    assert parsed == {"blocks": [{"type": "paragraph", "text": "x"}]}


@pytest.mark.parametrize(
    "bad",
    ["not json", '{"blocks": []}', '{"blocks": [{}]}', '{"foo": 1}'],
)
def test_normalize_fallback_for_invalid(bad: str) -> None:
    out = normalize_assistant_output(bad)
    data = json.loads(out)
    assert len(data["blocks"]) == 1
    assert data["blocks"][0]["type"] == "paragraph"
