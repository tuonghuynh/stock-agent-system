"""Trust boundary for hostile external evidence content."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction_override",
        re.compile(r"\b(?:ignore|disregard)\b.{0,40}\b(?:instructions?|policy)\b", re.I),
    ),
    (
        "privilege_escalation",
        re.compile(r"\b(?:system|developer|admin)\s+(?:prompt|message|access)\b", re.I),
    ),
    ("tool_request", re.compile(r"\b(?:call|invoke|use)\b.{0,30}\b(?:broker|tool|api)\b", re.I)),
    (
        "secret_request",
        re.compile(
            r"\b(?:reveal|print|send|exfiltrate)\b.{0,30}\b(?:secret|token|key|credential)\b",
            re.I,
        ),
    ),
    (
        "schema_change",
        re.compile(r"\b(?:change|replace|bypass)\b.{0,30}\b(?:schema|objective|workflow)\b", re.I),
    ),
)


@dataclass(frozen=True, slots=True)
class RunAuthority:
    objective: str
    allowed_tools: tuple[str, ...]
    output_schema: str
    policy_version: str
    workflow_version: str


@dataclass(frozen=True, slots=True)
class SafeExternalContent:
    reference: str
    content_hash: str
    detected_signals: tuple[str, ...]
    authority: RunAuthority
    executable: bool = False


class ContentFirewall:
    """Classify hostile text and retain only an opaque reference and digest."""

    def inspect(
        self,
        *,
        reference: str,
        raw_content: str,
        authority: RunAuthority,
    ) -> SafeExternalContent:
        if not reference.strip():
            raise ValueError("reference must not be blank")
        if not raw_content:
            raise ValueError("raw_content must not be empty")
        signals = tuple(
            name for name, pattern in _INJECTION_PATTERNS if pattern.search(raw_content)
        )
        return SafeExternalContent(
            reference=reference,
            content_hash=hashlib.sha256(raw_content.encode("utf-8")).hexdigest(),
            detected_signals=signals,
            authority=authority,
        )
