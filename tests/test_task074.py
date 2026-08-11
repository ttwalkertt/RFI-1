"""Focused contracts and one-cycle behavior for TASK-074."""

from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

from rfi.investigation_qa import (
    CaseIdentity,
    LifecycleError,
    QADisposition,
    SingleRepairLifecycle,
    parse_qa1,
    parse_qa2,
    parse_repair,
    qa1_output_schema,
    qa2_output_schema,
    repair_output_schema,
)
from rfi.investigation_qa.prompts import qa1_prompt, qa2_prompt, repair_prompt
from rfi.mcp.surface import RfiMcpSurface

ROOT = Path(__file__).resolve().parents[1]


def evidence(uri: str = "rfi://dictionary") -> dict[str, str]:
    return {"uri": uri, "description": "Stable retained repository fact."}


def qa1_payload(case: str = "chronology") -> dict[str, object]:
    return {
        "schema_version": "task074.investigation-qa.v1",
        "case_id": case,
        "disposition": "repair_required",
        "summary": "One bounded defect requires repair.",
        "findings": [
            {
                "finding_id": f"TASK074-{case.upper()}-Q1-F001",
                "case_id": case,
                "severity": "material",
                "defect_class": "incorrect_chronology",
                "affected_claim": "The claimed first retained match.",
                "defect": "The claim conflicts with independently inspected retained evidence.",
                "supporting_evidence": [evidence()],
                "conflicting_or_missing_evidence": [
                    evidence("rfi://transcript-segments/transcript-segment-abc")
                ],
                "why_it_matters": "The question explicitly asks for a boundary.",
                "repair_instruction": "Correct and qualify the retained boundary.",
                "confidence": "high",
                "additional_investigation_required": True,
            }
        ],
    }


def repair_payload(case: str = "chronology") -> dict[str, object]:
    finding_id = f"TASK074-{case.upper()}-Q1-F001"
    return {
        "schema_version": "task074.investigation-qa.v1",
        "case_id": case,
        "repaired_answer": "The corrected answer retains supported claims and states its bound.",
        "finding_actions": [
            {
                "finding_id": finding_id,
                "action": "Corrected the claim after an independent exact evidence read.",
                "evidence_references": [evidence()],
            }
        ],
        "unresolved_items": [],
        "repair_summary": "The only finding was addressed.",
    }


def qa2_payload(case: str = "chronology") -> dict[str, object]:
    finding_id = f"TASK074-{case.upper()}-Q1-F001"
    return {
        "schema_version": "task074.investigation-qa.v1",
        "case_id": case,
        "disposition": "pass",
        "summary": "The bounded repair resolved the finding without regression.",
        "resolutions": [
            {
                "finding_id": finding_id,
                "state": "resolved",
                "explanation": "The corrected claim now matches exact retained evidence.",
                "evidence_references": [evidence()],
                "attribution": None,
            }
        ],
        "new_findings": [],
        "unresolved_item_assessment": [],
    }


class InvestigationQaContractTests(unittest.TestCase):
    def test_strict_schemas_cover_findings_repair_and_resolution(self) -> None:
        qa1 = parse_qa1(qa1_payload(), "chronology")
        finding_ids = tuple(item.finding_id for item in qa1.findings)
        repair = parse_repair(repair_payload(), "chronology", finding_ids)
        qa2 = parse_qa2(qa2_payload(), "chronology", finding_ids)
        self.assertEqual(qa1.disposition, QADisposition.REPAIR_REQUIRED)
        self.assertEqual(repair.finding_actions[0].finding_id, finding_ids[0])
        self.assertEqual(qa2.resolutions[0].state.value, "resolved")
        for schema in (
            qa1_output_schema("chronology"),
            repair_output_schema("chronology", finding_ids),
            qa2_output_schema("chronology", finding_ids),
        ):
            self.assertFalse(schema["additionalProperties"])
            json.dumps(schema)

    def test_finding_ids_and_stable_rfi_references_are_enforced(self) -> None:
        payload = qa1_payload()
        payload["findings"][0]["finding_id"] = "invented"  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "finding_id"):
            parse_qa1(payload, "chronology")
        payload = qa1_payload()
        payload["findings"][0]["supporting_evidence"][0]["uri"] = "notes.txt"  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "uri"):
            parse_qa1(payload, "chronology")

    def test_disposition_and_exact_finding_associations_are_enforced(self) -> None:
        passing = qa1_payload()
        passing["disposition"] = "pass"
        with self.assertRaisesRegex(ValueError, "passing"):
            parse_qa1(passing, "chronology")
        qa1 = parse_qa1(qa1_payload(), "chronology")
        finding_ids = tuple(item.finding_id for item in qa1.findings)
        repair = repair_payload()
        repair["finding_actions"] = []
        with self.assertRaises(ValueError):
            parse_repair(repair, "chronology", finding_ids)
        qa2 = qa2_payload()
        qa2["resolutions"] = []
        with self.assertRaises(ValueError):
            parse_qa2(qa2, "chronology", finding_ids)

    def test_unresolved_repair_must_be_explicit_and_preserved(self) -> None:
        qa1 = parse_qa1(qa1_payload(), "chronology")
        finding_ids = tuple(item.finding_id for item in qa1.findings)
        payload = repair_payload()
        payload["unresolved_items"] = [
            {
                "finding_id": finding_ids[0],
                "limitation": "The repository authority does not establish completeness.",
                "limitation_kind": "repository_authority_limitation",
                "preserved_in_answer": False,
            }
        ]
        with self.assertRaisesRegex(ValueError, "preserved"):
            parse_repair(payload, "chronology", finding_ids)


class SingleRepairLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.answer = "Original fixed first-pass answer."
        identity = CaseIdentity.from_content(
            "chronology", "When was the first and latest retained match?", self.answer
        )
        self.lifecycle = SingleRepairLifecycle(identity, self.answer)
        self.qa1 = parse_qa1(qa1_payload(), "chronology")
        self.finding_ids = tuple(item.finding_id for item in self.qa1.findings)
        self.repair = parse_repair(
            repair_payload(), "chronology", self.finding_ids
        )
        self.qa2 = parse_qa2(qa2_payload(), "chronology", self.finding_ids)

    def test_lifecycle_is_qa1_one_repair_fresh_qa2_then_terminal(self) -> None:
        self.lifecycle.record_qa1(self.qa1)
        self.lifecycle.record_repair(self.repair)
        self.assertEqual(self.lifecycle.qa2_submission, self.repair.repaired_answer)
        self.lifecycle.record_qa2(self.qa2)
        snapshot = self.lifecycle.snapshot()
        self.assertTrue(snapshot["terminal"])
        self.assertEqual(snapshot["repair_cycle_count"], 1)
        self.assertFalse(snapshot["escalation_available"])
        self.assertEqual(snapshot["original_answer"], self.answer)
        self.assertEqual(
            snapshot["repair"]["repaired_answer"], self.repair.repaired_answer
        )

    def test_second_repair_recursive_review_and_post_terminal_actions_fail(self) -> None:
        self.lifecycle.record_qa1(self.qa1)
        self.lifecycle.record_repair(self.repair)
        with self.assertRaises(LifecycleError):
            self.lifecycle.record_repair(self.repair)
        self.lifecycle.record_qa2(self.qa2)
        with self.assertRaises(LifecycleError):
            self.lifecycle.record_qa2(self.qa2)
        with self.assertRaises(LifecycleError):
            self.lifecycle.record_repair(self.repair)

    def test_required_repair_cannot_be_bypassed_and_no_escalation_exists(self) -> None:
        self.lifecycle.record_qa1(self.qa1)
        with self.assertRaises(LifecycleError):
            self.lifecycle.record_qa2(self.qa2)
        self.assertFalse(hasattr(self.lifecycle, "escalate"))
        self.assertFalse(hasattr(self.lifecycle, "request_context"))

    def test_pass_bypasses_repair_agent_but_still_receives_terminal_qa2(self) -> None:
        payload = qa1_payload("sentiment")
        payload["disposition"] = "pass"
        payload["findings"] = []
        qa1 = parse_qa1(payload, "sentiment")
        identity = CaseIdentity.from_content("sentiment", "Question", self.answer)
        lifecycle = SingleRepairLifecycle(identity, self.answer)
        lifecycle.record_qa1(qa1)
        qa2_payload_value = {
            "schema_version": "task074.investigation-qa.v1",
            "case_id": "sentiment",
            "disposition": "pass",
            "summary": "The unchanged submission passes fresh review.",
            "resolutions": [],
            "new_findings": [],
            "unresolved_item_assessment": [],
        }
        qa2 = parse_qa2(qa2_payload_value, "sentiment", ())
        self.assertEqual(lifecycle.qa2_submission, self.answer)
        lifecycle.record_qa2(qa2)
        self.assertEqual(lifecycle.snapshot()["repair_cycle_count"], 0)


class IndependenceBoundaryTests(unittest.TestCase):
    def test_prompts_expose_only_ticket_authorized_durable_context(self) -> None:
        first = qa1_prompt(
            "chronology",
            "When were the first and latest retained matches?",
            "The submitted answer gives two dates.",
        )
        self.assertNotIn("2024-09-04", first)
        self.assertNotIn("2026-07-28", first)
        self.assertNotIn("task073-experiment/mcp", first)
        qa1 = parse_qa1(qa1_payload(), "chronology")
        bounded = repair_prompt(
            "chronology", "Question", "Submitted answer", qa1
        )
        self.assertIn("There is no escalation path", bounded)
        self.assertNotIn("original investigation trace:", bounded)
        repair = parse_repair(repair_payload(), "chronology", (
            "TASK074-CHRONOLOGY-Q1-F001",
        ))
        terminal = qa2_prompt(
            "chronology", "Question", repair.repaired_answer, qa1, repair
        )
        self.assertIn("fresh independent terminal", terminal)
        self.assertIn("This review is terminal", terminal)

    def test_quality_package_does_not_import_task071_harness_or_mcp_implementation(self) -> None:
        imports: set[str] = set()
        for path in (ROOT / "src/rfi/investigation_qa").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports.update(
                node.module or ""
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
            )
        self.assertFalse(any(name.startswith("rfi.research") for name in imports))
        self.assertFalse(any(name.startswith("rfi.mcp") for name in imports))

    def test_frozen_mcp_has_no_qa_repair_or_mutation_convenience_tools(self) -> None:
        names = {item["name"] for item in RfiMcpSurface.tool_specs(None)}  # type: ignore[arg-type]
        self.assertEqual(
            names,
            {"query_artifacts", "search_transcript_segments", "read_artifact_bytes"},
        )
        prohibited = {
            "validate_claim",
            "check_chronology",
            "find_counterevidence",
            "review_answer",
            "repair_answer",
        }
        self.assertTrue(names.isdisjoint(prohibited))

    def test_experiment_runner_cannot_rerun_first_pass_investigations(self) -> None:
        source = (ROOT / "scripts/task074_qa_repair_experiment.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("task073_codex_work_experiment", source)
        self.assertIn('"first_pass_investigations_rerun": False', source)
        self.assertNotIn("rfi.research", source)


if __name__ == "__main__":
    unittest.main()
