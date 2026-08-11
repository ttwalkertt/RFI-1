#!/usr/bin/env python3
"""Validate independent RFI QA benchmark v2, including protected split digests."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
VERSION = "rfi-qa-independent-v2.0.0"
PARTITIONS = ("calibration", "validation", "quarantine")
OBJECTIVE_PARTITIONS = ("calibration", "validation")
CASE_KEYS = {
    "benchmark_version", "case_id", "pair_id", "title", "fixture_id", "difficulty",
    "adjudicability", "investigation_question", "answer_requirements", "submitted_answer", "reference_qa",
}
REFERENCE_KEYS = {"disposition", "material_findings", "defect_classes", "rationale", "adjudication_evidence"}
FINDING_KEYS = {"finding_id", "severity", "defect_class", "affected_claim", "finding", "evidence_locators"}
DIFFICULTIES = {"atomic", "multi_record", "authority_boundary", "judgment_dependent"}
DISPOSITIONS = {"supported", "defective", "indeterminate"}
AUTHORITY_MODES = {"complete", "partial", "dimension_complete"}
ABSENCE_SEMANTICS = {"permitted_within_scope", "not_permitted", "permitted_only_as_stated"}


def fail(message: str) -> None:
    raise ValueError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def set_digest(values: set[str]) -> str:
    return sha256_bytes(("\n".join(sorted(values)) + "\n").encode("utf-8"))


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"{path}: {exc}")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        fail(f"{path}: {exc}")
    if not lines:
        fail(f"{path}: empty JSONL file")
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            fail(f"{path}:{line_number}: blank line")
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            fail(f"{path}:{line_number}: {exc}")
        if not isinstance(item, dict):
            fail(f"{path}:{line_number}: case must be an object")
        cases.append(item)
    return cases


def validate_schema_documents(taxonomy_classes: set[str]) -> None:
    case_schema = read_json(ROOT / "case.schema.json")
    fixture_schema = read_json(ROOT / "fixture.schema.json")
    for name, schema in (("case", case_schema), ("fixture", fixture_schema)):
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            fail(f"{name} schema: wrong draft")
        if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
            fail(f"{name} schema: top-level closed-object contract missing")
    if case_schema["properties"]["benchmark_version"].get("const") != VERSION:
        fail("case schema benchmark version mismatch")
    if fixture_schema["properties"]["benchmark_version"].get("const") != VERSION:
        fail("fixture schema benchmark version mismatch")
    if not re.fullmatch(case_schema["properties"]["case_id"]["pattern"], "R2C-001"):
        fail("case schema does not accept objective IDs")
    if not re.fullmatch(case_schema["properties"]["case_id"]["pattern"], "R2Q-001"):
        fail("case schema does not accept quarantine IDs")
    if not taxonomy_classes:
        fail("taxonomy is empty")


def read_taxonomy() -> tuple[str, set[str]]:
    taxonomy = read_json(ROOT / "taxonomy.json")
    if set(taxonomy) != {"taxonomy_version", "classes"}:
        fail("taxonomy.json: unexpected keys")
    classes: set[str] = set()
    for item in taxonomy["classes"]:
        if set(item) != {"id", "definition"} or not item["definition"].strip():
            fail("taxonomy.json: invalid class entry")
        if item["id"] in classes:
            fail(f"taxonomy.json: duplicate class {item['id']}")
        classes.add(item["id"])
    return taxonomy["taxonomy_version"], classes


def read_fixtures(partition: str) -> dict[str, dict[str, Any]]:
    path = ROOT / partition / "fixtures.json"
    collection = read_json(path)
    if set(collection) != {"benchmark_version", "fixtures"} or collection["benchmark_version"] != VERSION:
        fail(f"{partition}: invalid fixture collection envelope")
    result: dict[str, dict[str, Any]] = {}
    global_locators: set[str] = set()
    for fixture in collection["fixtures"]:
        if set(fixture) != {"fixture_id", "title", "authority", "records"}:
            fail(f"{partition}: invalid fixture keys")
        fixture_id = fixture["fixture_id"]
        expected_fixture_pattern = r"R2F-(?:[0-9]{3}|Q[0-9]{3})"
        if not re.fullmatch(expected_fixture_pattern, fixture_id) or fixture_id in result:
            fail(f"{partition}: invalid or duplicate fixture ID {fixture_id}")
        authority = fixture["authority"]
        if set(authority) != {"locator", "mode", "scope", "absence_semantics"}:
            fail(f"{fixture_id}: invalid authority keys")
        if authority["locator"] != f"rfiqa-v2://{fixture_id}/@authority":
            fail(f"{fixture_id}: invalid authority locator")
        if authority["mode"] not in AUTHORITY_MODES or authority["absence_semantics"] not in ABSENCE_SEMANTICS:
            fail(f"{fixture_id}: invalid authority semantics")
        if not authority["scope"].strip():
            fail(f"{fixture_id}: empty authority scope")
        if authority["locator"] in global_locators:
            fail(f"{fixture_id}: duplicate authority locator")
        global_locators.add(authority["locator"])
        evidence_ids: set[str] = set()
        for record in fixture["records"]:
            if set(record) != {"evidence_id", "locator", "content"}:
                fail(f"{fixture_id}: invalid record keys")
            evidence_id = record["evidence_id"]
            if not re.fullmatch(r"R[1-9][0-9]*", evidence_id) or evidence_id in evidence_ids:
                fail(f"{fixture_id}: invalid or duplicate evidence ID {evidence_id}")
            evidence_ids.add(evidence_id)
            expected_prefix = f"rfiqa-v2://{fixture_id}/{evidence_id}#"
            if not record["locator"].startswith(expected_prefix):
                fail(f"{fixture_id}/{evidence_id}: invalid locator")
            if record["locator"] in global_locators or not record["content"].strip():
                fail(f"{fixture_id}/{evidence_id}: duplicate locator or empty content")
            global_locators.add(record["locator"])
        if not evidence_ids:
            fail(f"{fixture_id}: no evidence records")
        result[fixture_id] = fixture
    return result


def validate_case(
    partition: str,
    case: dict[str, Any],
    fixture: dict[str, Any],
    taxonomy_classes: set[str],
) -> None:
    case_id = case.get("case_id", "<missing>")
    if set(case) != CASE_KEYS or case["benchmark_version"] != VERSION:
        fail(f"{case_id}: invalid case envelope")
    if not re.fullmatch(r"R2(?:C|Q)-[0-9]{3}", case_id):
        fail(f"{case_id}: invalid ID")
    if case["fixture_id"] != fixture["fixture_id"]:
        fail(f"{case_id}: fixture mismatch")
    if case["difficulty"] not in DIFFICULTIES:
        fail(f"{case_id}: invalid difficulty")
    adjudicability = case["adjudicability"]
    if set(adjudicability) != {"status", "human_review_required", "note"}:
        fail(f"{case_id}: invalid adjudicability")
    if partition == "quarantine":
        if not case_id.startswith("R2Q-") or case["pair_id"] is not None:
            fail(f"{case_id}: quarantine ID/pair invariant failed")
        if adjudicability["status"] != "borderline" or adjudicability["human_review_required"] is not True:
            fail(f"{case_id}: quarantine adjudicability invariant failed")
    else:
        if not case_id.startswith("R2C-") or not re.fullmatch(r"R2P-[0-9]{3}", case["pair_id"] or ""):
            fail(f"{case_id}: objective ID/pair invariant failed")
        if adjudicability["status"] != "objective" or adjudicability["human_review_required"] is not False:
            fail(f"{case_id}: objective adjudicability invariant failed")
    if not all(str(case[field]).strip() for field in ("title", "investigation_question", "answer_requirements")):
        fail(f"{case_id}: empty required prose")

    allowed_locators = {fixture["authority"]["locator"]} | {record["locator"] for record in fixture["records"]}
    submitted = case["submitted_answer"]
    if set(submitted) != {"text", "evidence_locators"} or not submitted["text"].strip():
        fail(f"{case_id}: invalid submitted answer")
    if len(submitted["evidence_locators"]) != len(set(submitted["evidence_locators"])):
        fail(f"{case_id}: duplicate submitted locator")
    if not set(submitted["evidence_locators"]).issubset(allowed_locators):
        fail(f"{case_id}: unresolved submitted locator")

    reference = case["reference_qa"]
    if set(reference) != REFERENCE_KEYS or reference["disposition"] not in DISPOSITIONS:
        fail(f"{case_id}: invalid reference QA envelope")
    findings = reference["material_findings"]
    classes = reference["defect_classes"]
    if reference["disposition"] == "supported" and (findings or classes):
        fail(f"{case_id}: supported case has findings")
    if reference["disposition"] != "supported" and not findings:
        fail(f"{case_id}: non-supported case lacks finding")
    if len(classes) != len(set(classes)) or not set(classes).issubset(taxonomy_classes):
        fail(f"{case_id}: invalid taxonomy usage")
    derived_classes: list[str] = []
    for index, item in enumerate(findings, start=1):
        if set(item) != FINDING_KEYS:
            fail(f"{case_id}: invalid finding keys")
        if item["finding_id"] != f"{case_id}-F{index}" or item["severity"] != "material":
            fail(f"{case_id}: unstable finding identity or severity")
        if item["defect_class"] not in taxonomy_classes:
            fail(f"{case_id}: unknown defect class")
        if not item["evidence_locators"] or not set(item["evidence_locators"]).issubset(allowed_locators):
            fail(f"{case_id}: unresolved finding evidence")
        derived_classes.append(item["defect_class"])
    if list(dict.fromkeys(derived_classes)) != classes:
        fail(f"{case_id}: defect class summary differs from findings")
    if not reference["rationale"].strip() or not reference["adjudication_evidence"]:
        fail(f"{case_id}: incomplete reference rationale")
    for item in reference["adjudication_evidence"]:
        if set(item) != {"locator", "role", "fact"} or item["locator"] not in allowed_locators:
            fail(f"{case_id}: invalid adjudication evidence")
        if not item["role"].strip() or not item["fact"].strip():
            fail(f"{case_id}: empty adjudication evidence")


def load_partition(partition: str, taxonomy_classes: set[str]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    cases = read_jsonl(ROOT / partition / "cases.jsonl")
    fixtures = read_fixtures(partition)
    case_ids: set[str] = set()
    used_fixtures: set[str] = set()
    pair_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        case_id = case["case_id"]
        if case_id in case_ids:
            fail(f"{partition}: duplicate case ID {case_id}")
        case_ids.add(case_id)
        fixture_id = case["fixture_id"]
        if fixture_id not in fixtures:
            fail(f"{case_id}: fixture not found in same partition")
        used_fixtures.add(fixture_id)
        validate_case(partition, case, fixtures[fixture_id], taxonomy_classes)
        if case["pair_id"] is not None:
            pair_groups[case["pair_id"]].append(case)
    if used_fixtures != set(fixtures):
        fail(f"{partition}: unused or missing fixture closure")
    if partition in OBJECTIVE_PARTITIONS:
        fixture_to_pair: dict[str, str] = {}
        for pair_id, members in pair_groups.items():
            if len(members) != 2:
                fail(f"{partition}/{pair_id}: expected two members")
            left, right = members
            for field in ("fixture_id", "investigation_question", "answer_requirements"):
                if left[field] != right[field]:
                    fail(f"{partition}/{pair_id}: asymmetry in {field}")
            dispositions = {member["reference_qa"]["disposition"] for member in members}
            if "supported" not in dispositions or len(dispositions) != 2:
                fail(f"{partition}/{pair_id}: expected one supported and one non-supported member")
            if left["submitted_answer"] == right["submitted_answer"]:
                fail(f"{partition}/{pair_id}: submitted answer payloads must differ")
            fixture_id = left["fixture_id"]
            if fixture_id in fixture_to_pair:
                fail(f"{partition}: fixture reused across pairs")
            fixture_to_pair[fixture_id] = pair_id
    elif pair_groups:
        fail("quarantine must not contain matched pairs")
    return cases, fixtures


def aggregate(cases: list[dict[str, Any]], fixtures: dict[str, dict[str, Any]]) -> dict[str, Any]:
    pair_ids = {case["pair_id"] for case in cases if case["pair_id"] is not None}
    return {
        "pair_count": len(pair_ids),
        "case_count": len(cases),
        "fixture_count": len(fixtures),
        "disposition_counts": dict(sorted(Counter(case["reference_qa"]["disposition"] for case in cases).items())),
        "defect_class_case_counts": dict(sorted(Counter(item for case in cases for item in case["reference_qa"]["defect_classes"]).items())),
        "difficulty_counts": dict(sorted(Counter(case["difficulty"] for case in cases).items())),
        "authority_mode_counts": dict(sorted(Counter(item["authority"]["mode"] for item in fixtures.values()).items())),
        "pair_set_sha256": set_digest(pair_ids),
    }


def validate_file_digests(manifest: dict[str, Any], full: bool) -> None:
    digest_section = manifest["digests"]
    expected_files: dict[str, str] = digest_section["corpus_files"]
    for relative, expected in expected_files.items():
        path = ROOT / relative
        if path.exists():
            actual = sha256_file(path)
            if actual != expected:
                fail(f"digest mismatch for {relative}: {actual} != {expected}")
        elif full or not relative.startswith("validation/"):
            fail(f"required digest file missing: {relative}")
    recomputed_corpus = sha256_bytes(
        "".join(f"{path}:{expected_files[path]}\n" for path in sorted(expected_files)).encode("utf-8")
    )
    if recomputed_corpus != digest_section["corpus_sha256"]:
        fail("manifest corpus digest is internally inconsistent")
    for partition in PARTITIONS:
        cases_path = ROOT / partition / "cases.jsonl"
        fixtures_path = ROOT / partition / "fixtures.json"
        recorded_cases_sha = expected_files[f"{partition}/cases.jsonl"]
        recorded_fixtures_sha = expected_files[f"{partition}/fixtures.json"]
        recorded_combined = sha256_bytes(
            f"cases.jsonl:{recorded_cases_sha}\nfixtures.json:{recorded_fixtures_sha}\n".encode("utf-8")
        )
        if digest_section["partitions"][partition] != {
            "cases_sha256": recorded_cases_sha,
            "fixtures_sha256": recorded_fixtures_sha,
            "partition_sha256": recorded_combined,
        }:
            fail(f"{partition}: manifest partition digest is internally inconsistent")
        if not cases_path.exists() and partition == "validation" and not full:
            continue
        cases_sha = sha256_file(cases_path)
        fixtures_sha = sha256_file(fixtures_path)
        combined = sha256_bytes(f"cases.jsonl:{cases_sha}\nfixtures.json:{fixtures_sha}\n".encode("utf-8"))
        expected = digest_section["partitions"][partition]
        if {"cases_sha256": cases_sha, "fixtures_sha256": fixtures_sha, "partition_sha256": combined} != expected:
            fail(f"{partition}: partition digest mismatch")


def validate_manifest_privacy(manifest: dict[str, Any]) -> None:
    serialized = json.dumps(manifest, sort_keys=True)
    prohibited_fragments = ("R2C-", "R2Q-", "rfiqa-v2://", "investigation_question", "material_findings", "submitted_answer")
    for fragment in prohibited_fragments:
        if fragment in serialized:
            fail(f"split manifest leaks case-level content: {fragment}")
    confidentiality = manifest["held_out_confidentiality"]
    if not all(value is False for key, value in confidentiality.items() if key.endswith("_listed")):
        fail("manifest confidentiality declarations are inconsistent")
    if confidentiality["manifest_validation_metadata_is_aggregate_only"] is not True:
        fail("manifest aggregate-only declaration missing")


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--full", action="store_true", help="require and validate held-out files")
    group.add_argument("--visible", action="store_true", help="validate calibration-visible repository with held-out files absent")
    args = parser.parse_args()
    validation_paths = (ROOT / "validation" / "cases.jsonl", ROOT / "validation" / "fixtures.json")
    validation_present = all(path.exists() for path in validation_paths)
    validation_any = any(path.exists() for path in validation_paths)
    full = args.full or (not args.visible and validation_present)
    if args.full and not validation_present:
        fail("--full requested but validation partition is absent")
    if args.visible and validation_any:
        fail("--visible requires held-out validation files to be physically absent")

    taxonomy_version, taxonomy_classes = read_taxonomy()
    validate_schema_documents(taxonomy_classes)
    metadata = read_json(ROOT / "authoring-metadata.json")
    manifest = read_json(ROOT / "split-manifest.json")
    if manifest["benchmark_version"] != VERSION or metadata["benchmark_version"] != VERSION:
        fail("benchmark version mismatch")
    if manifest["taxonomy_version"] != taxonomy_version or metadata["taxonomy_version"] != taxonomy_version:
        fail("taxonomy version mismatch")
    validate_manifest_privacy(manifest)
    if any(metadata["independence_boundary"].values()):
        fail("authoring metadata independence boundary is not clean")
    if not manifest["integrity_checks"] or not all(manifest["integrity_checks"].values()):
        fail("manifest integrity declarations are incomplete")

    loaded: dict[str, tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]] = {}
    for partition in (PARTITIONS if full else ("calibration", "quarantine")):
        loaded[partition] = load_partition(partition, taxonomy_classes)
        summary = aggregate(*loaded[partition])
        if summary != manifest["partitions"][partition]:
            fail(f"{partition}: manifest aggregate mismatch")

    split = manifest["split"]
    population = [f"R2P-{number:03d}" for number in range(split["objective_pair_id_population"]["first"], split["objective_pair_id_population"]["last"] + 1)]
    randomized = population.copy()
    random.Random(split["random_seed"]).shuffle(randomized)
    expected_calibration = set(randomized[: split["calibration_pair_target"]])
    expected_validation = set(randomized[split["calibration_pair_target"] :])
    actual_calibration = {case["pair_id"] for case in loaded["calibration"][0]}
    if actual_calibration != expected_calibration:
        fail("calibration pair assignment does not reproduce from seed")
    if set_digest(expected_calibration) != manifest["partitions"]["calibration"]["pair_set_sha256"]:
        fail("calibration pair-set digest mismatch")
    if set_digest(expected_validation) != manifest["partitions"]["validation"]["pair_set_sha256"]:
        fail("validation pair-set digest mismatch")

    if full:
        actual_validation = {case["pair_id"] for case in loaded["validation"][0]}
        if actual_validation != expected_validation:
            fail("validation pair assignment does not reproduce from seed")
        case_sets = [{case["case_id"] for case in loaded[item][0]} for item in PARTITIONS]
        fixture_sets = [set(loaded[item][1]) for item in PARTITIONS]
        pair_sets = [{case["pair_id"] for case in loaded[item][0] if case["pair_id"]} for item in PARTITIONS]
        for sets, label in ((case_sets, "case"), (fixture_sets, "fixture"), (pair_sets, "pair")):
            if any(sets[left] & sets[right] for left in range(3) for right in range(left + 1, 3)):
                fail(f"cross-partition {label} overlap")
        objective_cases = loaded["calibration"][0] + loaded["validation"][0]
        objective_summary = {
            "pair_count": len({case["pair_id"] for case in objective_cases}),
            "case_count": len(objective_cases),
            "disposition_counts": dict(sorted(Counter(case["reference_qa"]["disposition"] for case in objective_cases).items())),
        }
        if objective_summary != manifest["objective_totals"]:
            fail("objective total mismatch")
    else:
        calibration = manifest["partitions"]["calibration"]
        validation = manifest["partitions"]["validation"]
        combined_dispositions = Counter(calibration["disposition_counts"]) + Counter(validation["disposition_counts"])
        if {
            "pair_count": calibration["pair_count"] + validation["pair_count"],
            "case_count": calibration["case_count"] + validation["case_count"],
            "disposition_counts": dict(sorted(combined_dispositions.items())),
        } != manifest["objective_totals"]:
            fail("visible manifest objective arithmetic mismatch")

    validate_file_digests(manifest, full)
    mode = "full local corpus" if full else "calibration-visible corpus with held-out files absent"
    print(f"validated {VERSION}: {mode}")
    print("calibration:", manifest["partitions"]["calibration"])
    print("validation aggregate:", manifest["partitions"]["validation"])
    print("quarantine:", manifest["partitions"]["quarantine"])
    print("corpus_sha256:", manifest["digests"]["corpus_sha256"])


if __name__ == "__main__":
    main()
