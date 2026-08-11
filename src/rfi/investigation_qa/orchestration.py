"""Minimal state machine for QA #1, at most one repair, and terminal QA #2."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from rfi.investigation_qa.contracts import QA2Review, QADisposition, QAReview, RepairResult


class LifecycleError(ValueError):
    """The caller attempted to escape the one-cycle lifecycle."""


class LifecycleState(StrEnum):
    """Externally inspectable state of one case."""

    FIRST_PASS_FIXED = "first_pass_fixed"
    QA1_COMPLETE = "qa1_complete"
    REPAIR_COMPLETE = "repair_complete"
    TERMINAL = "terminal"


@dataclass(frozen=True)
class CaseIdentity:
    """Immutable association among case, question, and preserved first-pass answer."""

    case_id: str
    question: str
    question_sha256: str
    original_answer_sha256: str

    @classmethod
    def from_content(cls, case_id: str, question: str, answer: str) -> CaseIdentity:
        return cls(
            case_id,
            question,
            hashlib.sha256(question.encode()).hexdigest(),
            hashlib.sha256(answer.encode()).hexdigest(),
        )


class SingleRepairLifecycle:
    """Enforce exactly two QA reviews and never more than one repair invocation."""

    def __init__(self, identity: CaseIdentity, original_answer: str) -> None:
        if hashlib.sha256(original_answer.encode()).hexdigest() != identity.original_answer_sha256:
            raise LifecycleError("original answer does not match the fixed case identity")
        self.identity = identity
        self.original_answer = original_answer
        self.state = LifecycleState.FIRST_PASS_FIXED
        self.qa1: QAReview | None = None
        self.repair: RepairResult | None = None
        self.qa2: QA2Review | None = None

    def record_qa1(self, review: QAReview) -> None:
        if self.state is not LifecycleState.FIRST_PASS_FIXED:
            raise LifecycleError("QA #1 may be recorded exactly once after the fixed first pass")
        if review.case_id != self.identity.case_id:
            raise LifecycleError("QA #1 case association mismatch")
        self.qa1 = review
        self.state = LifecycleState.QA1_COMPLETE

    @property
    def repair_required(self) -> bool:
        return bool(self.qa1 and self.qa1.disposition is QADisposition.REPAIR_REQUIRED)

    @property
    def qa2_submission(self) -> str:
        if self.repair is not None:
            return self.repair.repaired_answer
        if self.qa1 and self.qa1.disposition is not QADisposition.REPAIR_REQUIRED:
            return self.original_answer
        raise LifecycleError("QA #2 submission is unavailable before required repair")

    def record_repair(self, repair: RepairResult) -> None:
        if self.state is not LifecycleState.QA1_COMPLETE or not self.repair_required:
            raise LifecycleError("repair is permitted once and only after repair_required QA #1")
        if repair.case_id != self.identity.case_id:
            raise LifecycleError("repair case association mismatch")
        self.repair = repair
        self.state = LifecycleState.REPAIR_COMPLETE

    def record_qa2(self, review: QA2Review) -> None:
        if self.qa1 is None:
            raise LifecycleError("QA #2 requires QA #1")
        allowed = {LifecycleState.QA1_COMPLETE, LifecycleState.REPAIR_COMPLETE}
        if self.state not in allowed:
            raise LifecycleError("QA #2 may be recorded exactly once and is terminal")
        if self.repair_required and self.state is not LifecycleState.REPAIR_COMPLETE:
            raise LifecycleError("QA #2 cannot bypass a required bounded repair")
        if review.case_id != self.identity.case_id:
            raise LifecycleError("QA #2 case association mismatch")
        expected = tuple(item.finding_id for item in self.qa1.findings)
        actual = tuple(item.finding_id for item in review.resolutions)
        if sorted(expected) != sorted(actual):
            raise LifecycleError("QA #2 finding resolutions do not match QA #1")
        self.qa2 = review
        self.state = LifecycleState.TERMINAL

    def snapshot(self) -> dict[str, Any]:
        """Return a durable association record without interpretation."""
        return {
            "identity": asdict(self.identity),
            "state": self.state.value,
            "original_answer": self.original_answer,
            "qa1": asdict(self.qa1) if self.qa1 else None,
            "repair_invoked": self.repair is not None,
            "repair_cycle_count": int(self.repair is not None),
            "repair": asdict(self.repair) if self.repair else None,
            "qa2_submission_sha256": (
                hashlib.sha256(self.qa2_submission.encode()).hexdigest()
                if self.qa1 and (not self.repair_required or self.repair)
                else None
            ),
            "qa2": asdict(self.qa2) if self.qa2 else None,
            "terminal": self.state is LifecycleState.TERMINAL,
            "escalation_available": False,
        }
