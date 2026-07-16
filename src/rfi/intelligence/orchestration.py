"""Bounded orchestration and fail-closed grounding validation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from typing import Any

from rfi.retrieval import EvidencePackage, ResultClass, RetrievalError

from rfi.intelligence.contracts import (
    ClaimKind,
    CompletionStatus,
    ContradictionReport,
    EvidenceGateway,
    EvidenceReference,
    ExecutionEvent,
    ExecutionRecord,
    ExecutionTrace,
    InformationNeed,
    IntelligenceBudget,
    IntelligenceClaim,
    IntelligenceError,
    IntelligenceResult,
    ModelEvidence,
    Planner,
    Reasoner,
    ReasoningDraft,
    RetrievalPlan,
    RetrievalStep,
    StopReason,
)


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), default=str) + "\n").encode()


def _identity(prefix: str, value: Any) -> str:
    return f"{prefix}-{hashlib.sha256(_canonical(value)).hexdigest()}"


class PackageGateway:
    """Adapt TASK-006 public retrieval and assembly methods without exposing storage."""

    def __init__(self, retrieve: Any, assemble: Any) -> None:
        self._retrieve = retrieve
        self._assemble = assemble

    def retrieve(self, query: Any) -> EvidencePackage:
        """Retrieve and assemble solely through supplied public callables."""
        return self._assemble(self._retrieve(query))


class IntelligenceOrchestrator:
    """Execute provider-neutral plans under hard budgets and visible failure semantics."""

    def __init__(self, planner: Planner, reasoner: Reasoner, gateway: EvidenceGateway) -> None:
        self.planner = planner
        self.reasoner = reasoner
        self.gateway = gateway

    def execute(
        self,
        need: InformationNeed,
        budget: IntelligenceBudget | None = None,
    ) -> ExecutionRecord:
        """Execute one need and always return an operator-inspectable governed record."""
        active_budget = budget or IntelligenceBudget()
        seed = {"need": asdict(need), "budget": asdict(active_budget)}
        execution_id = _identity("intelligence-execution", seed)
        events: list[ExecutionEvent] = []
        queries: list[Any] = []
        packages: list[EvidencePackage] = []
        completed: list[RetrievalStep] = []
        failures: list[str] = []

        def event(category: str, detail: str, step: str | None = None,
                  package: str | None = None) -> None:
            events.append(ExecutionEvent(len(events) + 1, category, detail, step, package))

        try:
            plan = self.planner.plan(need, active_budget)
            self._validate_plan(plan, active_budget)
            event("plan", f"accepted {len(plan.steps)} bounded retrieval step(s)")
        except Exception as error:
            return self._failure_record(
                execution_id, need, None, events, queries, packages, None, None,
                StopReason.FAILURE, f"planner failure: {error}",
            )
        if plan.refusal_reason:
            event("refusal", plan.refusal_reason)
            return self._terminal_record(
                execution_id, need, plan, events, queries, packages, None, None,
                (), (), (), CompletionStatus.REFUSED, plan.refusal_reason,
                StopReason.REFUSED, failures,
            )
        pending = list(plan.steps)
        missing: tuple[str, ...] = ()
        while pending and len(completed) < active_budget.max_iterations:
            step = pending.pop(0)
            if len(packages) >= active_budget.max_packages:
                event("stop", "package limit reached before next step", step.step_id)
                break
            event("retrieval-request", step.purpose, step.step_id)
            queries.append(step.query)
            try:
                package = self.gateway.retrieve(step.query)
                self._validate_package(package, step)
            except (IntelligenceError, RetrievalError, Exception) as error:
                failures.append(f"{step.step_id}: retrieval failure: {error}")
                event("retrieval-failure", str(error), step.step_id)
                break
            if sum(item.bytes_used for item in packages) + package.bytes_used > (
                active_budget.max_total_evidence_bytes
            ):
                failures.append("total evidence-byte budget exhausted")
                event("budget", "package rejected by total evidence-byte budget", step.step_id)
                break
            packages.append(package)
            completed.append(step)
            event(
                "evidence-package",
                f"consumed {package.bytes_used} verified context bytes; "
                f"complete={package.complete}",
                step.step_id,
                package.package_id,
            )
            missing = self._missing(step, package)
            if missing:
                event("coverage", "missing: " + ", ".join(missing), step.step_id)
                if not pending and len(completed) < active_budget.max_iterations:
                    try:
                        follow_up = self.planner.follow_up(
                            need, plan, tuple(completed), missing
                        )
                    except Exception as error:
                        failures.append(f"follow-up planner failure: {error}")
                        event("planner-failure", str(error), step.step_id)
                        break
                    if follow_up is not None:
                        self._validate_step(follow_up)
                        pending.append(follow_up)
                        event("follow-up", follow_up.purpose, follow_up.step_id)
                    else:
                        event("follow-up", "planner declined additional retrieval", step.step_id)
                elif not pending:
                    failures.append("iteration limit exhausted")
                    event("stop", "iteration limit exhausted", step.step_id)
        if pending and len(completed) >= active_budget.max_iterations:
            failures.append("iteration limit exhausted")
            event("stop", "iteration limit exhausted")
        model_evidence = self._project(packages, active_budget.max_model_input_chars)
        event(
            "model-input",
            f"projected {model_evidence.chars} chars; truncated={model_evidence.truncated}",
        )
        try:
            draft = self.reasoner.reason(need, plan, model_evidence)
            event("model-output", f"received {len(draft.claims)} claim(s)")
            self._validate_draft(draft, model_evidence.evidence)
            event("grounding-validation", "all claims mapped to consumed evidence")
        except Exception as error:
            return self._failure_record(
                execution_id, need, plan, events, queries, packages, model_evidence,
                None, StopReason.FAILURE, f"model or grounding failure: {error}",
            )
        gaps = tuple(dict.fromkeys((*draft.evidence_gaps, *missing)))
        status = draft.requested_status
        stop = StopReason.REQUIREMENTS_SATISFIED
        if failures and "iteration limit exhausted" in failures:
            status = CompletionStatus.INCOMPLETE
            stop = StopReason.ITERATION_LIMIT
        elif failures and "evidence-byte budget" in failures[-1]:
            status = CompletionStatus.INCOMPLETE
            stop = StopReason.EVIDENCE_BUDGET
        elif gaps or draft.contradictions or model_evidence.truncated:
            status = CompletionStatus.INCOMPLETE
            stop = StopReason.EVIDENCE_INSUFFICIENT
        if not packages:
            status = CompletionStatus.INCOMPLETE
            stop = StopReason.EVIDENCE_INSUFFICIENT
            gaps = tuple(dict.fromkeys((*gaps, "no evidence package was consumed")))
        event("stop", stop.value)
        return self._terminal_record(
            execution_id, need, plan, events, queries, packages, model_evidence, draft,
            draft.claims, draft.uncertainties, gaps, status, draft.response, stop, failures,
        )

    def _validate_plan(self, plan: RetrievalPlan, budget: IntelligenceBudget) -> None:
        if not plan.plan_id or not plan.interpretation:
            raise IntelligenceError("malformed planner output")
        if plan.budget != budget:
            raise IntelligenceError("planner altered governing budget")
        if len(plan.steps) > budget.max_packages or len(plan.steps) > budget.max_iterations:
            raise IntelligenceError("plan exceeds package or iteration budget")
        if not plan.steps and not plan.refusal_reason:
            raise IntelligenceError("plan has neither steps nor refusal")
        identifiers = [step.step_id for step in plan.steps]
        if len(identifiers) != len(set(identifiers)):
            raise IntelligenceError("plan contains duplicate step identifiers")
        for step in plan.steps:
            self._validate_step(step)

    def _validate_step(self, step: RetrievalStep) -> None:
        query = step.query
        if not step.step_id or not step.purpose or not query.text.strip():
            raise IntelligenceError("malformed retrieval step")
        if query.constraints.unsupported:
            raise IntelligenceError("unsupported retrieval constraints in plan")
        if query.max_results < 1 or query.candidate_limit < query.max_results:
            raise IntelligenceError("invalid retrieval result bounds")
        if query.evidence_budget_bytes < 1:
            raise IntelligenceError("invalid per-package evidence budget")
        if not set(step.required_result_classes).issubset(set(query.result_classes)):
            raise IntelligenceError("step requirements exceed requested result classes")

    def _validate_package(self, package: EvidencePackage, step: RetrievalStep) -> None:
        if package.query != step.query or package.trace.query != step.query:
            raise IntelligenceError("evidence package does not match requested query")
        if not package.package_id.startswith("evidence-package-"):
            raise IntelligenceError("invalid evidence-package identity")
        if package.trace.failures:
            raise IntelligenceError("evidence package contains retrieval failures")
        if package.bytes_used > package.byte_budget:
            raise IntelligenceError("evidence package exceeds declared byte budget")
        context_keys = {
            (
                item.provenance.source_object_id,
                item.provenance.document_id,
                item.provenance.artifact_id,
                item.provenance.byte_start,
                item.provenance.byte_end,
                item.provenance.content_sha256,
            )
            for item in package.contexts
        }
        for result in package.source_evidence:
            item = result.source_object
            key = (
                item.source_object_id, item.document_id, item.artifact_id,
                item.byte_start, item.byte_end, item.content_sha256,
            )
            if key not in context_keys:
                raise IntelligenceError("source result lacks verified package context")
        for result in package.derived_knowledge:
            if not result.derived_object.provenance:
                raise IntelligenceError("derived result lacks provenance")
            for item in result.derived_object.provenance:
                key = (
                    item.source_object_id, item.document_id, item.artifact_id,
                    item.byte_start, item.byte_end, item.content_sha256,
                )
                if key not in context_keys:
                    raise IntelligenceError("derived result lacks verified package context")

    def _missing(self, step: RetrievalStep, package: EvidencePackage) -> tuple[str, ...]:
        missing: list[str] = []
        if ResultClass.SOURCE_EVIDENCE in step.required_result_classes and not (
            package.source_evidence
        ):
            missing.append("source-evidence")
        if ResultClass.DERIVED_KNOWLEDGE in step.required_result_classes and not (
            package.derived_knowledge
        ):
            missing.append("derived-knowledge")
        searchable = json.dumps(
            {
                "source": [asdict(item.source_object) for item in package.source_evidence],
                "knowledge": [asdict(item.derived_object) for item in package.derived_knowledge],
                "contexts": [item.text for item in package.contexts],
            },
            sort_keys=True,
            default=str,
        ).lower()
        missing.extend(term for term in step.required_terms if term.lower() not in searchable)
        missing.extend(package.coverage_gaps)
        missing.extend(package.omissions)
        return tuple(dict.fromkeys(missing))

    def _project(self, packages: list[EvidencePackage], max_chars: int) -> ModelEvidence:
        references: list[EvidenceReference] = []
        content_items: list[dict[str, Any]] = []
        for package in packages:
            for result in package.source_evidence:
                item = result.source_object
                evidence_id = f"{package.package_id}:source:{item.source_object_id}"
                references.append(
                    EvidenceReference(
                        evidence_id, package.package_id, ClaimKind.SOURCE_EVIDENCE,
                        item.source_object_id, (item.document_id,), (item.source_object_id,),
                    )
                )
                content_items.append(
                    {"evidence_id": evidence_id, "authority": "source-evidence",
                     "source_object": asdict(item)}
                )
            for result in package.derived_knowledge:
                item = result.derived_object
                evidence_id = f"{package.package_id}:knowledge:{item.object_id}"
                references.append(
                    EvidenceReference(
                        evidence_id, package.package_id, ClaimKind.DERIVED_KNOWLEDGE,
                        item.object_id,
                        tuple(sorted({value.document_id for value in item.provenance})),
                        tuple(value.source_object_id for value in item.provenance),
                    )
                )
                content_items.append(
                    {"evidence_id": evidence_id, "authority": "derived-knowledge",
                     "derived_object": asdict(item)}
                )
            content_items.append(
                {"package_id": package.package_id, "coverage_gaps": package.coverage_gaps,
                 "contradictions": package.contradictions, "omissions": package.omissions,
                 "contexts": [asdict(item) for item in package.contexts]}
            )
        rendered = json.dumps(content_items, sort_keys=True, default=str)
        truncated = len(rendered) > max_chars
        if truncated:
            rendered = rendered[:max_chars]
        return ModelEvidence(
            tuple(references), tuple(item.package_id for item in packages), rendered,
            len(rendered), truncated,
        )

    def _validate_draft(
        self, draft: ReasoningDraft, evidence: tuple[EvidenceReference, ...]
    ) -> None:
        available = {item.evidence_id: item for item in evidence}
        if not draft.response.strip():
            raise IntelligenceError("model returned an empty response")
        identifiers: set[str] = set()
        for claim in draft.claims:
            if not claim.claim_id or claim.claim_id in identifiers:
                raise IntelligenceError("missing or duplicate claim identifier")
            identifiers.add(claim.claim_id)
            if not claim.evidence_ids:
                raise IntelligenceError(f"claim has no evidence mapping: {claim.claim_id}")
            if not claim.support_explanation.strip():
                raise IntelligenceError(f"claim lacks support explanation: {claim.claim_id}")
            if not 0.0 <= claim.confidence <= 1.0:
                raise IntelligenceError(f"claim confidence is invalid: {claim.claim_id}")
            resolved = []
            for evidence_id in claim.evidence_ids:
                if evidence_id not in available:
                    raise IntelligenceError(
                        f"claim references unconsumed evidence: {claim.claim_id}"
                    )
                resolved.append(available[evidence_id])
            if claim.kind == ClaimKind.SOURCE_EVIDENCE and any(
                item.authority != ClaimKind.SOURCE_EVIDENCE for item in resolved
            ):
                raise IntelligenceError("source claim cites non-source authority")
            if claim.kind == ClaimKind.DERIVED_KNOWLEDGE and any(
                item.authority != ClaimKind.DERIVED_KNOWLEDGE for item in resolved
            ):
                raise IntelligenceError("derived claim cites non-derived authority")
            if claim.kind == ClaimKind.MODEL_INFERENCE and claim.uncertainty is None:
                raise IntelligenceError("model inference lacks explicit uncertainty")

    def _terminal_record(
        self, execution_id: str, need: InformationNeed, plan: RetrievalPlan,
        events: list[ExecutionEvent], queries: list[Any], packages: list[EvidencePackage],
        model_evidence: ModelEvidence | None, draft: ReasoningDraft | None,
        claims: tuple[IntelligenceClaim, ...], uncertainties: tuple[str, ...],
        gaps: tuple[str, ...], status: CompletionStatus, response: str,
        stop: StopReason, failures: list[str],
    ) -> ExecutionRecord:
        contradictions = draft.contradictions if draft else ()
        selected_ids = {item for claim in claims for item in claim.evidence_ids}
        evidence = tuple(
            item for item in (model_evidence.evidence if model_evidence else ())
            if item.evidence_id in selected_ids
        )
        material = {
            "execution_id": execution_id, "status": status, "response": response,
            "claims": [asdict(item) for item in claims], "stop": stop,
        }
        result = IntelligenceResult(
            _identity("intelligence-result", material), execution_id, status, response,
            claims, evidence, uncertainties, gaps, contradictions,
            tuple(item.trace.trace_id for item in packages),
            tuple(item.package_id for item in packages), stop,
        )
        trace = ExecutionTrace(
            execution_id, need, plan, tuple(events), tuple(queries),
            tuple(item.package_id for item in packages), tuple(packages), model_evidence, draft,
            len(packages), stop, tuple(failures),
        )
        return ExecutionRecord(result, trace)

    def _failure_record(
        self, execution_id: str, need: InformationNeed, plan: RetrievalPlan | None,
        events: list[ExecutionEvent], queries: list[Any], packages: list[EvidencePackage],
        model_evidence: ModelEvidence | None, draft: ReasoningDraft | None,
        stop: StopReason, failure: str,
    ) -> ExecutionRecord:
        events.append(ExecutionEvent(len(events) + 1, "failure", failure))
        result = IntelligenceResult(
            _identity("intelligence-result", {"execution": execution_id, "failure": failure}),
            execution_id, CompletionStatus.FAILED, "Unable to produce a governed result.", (), (),
            ("execution failed closed",), (failure,), (),
            tuple(item.trace.trace_id for item in packages),
            tuple(item.package_id for item in packages), stop,
        )
        trace = ExecutionTrace(
            execution_id, need, plan, tuple(events), tuple(queries),
            tuple(item.package_id for item in packages), tuple(packages), model_evidence, draft,
            len(packages), stop, (failure,),
        )
        return ExecutionRecord(result, trace)
