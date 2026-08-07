"""Deterministic provider-neutral management transcript classification."""

from __future__ import annotations

import re
from dataclasses import dataclass

from rfi.acquisition.contracts import (
    TranscriptEventDisposition,
    TranscriptEventKind,
    TranscriptMetadataObservation,
)

EARNINGS_TRANSCRIPT = "earnings_transcript"
MANAGEMENT_TRANSCRIPT = "management_transcript"

_INVESTOR_DAY = re.compile(r"\b(?:investor|capital markets?)\s+day\b", re.I)
_FIRESIDE_CHAT = re.compile(r"\bfireside\s+chat\b", re.I)
_ANALYST_EVENT = re.compile(
    r"\b(?:analyst\s+(?:day|meeting|event|briefing)|sell[- ]side\s+event)\b", re.I
)
_CONFERENCE = re.compile(
    r"\b(?:conference(?!\s+call\b)|summit|symposium|industry\s+forum|"
    r"technology\s+forum)\b",
    re.I,
)
_EARNINGS_CALL = re.compile(
    r"\b(?:earnings(?:\s+conference)?\s+call|"
    r"(?:quarterly|annual|financial|fiscal)\s+(?:results?|earnings)\s+"
    r"(?:conference\s+)?call)\b",
    re.I,
)


@dataclass(frozen=True)
class TranscriptClassification:
    """Resolved repository classification derived from trusted transcript metadata."""

    canonical_artifact_id: str
    event_kind: TranscriptEventKind
    basis: str

    @property
    def qualifies_as_earnings(self) -> bool:
        return self.canonical_artifact_id == EARNINGS_TRANSCRIPT


def classify_transcript_event(
    observation: TranscriptMetadataObservation | None,
) -> TranscriptClassification:
    """Resolve a narrow earnings corpus and a broad retained management corpus."""
    if observation is None:
        return TranscriptClassification(
            MANAGEMENT_TRANSCRIPT,
            TranscriptEventKind.OTHER_MANAGEMENT,
            "trusted_event_metadata_unavailable",
        )
    label = " ".join(observation.event_label.split())
    disposition = observation.event_disposition
    if disposition is TranscriptEventDisposition.EXPLICIT_EARNINGS:
        return TranscriptClassification(
            EARNINGS_TRANSCRIPT,
            TranscriptEventKind.EARNINGS_CALL,
            "trusted_explicit_earnings",
        )
    kind = _non_earnings_kind(label)
    if disposition is TranscriptEventDisposition.EXPLICIT_NON_EARNINGS:
        return TranscriptClassification(
            MANAGEMENT_TRANSCRIPT,
            kind,
            "trusted_explicit_non_earnings",
        )
    if kind is not TranscriptEventKind.OTHER_MANAGEMENT:
        return TranscriptClassification(
            MANAGEMENT_TRANSCRIPT,
            kind,
            "deterministic_event_label_non_earnings",
        )
    if _EARNINGS_CALL.search(label):
        return TranscriptClassification(
            EARNINGS_TRANSCRIPT,
            TranscriptEventKind.EARNINGS_CALL,
            "deterministic_event_label_earnings",
        )
    return TranscriptClassification(
        MANAGEMENT_TRANSCRIPT,
        TranscriptEventKind.OTHER_MANAGEMENT,
        "deterministic_fail_closed_unknown",
    )


def _non_earnings_kind(label: str) -> TranscriptEventKind:
    """Classify specific non-earnings kinds before broader conference vocabulary."""
    if _INVESTOR_DAY.search(label):
        return TranscriptEventKind.INVESTOR_DAY
    if _FIRESIDE_CHAT.search(label):
        return TranscriptEventKind.FIRESIDE_CHAT
    if _ANALYST_EVENT.search(label):
        return TranscriptEventKind.ANALYST_EVENT
    if _CONFERENCE.search(label):
        return TranscriptEventKind.CONFERENCE
    return TranscriptEventKind.OTHER_MANAGEMENT
