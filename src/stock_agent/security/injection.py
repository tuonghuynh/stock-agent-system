"""Adversarial content classification that never grants external text authority."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum

from stock_agent.observability.trust import RunAuthority


class ThreatDisposition(StrEnum):
    OPAQUE = "OPAQUE"
    HOSTILE = "HOSTILE"


@dataclass(frozen=True, slots=True)
class ScannedExternalContent:
    reference: str
    content_hash: str
    disposition: ThreatDisposition
    signals: tuple[str, ...]
    authority_fingerprint: str
    executable: bool = False


_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction_override",
        re.compile(
            r"\b(?:ignore|disregard|override)\b.{0,60}\b(?:instruction|policy|rule)", re.I
        ),
    ),
    (
        "privilege_claim",
        re.compile(
            r"\b(?:system|developer|administrator|root)\b.{0,30}"
            r"\b(?:prompt|access|message|mode)",
            re.I,
        ),
    ),
    (
        "broker_request",
        re.compile(
            r"\b(?:submit|place|cancel|execute)\b.{0,30}\b(?:order|trade|broker)", re.I
        ),
    ),
    (
        "secret_exfiltration",
        re.compile(
            r"\b(?:reveal|print|send|exfiltrate|leak)\b.{0,40}"
            r"\b(?:secret|token|credential|key|password)",
            re.I,
        ),
    ),
    (
        "authority_change",
        re.compile(
            r"\b(?:change|replace|bypass|disable)\b.{0,40}"
            r"\b(?:objective|schema|tool|workflow|risk|policy)",
            re.I,
        ),
    ),
    (
        "encoded_instruction",
        re.compile(
            r"\b(?:base64|decode|eval|exec)\b.{0,40}\b(?:payload|instruction|command)",
            re.I,
        ),
    ),
)


class AdversarialContentScanner:
    def scan(
        self, *, reference: str, raw_content: str, authority: RunAuthority
    ) -> ScannedExternalContent:
        if not reference.strip() or not raw_content:
            raise ValueError("external content requires a reference and content")
        signals = tuple(name for name, pattern in _PATTERNS if pattern.search(raw_content))
        authority_fingerprint = hashlib.sha256(
            repr(
                (
                    authority.objective,
                    authority.allowed_tools,
                    authority.output_schema,
                    authority.policy_version,
                    authority.workflow_version,
                )
            ).encode()
        ).hexdigest()
        return ScannedExternalContent(
            reference=reference,
            content_hash=hashlib.sha256(raw_content.encode()).hexdigest(),
            disposition=(ThreatDisposition.HOSTILE if signals else ThreatDisposition.OPAQUE),
            signals=signals,
            authority_fingerprint=authority_fingerprint,
        )
