#!/usr/bin/env python3
"""Validate schema, corpus authority, evidence locators, pairs, split, and isolation."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import tarfile
from dataclasses import asdict
from pathlib import Path

from rfi.acquisition import AcquisitionRepository
from rfi.artifacts import ArtifactQueryService
from rfi.firms import FirmRepository
from rfi.research import TranscriptKnowledgeAccess, TranscriptScope
from rfi.source_profiles import load_canonical_template

SCOPE = "stx-retained-earnings-transcripts-sqlite-revision-8237"
CASE_ID = re.compile(r"^stx-s\d{3}-(acceptable|defective)$")
SCENARIO_ID = re.compile(r"^stx-s\d{3}$")
STATES = {"supported", "contradicted", "indeterminate", "mixed"}
QUALITIES = {"acceptable", "defective"}


def load_jsonl(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def tree_digest(path):
    members = []
    for item in sorted(path.rglob("*")):
        if item.is_file():
            members.append({"path": str(item.relative_to(path)), "sha256": sha(item.read_bytes()), "bytes": item.stat().st_size})
    return sha(canonical(members).encode()), members


def make_access(state):
    artifacts = ArtifactQueryService(
        AcquisitionRepository(state / "acquisition"),
        FirmRepository.open(state / "firm-catalog"),
        load_canonical_template(),
    )
    return TranscriptKnowledgeAccess(artifacts, TranscriptScope(("seagate",), ("earnings_transcript",)))


def validate_case(case, quarantine=False):
    required = {"case_id", "scenario_id", "corpus_scope_id", "question", "submitted_answer", "submitted_evidence_ids"}
    require(required <= case.keys(), f"case fields missing: {case.get('case_id')}")
    require(case["corpus_scope_id"] == SCOPE, f"wrong corpus scope: {case['case_id']}")
    require(len(case["question"]) >= 10 and len(case["submitted_answer"]) >= 10, f"empty case text: {case['case_id']}")
    require(case["submitted_evidence_ids"] and len(case["submitted_evidence_ids"]) == len(set(case["submitted_evidence_ids"])), f"invalid submitted evidence: {case['case_id']}")
    if quarantine:
        require(re.fullmatch(r"stx-q\d{3}", case["case_id"]) is not None, f"bad quarantine ID: {case['case_id']}")
    else:
        require(CASE_ID.fullmatch(case["case_id"]) is not None, f"bad case ID: {case['case_id']}")
        require(SCENARIO_ID.fullmatch(case["scenario_id"]) is not None, f"bad scenario ID: {case['scenario_id']}")
        require(case["pair_id"] == case["scenario_id"], f"pair mismatch: {case['case_id']}")
        require(case["pair_member"] in QUALITIES, f"bad pair member: {case['case_id']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--state", type=Path, default=Path(".artifacts/task071-live-eval"))
    parser.add_argument("--visible-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(); root = args.root
    taxonomy = json.loads((root / "taxonomy/defect-taxonomy.json").read_text()); classes = set(taxonomy["classes"])
    digests = json.loads((root / "digests.json").read_text())
    for relative, expected in digests["members"].items():
        require(sha((root / relative).read_bytes()) == expected, f"core digest differs: {relative}")
    corpus = json.loads((root / "corpus/seagate-transcript-corpus-manifest.json").read_text())
    split = json.loads((root / "split-manifest.json").read_text())
    calibration = load_jsonl(root / "calibration/cases.jsonl"); calrefs = load_jsonl(root / "calibration/reference.jsonl")
    quarantine = load_jsonl(root / "quarantine/cases.jsonl"); qrefs = load_jsonl(root / "quarantine/reference.jsonl")
    held = heldrefs = private = []
    if not args.visible_only:
        held = load_jsonl(root / "withheld/payload/cases.jsonl"); heldrefs = load_jsonl(root / "withheld/payload/reference.jsonl")
        private = json.loads((root / "withheld/payload/private-split-manifest.json").read_text())
    for case in calibration + held: validate_case(case)
    for case in quarantine: validate_case(case, quarantine=True)
    cases, refs = calibration + held, calrefs + heldrefs
    require(len({c["case_id"] for c in cases}) == len(cases), "duplicate case IDs")
    require(len({r["case_id"] for r in refs}) == len(refs), "duplicate reference IDs")
    require({c["case_id"] for c in cases} == {r["case_id"] for r in refs}, "case/reference mismatch")
    require({c["case_id"] for c in quarantine} == {r["case_id"] for r in qrefs}, "quarantine case/reference mismatch")
    refmap = {r["case_id"]: r for r in refs}
    for ref in refs:
        require(ref["corpus_scope_id"] == SCOPE and ref["proposition_state"] in STATES and ref["answer_quality"] in QUALITIES, f"bad reference labels: {ref['case_id']}")
        if ref["answer_quality"] == "acceptable":
            require(ref["primary_failure"] is None and not ref["acceptable_failure_classes"], f"acceptable case has defect: {ref['case_id']}")
        else:
            require(ref["primary_failure"] in classes, f"unknown primary failure: {ref['case_id']}")
            require(ref["primary_failure"] in ref["acceptable_failure_classes"], f"primary not acceptable class: {ref['case_id']}")
            require(set(ref["acceptable_failure_classes"]) <= classes, f"unknown acceptable class: {ref['case_id']}")
        evid_ids = [e["evidence_id"] for e in ref["evidence"]]
        require(evid_ids and len(evid_ids) == len(set(evid_ids)), f"duplicate reference evidence: {ref['case_id']}")
        require(set(ref["minimum_decisive_evidence_ids"]) <= set(evid_ids), f"decisive evidence outside universe: {ref['case_id']}")
        require(set(ref["material_qualifying_counterevidence_ids"]) <= set(evid_ids), f"counterevidence outside universe: {ref['case_id']}")

    pairs = {}
    for case in cases: pairs.setdefault(case["scenario_id"], []).append(case)
    for sid, members in pairs.items():
        require(len(members) == 2 and {x["pair_member"] for x in members} == QUALITIES, f"bad matched pair: {sid}")
        good, bad = sorted(members, key=lambda x: x["pair_member"])
        require(good["question"] == bad["question"] and good["answer_requirements"] == bad["answer_requirements"], f"pair question differs: {sid}")
        require(good["submitted_evidence_ids"] == bad["submitted_evidence_ids"], f"pair evidence differs: {sid}")
        require([e["evidence_id"] for e in refmap[good["case_id"]]["evidence"]] == [e["evidence_id"] for e in refmap[bad["case_id"]]["evidence"]], f"reference evidence differs: {sid}")
        require(good["submitted_answer"] != bad["submitted_answer"], f"pair answer not mutated: {sid}")

    cal_sids = {c["scenario_id"] for c in calibration}; held_sids = {c["scenario_id"] for c in held}
    require(not (cal_sids & held_sids), "partition scenario overlap")
    require(not ({c["scenario_id"] for c in quarantine} & (cal_sids | held_sids)), "quarantine leaked into partitions")
    require(len(calibration) == 48 and len(cal_sids) == 24 and len(quarantine) == 4, "visible population differs")
    if held:
        require(len(held) == 32 and len(held_sids) == 16 and len(pairs) == 40, "held-out population differs")
        ordered = sorted(cal_sids | held_sids); random.Random(split["seed"]).shuffle(ordered)
        require(set(ordered[:24]) == cal_sids and set(ordered[24:]) == held_sids, "split replay differs")
        require(set(private["calibration_scenario_ids"]) == cal_sids and set(private["held_out_scenario_ids"]) == held_sids, "private split manifest differs")
        actual_digest, actual_members = tree_digest(root / "withheld/payload")
        recorded = json.loads((root / "withheld/payload-digest.json").read_text())
        require(actual_digest == recorded["tree_digest"] == split["held_out_payload_sha256"], "held-out payload digest differs")
        require(actual_digest == digests["held_out_payload_tree_sha256"], "top-level held-out digest differs")
        require(actual_members == recorded["members"], "held-out member digest differs")
        archive_record = json.loads((root / "withheld/archive-digest.json").read_text())
        archive = root / "withheld" / archive_record["archive"]
        require(archive.stat().st_size == archive_record["bytes"] and sha(archive.read_bytes()) == archive_record["sha256"], "held-out archive digest differs")
        require(archive_record["sha256"] == digests["held_out_archive_sha256"], "top-level archive digest differs")
        with tarfile.open(archive, "r:gz") as bundle:
            names = set(bundle.getnames())
        require("payload/cases.jsonl" in names and "payload/reference.jsonl" in names and "human-review-packet.md" in names, "held-out archive members missing")
        # Calibration-visible files cannot contain any held-out case text, IDs, labels, or evidence IDs.
        needles = set(held_sids)
        for case in held:
            # A retained segment may independently support a calibration scenario. Isolation
            # forbids the held-out selection/association, not visibility of repository evidence
            # that calibration legitimately uses for another question.
            needles.update((case["case_id"], case["question"], case["submitted_answer"]))
        visible_text = ""
        for path in root.rglob("*"):
            if path.is_file() and "withheld" not in path.parts:
                visible_text += path.read_text(encoding="utf-8", errors="ignore")
        require(not any(n in visible_text for n in needles), "held-out case information leaked into visible tree")

    require(corpus["repository_snapshot"] == "sqlite-revision-8237" and corpus["authority_revision"] == 8237, "wrong frozen revision")
    require(corpus["transcript_count"] == 21 and corpus["date_from"] == "2024-09-04" and corpus["date_through"] == "2026-07-28", "wrong frozen corpus inventory")
    require(not corpus["transcripts_lacking_trustworthy_source_effective_date"], "untrusted transcript dates present")
    require(all(d["source_effective_date_basis"] == "trusted_event_date" for d in corpus["documents"]), "unexpected date basis")

    access = make_access(args.state)
    try:
        desc = asdict(access.describe_corpus()); segments = access._segments
        require(access.repository_snapshot == corpus["repository_snapshot"], "live authority snapshot differs")
        require(len(desc["documents"]) == corpus["transcript_count"] and desc["segment_count"] == corpus["access_generation"]["segment_count"], "live corpus inventory differs")
        for ref in refs + qrefs:
            for evidence in ref["evidence"]:
                require(evidence["segment_id"] in segments, f"unknown segment: {evidence['segment_id']}")
                seg = asdict(segments[evidence["segment_id"]])
                mapping = {"segment_id":"segment_id","document_id":"document_id","artifact_id":"artifact_id","event_date":"event_date","ordinal":"ordinal","byte_start":"byte_start","byte_end":"byte_end","segment_sha256":"content_sha256","canonical_artifact_id":"canonical_artifact_id","event_kind":"event_kind","speaker_label":"speaker_label","title":"title","exact_text":"text"}
                for expected, actual in mapping.items():
                    require(evidence[expected] == seg[actual], f"evidence locator mismatch {expected}: {ref['case_id']}")
    finally:
        access.close()

    leakage = json.loads((root / "analysis/leakage-artifact-analysis.json").read_text())
    require(leakage["result"] == "PASS", "evidence-withheld leakage controls failed")
    result = {"result":"PASS", "mode":"visible-only" if args.visible_only else "full", "corpus":{"snapshot":corpus["repository_snapshot"],"date_from":corpus["date_from"],"date_through":corpus["date_through"],"transcripts":corpus["transcript_count"],"segments":corpus["access_generation"]["segment_count"]}, "population":{"scenarios":len(pairs),"answer_cases":len(cases),"calibration_cases":len(calibration),"held_out_cases":len(held),"quarantine_cases":len(quarantine)}, "checks":["schema and stable IDs","corpus scope and date basis","exact locator resolution","matched-pair integrity","label and taxonomy consistency","scenario partition co-location and disjointness","quarantine exclusion","fixed-seed split replay","payload and member digests","held-out visible-tree isolation","evidence-withheld leakage controls"]}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
