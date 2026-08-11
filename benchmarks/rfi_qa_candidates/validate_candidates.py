#!/usr/bin/env python3
"""Validate the standalone RFI QA candidate pool without third-party packages."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CASE_PATH = ROOT / "candidate_cases.jsonl"
FIXTURE_PATH = ROOT / "fixtures.json"
CASE_SCHEMA_PATH = ROOT / "case.schema.json"

CASE_KEYS = {
    "schema_version",
    "case_id",
    "pair_id",
    "title",
    "fixture_id",
    "difficulty",
    "adjudicability",
    "investigation_question",
    "answer_requirements",
    "submitted_answer",
    "reference_qa",
}
REFERENCE_KEYS = {
    "disposition",
    "material_findings",
    "defect_classes",
    "rationale",
    "adjudication_evidence",
}
FINDING_KEYS = {
    "finding_id",
    "defect_class",
    "affected_claim",
    "finding",
    "evidence_locators",
}
DIFFICULTIES = {"atomic", "cross_evidence", "evidence_limits", "judgment_dependent"}
DISPOSITIONS = {"supported", "defective", "indeterminate"}
AUTHORITY_MODES = {"complete", "partial", "dimension_complete"}


def fail(message: str) -> None:
    raise ValueError(message)


def read_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with CASE_PATH.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                fail(f"{CASE_PATH.name}:{line_number}: blank JSONL line")
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                fail(f"{CASE_PATH.name}:{line_number}: {exc}")
            if not isinstance(value, dict):
                fail(f"{CASE_PATH.name}:{line_number}: case must be an object")
            cases.append(value)
    return cases


def read_fixture_index() -> dict[str, dict[str, Any]]:
    fixture_collection = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if set(fixture_collection) != {"schema_version", "fixtures"}:
        fail("fixtures.json: unexpected top-level keys")
    if fixture_collection["schema_version"] != "1.0":
        fail("fixtures.json: unsupported schema_version")

    fixtures: dict[str, dict[str, Any]] = {}
    global_locators: set[str] = set()
    for fixture in fixture_collection["fixtures"]:
        if set(fixture) != {"fixture_id", "title", "authority", "records"}:
            fail("fixtures.json: unexpected or missing fixture keys")
        fixture_id = fixture["fixture_id"]
        if fixture_id in fixtures:
            fail(f"duplicate fixture_id {fixture_id}")
        if set(fixture["authority"]) != {"mode", "scope", "absence_claims"}:
            fail(f"{fixture_id}: unexpected or missing authority keys")
        if fixture["authority"]["mode"] not in AUTHORITY_MODES:
            fail(f"{fixture_id}: unknown authority mode")
        if not fixture["authority"]["scope"].strip():
            fail(f"{fixture_id}: empty authority scope")
        if not fixture["authority"]["absence_claims"].strip():
            fail(f"{fixture_id}: empty absence policy")
        evidence_ids: set[str] = set()
        for record in fixture["records"]:
            if set(record) != {"evidence_id", "locator", "content"}:
                fail(f"{fixture_id}: unexpected or missing record keys")
            evidence_id = record["evidence_id"]
            locator = record["locator"]
            if evidence_id in evidence_ids:
                fail(f"{fixture_id}: duplicate evidence_id {evidence_id}")
            evidence_ids.add(evidence_id)
            if locator in global_locators:
                fail(f"duplicate evidence locator {locator}")
            global_locators.add(locator)
            expected_prefix = f"fixture://{fixture_id}/{evidence_id}#"
            if not locator.startswith(expected_prefix):
                fail(f"{fixture_id}/{evidence_id}: locator must start {expected_prefix}")
            if not record["content"].strip():
                fail(f"{fixture_id}/{evidence_id}: empty evidence content")
        if not evidence_ids:
            fail(f"{fixture_id}: fixture has no records")
        fixtures[fixture_id] = fixture
    return fixtures


def validate_case(
    case: dict[str, Any],
    fixtures: dict[str, dict[str, Any]],
    allowed_defect_classes: set[str],
) -> None:
    case_id = case.get("case_id", "<missing-case-id>")
    if set(case) != CASE_KEYS:
        fail(f"{case_id}: unexpected or missing case keys: {sorted(set(case) ^ CASE_KEYS)}")
    if case["schema_version"] != "1.0":
        fail(f"{case_id}: unsupported schema_version")
    if not re.fullmatch(r"RFIQA-[0-9]{3}", case_id):
        fail(f"{case_id}: invalid case_id")
    pair_id = case["pair_id"]
    if pair_id is not None and not re.fullmatch(r"PAIR-[0-9]{3}", pair_id):
        fail(f"{case_id}: invalid pair_id")
    if case["difficulty"] not in DIFFICULTIES:
        fail(f"{case_id}: invalid difficulty")
    if case["fixture_id"] not in fixtures:
        fail(f"{case_id}: unknown fixture_id {case['fixture_id']}")

    adjudicability = case["adjudicability"]
    if set(adjudicability) != {"status", "human_review_required", "note"}:
        fail(f"{case_id}: invalid adjudicability keys")
    if adjudicability["status"] not in {"objective", "borderline"}:
        fail(f"{case_id}: invalid adjudicability status")
    expected_review_flag = adjudicability["status"] == "borderline"
    if adjudicability["human_review_required"] is not expected_review_flag:
        fail(f"{case_id}: human_review_required disagrees with status")
    if expected_review_flag and pair_id is not None:
        fail(f"{case_id}: borderline candidates must not be paired")
    if not expected_review_flag and pair_id is None:
        fail(f"{case_id}: objective candidates must have a control pair")

    fixture = fixtures[case["fixture_id"]]
    locators = {record["locator"] for record in fixture["records"]}
    submitted = case["submitted_answer"]
    if set(submitted) != {"text", "evidence_locators"}:
        fail(f"{case_id}: invalid submitted_answer keys")
    if not submitted["text"].strip():
        fail(f"{case_id}: empty submitted answer")
    if len(submitted["evidence_locators"]) != len(set(submitted["evidence_locators"])):
        fail(f"{case_id}: duplicate submitted evidence locator")
    for locator in submitted["evidence_locators"]:
        if locator not in locators:
            fail(f"{case_id}: submitted locator does not resolve in fixture: {locator}")

    reference = case["reference_qa"]
    if set(reference) != REFERENCE_KEYS:
        fail(f"{case_id}: invalid reference_qa keys")
    disposition = reference["disposition"]
    if disposition not in DISPOSITIONS:
        fail(f"{case_id}: invalid disposition")
    findings = reference["material_findings"]
    classes = reference["defect_classes"]
    if disposition == "supported" and (findings or classes):
        fail(f"{case_id}: supported case must not contain material findings or defect classes")
    if disposition != "supported" and not findings:
        fail(f"{case_id}: non-supported case must contain at least one material finding")
    if len(classes) != len(set(classes)):
        fail(f"{case_id}: duplicate reference defect class")

    finding_classes: list[str] = []
    seen_finding_ids: set[str] = set()
    for index, finding in enumerate(findings, start=1):
        if set(finding) != FINDING_KEYS:
            fail(f"{case_id}: invalid finding keys")
        expected_finding_id = f"{case_id}-F{index}"
        if finding["finding_id"] != expected_finding_id:
            fail(f"{case_id}: expected finding_id {expected_finding_id}")
        if finding["finding_id"] in seen_finding_ids:
            fail(f"{case_id}: duplicate finding_id")
        seen_finding_ids.add(finding["finding_id"])
        defect_class = finding["defect_class"]
        if defect_class not in allowed_defect_classes:
            fail(f"{case_id}: unknown defect class {defect_class}")
        finding_classes.append(defect_class)
        if not finding["evidence_locators"]:
            fail(f"{case_id}: finding lacks adjudication locator")
        for locator in finding["evidence_locators"]:
            if locator not in locators:
                fail(f"{case_id}: finding locator does not resolve in fixture: {locator}")
    if list(dict.fromkeys(finding_classes)) != classes:
        fail(f"{case_id}: defect_classes must equal ordered unique finding classes")

    if not reference["adjudication_evidence"]:
        fail(f"{case_id}: missing adjudication_evidence")
    for item in reference["adjudication_evidence"]:
        if set(item) != {"locator", "role", "fact"}:
            fail(f"{case_id}: invalid adjudication item keys")
        if item["locator"] not in locators:
            fail(f"{case_id}: adjudication locator does not resolve: {item['locator']}")


def main() -> None:
    fixtures = read_fixture_index()
    cases = read_cases()
    case_schema = json.loads(CASE_SCHEMA_PATH.read_text(encoding="utf-8"))
    allowed_defect_classes = set(case_schema["$defs"]["defect_class"]["enum"])

    case_ids: set[str] = set()
    pairs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        validate_case(case, fixtures, allowed_defect_classes)
        if case["case_id"] in case_ids:
            fail(f"duplicate case_id {case['case_id']}")
        case_ids.add(case["case_id"])
        if case["pair_id"] is not None:
            pairs[case["pair_id"]].append(case)

    for pair_id, pair_cases in sorted(pairs.items()):
        if len(pair_cases) != 2:
            fail(f"{pair_id}: expected exactly two cases")
        left, right = pair_cases
        for field in ("fixture_id", "investigation_question", "answer_requirements"):
            if left[field] != right[field]:
                fail(f"{pair_id}: paired cases differ in {field}")
        dispositions = {case["reference_qa"]["disposition"] for case in pair_cases}
        if "supported" not in dispositions or len(dispositions) != 2:
            fail(f"{pair_id}: expected one supported and one non-supported disposition")

    used_fixtures = {case["fixture_id"] for case in cases}
    unused_fixtures = set(fixtures) - used_fixtures
    if unused_fixtures:
        fail(f"unused fixtures: {sorted(unused_fixtures)}")

    disposition_counts = Counter(case["reference_qa"]["disposition"] for case in cases)
    status_counts = Counter(case["adjudicability"]["status"] for case in cases)
    difficulty_counts = Counter(case["difficulty"] for case in cases)
    print(f"validated {len(cases)} candidate cases, {len(fixtures)} fixtures, {len(pairs)} pairs")
    print("dispositions:", dict(sorted(disposition_counts.items())))
    print("adjudicability:", dict(sorted(status_counts.items())))
    print("difficulty:", dict(sorted(difficulty_counts.items())))


if __name__ == "__main__":
    main()
