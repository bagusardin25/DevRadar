"""Shared JSON-object parsing for LLM responses.

Providers differ in how faithfully they honour a JSON response format. Models
served without native JSON mode routinely wrap the object in a markdown fence
or add a sentence before it, so parsing has to survive both.
"""

from __future__ import annotations

import json
import re

_FENCE_OPEN = re.compile(r"^```(?:json)?\s*", re.IGNORECASE)
_FENCE_CLOSE = re.compile(r"\s*```$")


def parse_json_object(content: str) -> dict[str, object]:
    """Parse an LLM reply into a JSON object, repairing common wrappers.

    Raises ValueError when the reply cannot be read as a JSON object — callers
    treat that as a provider failure rather than an empty extraction.
    """
    text = (content or "").strip()
    if text.startswith("```"):
        text = _FENCE_CLOSE.sub("", _FENCE_OPEN.sub("", text))

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = _first_object(text)

    if not isinstance(data, dict):
        raise ValueError("LLM response is not a JSON object")
    return data


def _first_object(text: str) -> object:
    """Last resort for prompt-only JSON mode: read the first balanced object.

    Scans rather than regexes so nested braces survive, and skips braces that
    appear inside string literals.
    """
    start = text.find("{")
    if start < 0:
        raise ValueError("LLM response is not a JSON object")

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : index + 1])
    raise ValueError("LLM response is not a JSON object")
