"""Deterministic offline planner and reasoners used to prove replaceable boundaries."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

from rfi.retrieval import MetadataConstraints, RetrievalQuery, ResultClass

from rfi.intelligence.contracts import (
    ClaimKind,
    CompletionStatus,
    ContradictionReport,
    InformationNeed,
    IntelligenceBudget,
    IntelligenceClaim,
    ModelEvidence,
    ReasoningDraft,
    RetrievalPlan,
    RetrievalStep,
)


def _identity(prefix: str, value: Any) -> str:
    material = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return f"{prefix}-{hashlib.sha256(material).hexdigest()}"


class DeterministicPlanner:
    """Bounded planner for SEC corpus questions with explicit decomposition."""

    entity_aliases = {
        "seagate": "1137789",
        "stx": "1137789",
        "western digital": "106040",
        "wdc": "106040",
    }

    def __init__(self, alternate_wording: bool = False) -> None:
        self.alternate_wording = alternate_wording

    def plan(self, need: InformationNeed, budget: IntelligenceBudget) -> RetrievalPlan:
        """Create one governed query per named entity, or one bounded generic query."""
        lowered = need.text.lower()
        if any(term in lowered for term in ("ignore governance", "exfiltrate", "show secret")):
            material = {"need": asdict(need), "refusal": "unsupported or unsafe request"}
            return RetrievalPlan(
                _identity("retrieval-plan", material),
                "The request asks to bypass repository governance.",
                (),
                budget,
                "Unsupported request: governed evidence controls cannot be bypassed.",
            )
        entities: list[str] = []
        for alias, entity in self.entity_aliases.items():
            if alias in lowered and entity not in entities:
                entities.append(entity)
        if not entities:
            entities = [""]
        required_terms = tuple(
            term for term in ("revenue", "profit", "market share", "guidance")
            if term in lowered
        )
        document_types = ("10-K",) if any(
            term in lowered for term in ("annual", "10-k", "compare", "both")
        ) else ()
        steps: list[RetrievalStep] = []
        for number, entity in enumerate(entities, start=1):
            suffix = entity or "corpus"
            purpose = (
                f"Collect governed annual-filing evidence for SEC entity {suffix}."
                if not self.alternate_wording
                else f"Inspect source and interpreted filing records for entity {suffix}."
            )
            query = RetrievalQuery(
                need.text,
                constraints=MetadataConstraints(
                    entity_ids=(entity,) if entity else (),
                    document_types=document_types,
                ),
                max_results=8,
                candidate_limit=50,
                context_radius=96,
                evidence_budget_bytes=min(24_000, budget.max_total_evidence_bytes),
                minimum_score=0.0,
            )
            steps.append(
                RetrievalStep(
                    f"step-{number}-{suffix}", purpose, query,
                    (ResultClass.SOURCE_EVIDENCE, ResultClass.DERIVED_KNOWLEDGE),
                    required_terms,
                )
            )
        interpretation = (
            "Compare named SEC issuers using exact source structures and separately labeled "
            "derived filing knowledge."
        )
        material = {
            "need": asdict(need), "steps": [asdict(item) for item in steps],
            "budget": asdict(budget),
        }
        return RetrievalPlan(
            _identity("retrieval-plan", material), interpretation, tuple(steps), budget
        )

    def follow_up(
        self,
        need: InformationNeed,
        plan: RetrievalPlan,
        completed_steps: tuple[RetrievalStep, ...],
        missing_requirements: tuple[str, ...],
    ) -> RetrievalStep | None:
        """Try one wider governed query; never loop or invent another tool."""
        if not missing_requirements or any(
            step.step_id == "follow-up-coverage" for step in completed_steps
        ):
            return None
        query = RetrievalQuery(
            need.text + " " + " ".join(missing_requirements[:4]),
            max_results=8,
            candidate_limit=50,
            context_radius=64,
            evidence_budget_bytes=min(16_000, plan.budget.max_total_evidence_bytes),
            minimum_score=0.0,
        )
        return RetrievalStep(
            "follow-up-coverage",
            "Attempt one broader governed retrieval for unmet evidence requirements.",
            query,
            (ResultClass.SOURCE_EVIDENCE, ResultClass.DERIVED_KNOWLEDGE),
            tuple(item for item in missing_requirements if item in {
                "revenue", "profit", "market share", "guidance"
            }),
        )


class DeterministicReasoner:
    """Source-grounded offline reasoning with optional wording substitution."""

    def __init__(self, alternate_wording: bool = False) -> None:
        self.alternate_wording = alternate_wording

    def reason(
        self,
        need: InformationNeed,
        plan: RetrievalPlan,
        evidence: ModelEvidence,
    ) -> ReasoningDraft:
        """Synthesize public package objects while retaining their authority labels."""
        if evidence.truncated:
            return ReasoningDraft(
                "The bounded model input was truncated; no supportable answer was generated.",
                (), ("Model disclosure budget was exhausted.",),
                ("The complete governed evidence projection did not fit the model budget.",),
                (), CompletionStatus.INCOMPLETE,
            )
        items = json.loads(evidence.content)
        references = {item.evidence_id: item for item in evidence.evidence}
        claims: list[IntelligenceClaim] = []
        uncertainties: list[str] = []
        gaps: list[str] = []
        contradictions: list[ContradictionReport] = []
        observations: list[tuple[dict[str, Any], str]] = []
        entities: list[tuple[dict[str, Any], str]] = []
        source_seen: set[str] = set()
        for entry in items:
            authority = entry.get("authority")
            if authority is None:
                package_id = entry["package_id"]
                gaps.extend(entry["coverage_gaps"])
                gaps.extend(entry["omissions"])
                package_evidence = tuple(
                    item.evidence_id for item in evidence.evidence
                    if item.package_id == package_id
                )
                for message in entry["contradictions"]:
                    contradictions.append(
                        ContradictionReport(message, (package_id,), package_evidence)
                    )
                continue
            evidence_id = entry["evidence_id"]
            reference = references.get(evidence_id)
            if reference is None:
                continue
            if authority == "source-evidence":
                item = entry["source_object"]
                if item["document_id"] in source_seen:
                    continue
                source_seen.add(item["document_id"])
                text = (
                    f"Exact source evidence includes a {item['role']} structure in document "
                    f"{item['document_id']}."
                )
                claims.append(
                    self._claim(
                        text, ClaimKind.SOURCE_EVIDENCE, (evidence_id,),
                        "The cited source object is an exact byte-verified structure in the "
                        "consumed evidence package.", 1.0,
                    )
                )
                continue
            item = entry["derived_object"]
            if item["status"] in {"conflicted", "uncertain"}:
                uncertainties.append(
                    f"{item['object_id']} has {item['status']} derived-knowledge status."
                )
            if item["object_type"] == "entity":
                entities.append((item, evidence_id))
            elif item["object_type"] == "observation":
                observations.append((item, evidence_id))
        unique_entities: dict[str, tuple[dict[str, Any], str]] = {
            item["semantic_key"]: (item, reference) for item, reference in entities
        }
        for item, reference in unique_entities.values():
            names = item["payload"].get("names", [])
            name = names[0] if names else "unnamed issuer"
            text = (
                f"Repository-derived knowledge identifies {name} with SEC CIK "
                f"{item['payload'].get('cik', 'unknown')}."
            )
            claims.append(
                self._claim(
                    text, ClaimKind.DERIVED_KNOWLEDGE, (reference,),
                    "The cited item is repository-derived entity knowledge and is not presented "
                    "as source evidence.", item["confidence"],
                    None if item["status"] == "confirmed" else item["status"],
                )
            )
        annual: list[tuple[dict[str, Any], str]] = [
            value for value in observations if value[0]["payload"].get("form_type") == "10-K"
        ]
        for item, reference in annual[:4]:
            payload = item["payload"]
            text = (
                f"Derived filing knowledge records a 10-K for period "
                f"{payload.get('period_of_report', 'unknown')} in {payload.get('document_id')}."
            )
            claims.append(
                self._claim(
                    text, ClaimKind.DERIVED_KNOWLEDGE, (reference,),
                    "The cited observation supplies the form, period, and document identity.",
                    item["confidence"],
                )
            )
        annual_documents = {item["payload"].get("document_id") for item, unused in annual}
        annual_periods = {item["payload"].get("period_of_report") for item, unused in annual}
        if len(annual_documents) >= 2 and annual_periods:
            citations = tuple(reference for unused, reference in annual[:4])
            shared = ", ".join(sorted(str(item) for item in annual_periods if item))
            inference_text = (
                f"The consumed filing observations support a bounded comparison across "
                f"{len(annual_documents)} annual filings; observed report period(s): {shared}."
            )
            claims.append(
                self._claim(
                    inference_text, ClaimKind.MODEL_INFERENCE, citations,
                    "This synthesis compares cited derived filing observations; it does not "
                    "infer business performance.", 0.85,
                    "Inference is limited to corpus filing coverage and the narrow TASK-005 "
                    "ontology.",
                )
            )
        requested = need.text.lower()
        for term in ("revenue", "profit", "market share", "guidance"):
            if term in requested and not any(term in json.dumps(item["payload"]).lower()
                                             for item, unused in observations):
                gaps.append(f"The current derived ontology contains no {term} evidence.")
        if not claims:
            gaps.append("No supportable claim could be constructed from consumed evidence.")
        if contradictions:
            gaps.append("Contradictory or ambiguous evidence remains unresolved.")
        claims = list({item.claim_id: item for item in claims}.values())
        contradictions = list({
            (item.description, item.package_ids): item for item in contradictions
        }.values())
        status = (
            CompletionStatus.INCOMPLETE
            if gaps or contradictions
            else CompletionStatus.COMPLETE
        )
        prefix = (
            "Grounded corpus result:"
            if not self.alternate_wording
            else "Evidence-bound result:"
        )
        response = prefix + " " + (
            " ".join(item.text for item in claims)
            if claims else "The available evidence does not support an answer."
        )
        return ReasoningDraft(
            response, tuple(claims), tuple(dict.fromkeys(uncertainties)),
            tuple(dict.fromkeys(gaps)), tuple(contradictions), status,
        )

    def _claim(
        self,
        text: str,
        kind: ClaimKind,
        evidence_ids: tuple[str, ...],
        support: str,
        confidence: float,
        uncertainty: str | None = None,
    ) -> IntelligenceClaim:
        claim_id = _identity(
            "claim", {"text": text, "kind": kind, "evidence": evidence_ids}
        )
        return IntelligenceClaim(
            claim_id, text, kind, evidence_ids, support, confidence, uncertainty
        )
