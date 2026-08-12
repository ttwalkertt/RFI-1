"""TASK-075 gauge contracts, benchmark protection, scoring, and freeze controls."""

from __future__ import annotations

import importlib.util
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from rfi.qa_gauge import (
    BenchmarkCorpus,
    GaugeFinding,
    GaugeReview,
    consensus_review,
    gauge_output_schema,
    parse_gauge_review,
    prepare_control_manifests,
    prepare_v2_control_manifests,
    prepare_v3_control_manifests,
    score_partition,
)
from rfi.qa_gauge.prompts import (
    DESIGN_GAUGE_V2,
    DESIGN_GAUGE_V3,
    prompt_for_design,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = ROOT / "benchmarks/rfi_qa_candidates"
V2_CORPUS_ROOT = ROOT / "benchmarks/rfi_qa_candidates_v2"
V3_CORPUS_ROOT = ROOT / "benchmarks/rfi_qa_candidates_v3"
CONTROL = ROOT / "experiments/task075"


def review(
    evaluation_id: str,
    disposition: str,
    defect_class: str | None = None,
    locator: str = "fixture://FX-001/E1#value",
) -> GaugeReview:
    findings = (
        GaugeFinding("F001", defect_class, "claim", "material defect", (locator,)),
    ) if defect_class else ()
    return GaugeReview("task075.qa-gauge.v1", evaluation_id, disposition, findings, "rationale")


class GaugeContractTests(unittest.TestCase):
    def test_strict_schema_and_semantics_reject_invented_locator_and_findings_on_supported(
        self,
    ) -> None:
        schema = gauge_output_schema("eval", ("fixture://FX-001/E1#value",))
        self.assertFalse(schema["additionalProperties"])
        payload = {
            "schema_version": "task075.qa-gauge.v1",
            "evaluation_id": "eval",
            "disposition": "supported",
            "findings": [],
            "rationale": "All material claims are supported.",
        }
        parsed = parse_gauge_review(
            payload,
            evaluation_id="eval",
            allowed_locators=("fixture://FX-001/E1#value",),
        )
        self.assertEqual(parsed.disposition, "supported")
        payload["findings"] = [{
            "finding_id": "F001",
            "defect_class": "numeric_mismatch",
            "affected_claim": "claim",
            "finding": "wrong",
            "evidence_locators": ["fixture://FX-001/E1#value"],
        }]
        with self.assertRaisesRegex(ValueError, "supported"):
            parse_gauge_review(
                payload,
                evaluation_id="eval",
                allowed_locators=("fixture://FX-001/E1#value",),
            )
        payload["disposition"] = "defective"
        payload["findings"][0]["evidence_locators"] = [
            "fixture://FX-001/E1#value",
            "fixture://FX-001/E1#value",
        ]
        with self.assertRaisesRegex(ValueError, "at most once"):
            parse_gauge_review(
                payload,
                evaluation_id="eval",
                allowed_locators=("fixture://FX-001/E1#value",),
            )
        payload["findings"][0]["evidence_locators"] = ["fixture://invented/E1#value"]
        with self.assertRaisesRegex(ValueError, "not one of"):
            parse_gauge_review(
                payload,
                evaluation_id="eval",
                allowed_locators=("fixture://FX-001/E1#value",),
            )

    def test_consensus_requires_all_runs_and_strict_majority(self) -> None:
        reviews = (
            review("eval", "defective", "numeric_mismatch"),
            review("eval", "defective", "numeric_mismatch"),
            review("eval", "supported"),
        )
        consensus = consensus_review(reviews, required_runs=3)
        self.assertEqual(consensus.disposition, "defective")
        self.assertEqual(consensus.findings[0].defect_class, "numeric_mismatch")
        with self.assertRaisesRegex(ValueError, "every"):
            consensus_review(reviews[:2], required_runs=3)


class BenchmarkProtectionTests(unittest.TestCase):
    def test_v3_visible_partition_is_exact_and_verification_is_physically_absent(self) -> None:
        calibration = BenchmarkCorpus.load(V3_CORPUS_ROOT, partition="calibration")
        quarantine = BenchmarkCorpus.load(V3_CORPUS_ROOT, partition="quarantine")
        self.assertEqual((len(calibration.objective), len(calibration.fixtures)), (80, 40))
        self.assertEqual((len(quarantine.borderline), len(quarantine.fixtures)), (6, 6))
        self.assertFalse((V3_CORPUS_ROOT / "verification/cases.jsonl").exists())
        self.assertFalse((V3_CORPUS_ROOT / "verification/fixtures.json").exists())
        with self.assertRaisesRegex(ValueError, "physically absent"):
            BenchmarkCorpus.load(V3_CORPUS_ROOT, partition="verification")

    def test_v3_control_adopts_split_and_only_mechanically_sizes_budget(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            result = prepare_v3_control_manifests(
                corpus_root=V3_CORPUS_ROOT,
                scoring_path=CONTROL / "scoring-contract.json",
                base_config_path=CONTROL / "optimization-config.json",
                resumption_path=CONTROL / "v3/resumption.json",
                output=target,
                authoring_commit="8a44d4a13b69db443953d7162b659d4034b1b982",
            )
            self.assertEqual(result["maximum_calibration_model_calls"], 400)
            self.assertEqual(
                hashlib.sha256((target / "scoring-contract.json").read_bytes()).hexdigest(),
                hashlib.sha256((CONTROL / "scoring-contract.json").read_bytes()).hexdigest(),
            )
            partition = json.loads((target / "partition-manifest.json").read_text())
            self.assertEqual(len(partition["calibration"]["case_ids"]), 80)
            self.assertIsNone(partition["verification"]["case_ids"])
            self.assertEqual(partition["quarantine_case_count"], 6)
            config = json.loads((target / "optimization-config.json").read_text())
            self.assertEqual(
                config["optimization_budget"]["maximum_calibration_model_calls"], 400
            )
            self.assertEqual(config["optimization_budget"]["terminal_runs_per_case"], 3)

    def test_v2_visible_partition_is_exact_and_held_out_is_physically_absent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            visible = Path(directory) / "visible-corpus"
            shutil.copytree(
                V2_CORPUS_ROOT,
                visible,
                ignore=shutil.ignore_patterns("validation"),
            )
            calibration = BenchmarkCorpus.load(visible, partition="calibration")
            quarantine = BenchmarkCorpus.load(visible, partition="quarantine")
            self.assertEqual((len(calibration.objective), len(calibration.fixtures)), (44, 22))
            self.assertEqual((len(quarantine.borderline), len(quarantine.fixtures)), (4, 4))
            self.assertFalse((visible / "validation/cases.jsonl").exists())
            self.assertFalse((visible / "validation/fixtures.json").exists())
            with self.assertRaisesRegex(ValueError, "physically absent"):
                BenchmarkCorpus.load(visible, partition="validation")

    def test_restored_v2_validation_matches_preregistered_hashes(self) -> None:
        expected = {
            "cases.jsonl": "22e98803f86c36fc1009ce8c16b153e3e4bc871b31740f2620bab13a16fb899d",
            "fixtures.json": "9afb3a99090a85574f6c2a5effaf8a56fe93648eb85bbe280e21ccd84fbb0bbf",
        }
        for name, digest in expected.items():
            path = V2_CORPUS_ROOT / "validation" / name
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        validation = BenchmarkCorpus.load(V2_CORPUS_ROOT, partition="validation")
        self.assertEqual((len(validation.objective), len(validation.fixtures)), (28, 14))

    def test_v2_control_adopts_author_split_without_rerandomization(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            tempfile.TemporaryDirectory() as corpus_directory,
        ):
            target = Path(directory)
            visible = Path(corpus_directory) / "visible-corpus"
            shutil.copytree(
                V2_CORPUS_ROOT,
                visible,
                ignore=shutil.ignore_patterns("validation"),
            )
            result = prepare_v2_control_manifests(
                corpus_root=visible,
                scoring_path=CONTROL / "scoring-contract.json",
                config_path=CONTROL / "optimization-config.json",
                output=target,
                authoring_commit="ac2837034078ec101ea7e2a582916268b88663fb",
            )
            self.assertEqual(
                result["corpus_digest"],
                "09ec5ab31d4f9683e7ce7f9064fb294f388d4846b5f75a68875f69a6c740c54a",
            )
            partition = json.loads((target / "partition-manifest.json").read_text())
            self.assertEqual(len(partition["calibration"]["case_ids"]), 44)
            self.assertIsNone(partition["validation"]["case_ids"])
            self.assertFalse(partition["rerandomized"])

    def test_projection_withholds_reference_pair_adjudicability_and_title(self) -> None:
        corpus = BenchmarkCorpus.load(CORPUS_ROOT)
        payload = corpus.reviewer_payload(str(corpus.objective[0]["case_id"]))
        serialized = json.dumps(payload)
        for field in ("reference_qa", "pair_id", "adjudicability", "title"):
            self.assertNotIn(f'"{field}"', serialized)
        self.assertEqual(len(corpus.objective), 62)
        self.assertEqual(len(corpus.borderline), 4)

    def test_seeded_split_is_reproducible_disjoint_pair_preserving_and_quarantined(self) -> None:
        with (
            tempfile.TemporaryDirectory() as left_name,
            tempfile.TemporaryDirectory() as right_name,
        ):
            left = Path(left_name)
            right = Path(right_name)
            for target in (left, right):
                prepare_control_manifests(
                    corpus_root=CORPUS_ROOT,
                    scoring_path=CONTROL / "scoring-contract.json",
                    config_path=CONTROL / "optimization-config.json",
                    output=target,
                    preregistration_commit="test",
                )
            left_partition = json.loads((left / "partition-manifest.json").read_text())
            right_partition = json.loads((right / "partition-manifest.json").read_text())
            self.assertEqual(left_partition, right_partition)
            calibration = set(left_partition["calibration"]["case_ids"])
            validation = set(left_partition["validation"]["case_ids"])
            self.assertEqual((len(calibration), len(validation)), (40, 22))
            self.assertTrue(calibration.isdisjoint(validation))
            corpus = BenchmarkCorpus.load(CORPUS_ROOT)
            for case in corpus.objective:
                mate_ids = {
                    str(item["case_id"])
                    for item in corpus.objective
                    if item["pair_id"] == case["pair_id"]
                }
                self.assertTrue(mate_ids <= calibration or mate_ids <= validation)
            quarantine = json.loads((left / "quarantine-manifest.json").read_text())
            self.assertEqual(
                [item["case_id"] for item in quarantine["cases"]],
                ["RFIQA-063", "RFIQA-064", "RFIQA-065", "RFIQA-066"],
            )
            self.assertTrue(
                {item["case_id"] for item in quarantine["cases"]}.isdisjoint(
                    calibration | validation
                )
            )


class ScoringTests(unittest.TestCase):
    @staticmethod
    def _cases_with_defective_and_indeterminate(corpus: BenchmarkCorpus) -> list[dict[str, object]]:
        non_supported_pairs: dict[str, str] = {}
        for case in corpus.objective:
            disposition = str(case["reference_qa"]["disposition"])
            if disposition != "supported" and disposition not in non_supported_pairs:
                non_supported_pairs[disposition] = str(case["pair_id"])
        selected = {non_supported_pairs["defective"], non_supported_pairs["indeterminate"]}
        return [case for case in corpus.objective if str(case["pair_id"]) in selected]

    def test_exact_disposition_finding_grounding_pair_and_repeatability_scores(self) -> None:
        corpus = BenchmarkCorpus.load(CORPUS_ROOT)
        cases = self._cases_with_defective_and_indeterminate(corpus)
        reviews_by_case = {}
        for case in cases:
            case_id = str(case["case_id"])
            evaluation_id = str(corpus.reviewer_payload(case_id)["evaluation_id"])
            reference = case["reference_qa"]
            if reference["disposition"] == "supported":
                item = review(evaluation_id, "supported")
            else:
                finding = reference["material_findings"][0]
                item = review(
                    evaluation_id,
                    str(reference["disposition"]),
                    str(finding["defect_class"]),
                    str(finding["evidence_locators"][0]),
                )
            reviews_by_case[case_id] = (item, item, item)
        contract = json.loads((CONTROL / "scoring-contract.json").read_text())
        score = score_partition(
            cases=cases,
            reviews_by_case=reviews_by_case,
            contract=contract,
            required_runs=3,
        )
        self.assertEqual(score["metrics"]["disposition_accuracy"], 1.0)
        self.assertEqual(score["metrics"]["evidence_grounding_rate"], 1.0)
        self.assertEqual(score["metrics"]["matched_pair_discrimination"], 1.0)
        self.assertEqual(score["metrics"]["disposition_full_agreement"], 1.0)

    def test_false_accept_false_reject_and_unsupported_finding_are_separate(self) -> None:
        corpus = BenchmarkCorpus.load(CORPUS_ROOT)
        cases = self._cases_with_defective_and_indeterminate(corpus)
        reviews_by_case = {}
        for case in cases:
            case_id = str(case["case_id"])
            evaluation_id = str(corpus.reviewer_payload(case_id)["evaluation_id"])
            if case["reference_qa"]["disposition"] == "supported":
                item = review(evaluation_id, "defective", "unsupported_claim")
            else:
                item = review(evaluation_id, "supported")
            reviews_by_case[case_id] = (item,)
        contract = json.loads((CONTROL / "scoring-contract.json").read_text())
        score = score_partition(
            cases=cases,
            reviews_by_case=reviews_by_case,
            contract=contract,
            required_runs=1,
        )
        self.assertEqual(score["counts"]["false_accepts"], 1)
        self.assertEqual(score["counts"]["false_rejects"], 2)
        self.assertEqual(score["counts"]["unsupported_findings"], 2)


class HarnessBoundaryTests(unittest.TestCase):
    def test_decomposed_design_separates_truth_state_from_defect_mechanism(self) -> None:
        corpus = BenchmarkCorpus.load(CORPUS_ROOT)
        prompt = prompt_for_design(
            DESIGN_GAUGE_V2,
            corpus.reviewer_payload("RFIQA-023"),
        )
        self.assertIn("EPISTEMIC STATE", prompt)
        self.assertIn("neither establishable nor refutable", prompt)
        self.assertIn("denominator_error", prompt)
        self.assertNotIn("reference_qa", prompt)

    def test_v3_design_prioritizes_epistemic_state_and_root_cause(self) -> None:
        prompt = prompt_for_design(DESIGN_GAUGE_V3, {"case_id": "case"})
        self.assertIn("Truth status controls disposition", prompt)
        self.assertIn("A calibration requirement does not manufacture a contrary fact", prompt)
        self.assertIn("smallest set of non-overlapping material root-cause findings", prompt)
        self.assertIn("ordinary connective wording", prompt)
        self.assertIn("internal_inconsistency", prompt)
        self.assertIn("qualification_omitted", prompt)
        self.assertIn("provenance_authority_error", prompt)

    def test_validation_requires_freeze_and_one_shot_marker_is_implemented(self) -> None:
        source = (ROOT / "scripts/task075_qa_gauge_experiment.py").read_text(encoding="utf-8")
        self.assertIn('phase["phase"] != "frozen"', source)
        self.assertIn("held-out verification has already been attempted", source)
        self.assertIn("assert_frozen_gauge", source)
        self.assertIn("post-freeze mutation detected", source)
        self.assertNotIn(
            "reference_qa",
            (ROOT / "src/rfi/qa_gauge/prompts.py").read_text(encoding="utf-8"),
        )

    def test_harness_does_not_import_repair_or_task074_or_mcp(self) -> None:
        source = (ROOT / "scripts/task075_qa_gauge_experiment.py").read_text(encoding="utf-8")
        for prohibited in (
            "parse_repair",
            "SingleRepairLifecycle",
            "rfi.investigation_qa",
            "rfi.mcp",
        ):
            self.assertNotIn(prohibited, source)


if __name__ == "__main__":
    unittest.main()
