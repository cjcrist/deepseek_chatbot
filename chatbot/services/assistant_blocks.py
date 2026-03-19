"""Normalize assistant replies to a JSON block format for UI rendering (no Markdown)."""

import json
from typing import Any


def _strip_code_fence(text: str) -> str:
    t = text.strip()
    if not t.startswith("```"):
        return t
    lines = t.split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _clean_block(block: dict[str, Any]) -> dict[str, Any] | None:
    btype = block.get("type")
    if not isinstance(btype, str):
        return None

    if btype == "heading":
        text = _as_str(block.get("text")).strip()
        if not text:
            return None
        return {"type": "heading", "text": text}

    if btype == "paragraph":
        text = _as_str(block.get("text"))
        return {"type": "paragraph", "text": text}

    if btype == "list":
        ordered = bool(block.get("ordered", False))
        items = block.get("items")
        if not isinstance(items, list):
            return None
        str_items = [_as_str(item).strip() for item in items if _as_str(item).strip()]
        if not str_items:
            return None
        return {"type": "list", "ordered": ordered, "items": str_items}

    if btype == "code":
        text = _as_str(block.get("text"))
        language = block.get("language")
        out: dict[str, Any] = {"type": "code", "text": text}
        if language is not None and _as_str(language).strip():
            out["language"] = _as_str(language).strip()
        return out

    if btype == "table":
        headers = block.get("headers")
        rows = block.get("rows")
        if not isinstance(headers, list) or not isinstance(rows, list):
            return None
        h = [_as_str(x).strip() for x in headers]
        if not h:
            return None
        clean_rows: list[list[str]] = []
        for row in rows:
            if not isinstance(row, list):
                continue
            cells = [_as_str(c) for c in row]
            while len(cells) < len(h):
                cells.append("")
            clean_rows.append(cells[: len(h)])
        if not clean_rows:
            return None
        return {"type": "table", "headers": h, "rows": clean_rows}

    return None


def try_parse_blocks(raw: str) -> dict[str, Any] | None:
    """If *raw* is valid JSON with a blocks array, return the normalized dict; else None."""
    text = _strip_code_fence(raw)
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None
    blocks = data.get("blocks")
    if not isinstance(blocks, list):
        return None

    cleaned: list[dict[str, Any]] = []
    for item in blocks:
        if isinstance(item, dict):
            c = _clean_block(item)
            if c is not None:
                cleaned.append(c)

    if not cleaned:
        return None
    return {"blocks": cleaned}


def normalize_assistant_output(raw: str) -> str:
    """
    Return a canonical JSON string for persistence and API responses.

    If the model did not return valid structured JSON, wrap the raw text in a
    single paragraph block.
    """
    parsed = try_parse_blocks(raw)
    if parsed is not None:
        return json.dumps(parsed, ensure_ascii=False)
    fallback = raw.strip() if raw.strip() else " "
    return json.dumps(
        {"blocks": [{"type": "paragraph", "text": fallback}]},
        ensure_ascii=False,
    )
