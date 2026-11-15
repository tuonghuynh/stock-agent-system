"""Deterministic recursive redaction for audit and structured log fields."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

REDACTED = "[REDACTED]"

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | dict[str, JsonValue] | list[JsonValue]

_SENSITIVE_KEY = re.compile(
    r"(?:secret|token|password|credential|api[_-]?key|account(?:[_-]?(?:id|number))?|"
    r"raw[_-]?(?:prompt|content)|personal|ssn)",
    re.IGNORECASE,
)
_SENSITIVE_VALUE = re.compile(
    r"(?:bearer\s+[a-z0-9._~+/=-]+|(?:api[_-]?key|token|secret|password)\s*[:=]\s*\S+|"
    r"\b(?:acct|account)[-_ ]?[a-z0-9]{6,}\b)",
    re.IGNORECASE,
)


def redact(value: object, *, key: str = "") -> JsonValue:
    """Return a JSON-compatible copy with sensitive keys and values removed."""
    if key and _SENSITIVE_KEY.search(key):
        return REDACTED
    if isinstance(value, Mapping):
        return {
            str(item_key): redact(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return REDACTED if _SENSITIVE_VALUE.search(value) else value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


def assert_redacted(metadata: Mapping[str, object]) -> None:
    """Reject metadata that differs from its safely redacted representation."""
    safe = redact(metadata)
    if safe != dict(metadata):
        raise ValueError("audit metadata contains a sensitive field or value")
