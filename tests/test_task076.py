"""TASK-076 RFI-native Seagate benchmark structure and isolation controls."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks/rfi_native_seagate_transcripts_v1"


def jsonl(relative: str) -> list[dict]:
    return [
        json.loads(line)
        for line in (BENCHMARK / relative).read_text(encoding="utf-8").splitlines()
        if line
    ]


class NativeSeagateBenchmarkTests(unittest.TestCase):
    def test_population_pairs_and_partitions_are_scenario_disjoint(self) -> None:
        calibration = jsonl("calibration/cases.jsonl")
        held_out = jsonl("withheld/payload/cases.jsonl")
        quarantine = jsonl("quarantine/cases.jsonl")
        self.assertEqual((len(calibration), len(held_out), len(quarantine)), (48, 32, 4))
        calibration_scenarios = {case["scenario_id"] for case in calibration}
        held_out_scenarios = {case["scenario_id"] for case in held_out}
        self.assertEqual((len(calibration_scenarios), len(held_out_scenarios)), (24, 16))
        self.assertFalse(calibration_scenarios & held_out_scenarios)
        for population in (calibration, held_out):
            pairs: dict[str, list[dict]] = {}
            for case in population:
                pairs.setdefault(case["scenario_id"], []).append(case)
            for members in pairs.values():
                self.assertEqual(
                    {item["pair_member"] for item in members},
                    {"acceptable", "defective"},
                )
                self.assertEqual(members[0]["question"], members[1]["question"])
                self.assertEqual(
                    members[0]["submitted_evidence_ids"],
                    members[1]["submitted_evidence_ids"],
                )

    def test_core_digests_and_leakage_control_are_frozen(self) -> None:
        digests = json.loads((BENCHMARK / "digests.json").read_text(encoding="utf-8"))
        for relative, expected in digests["members"].items():
            actual = hashlib.sha256((BENCHMARK / relative).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, relative)
        leakage = json.loads(
            (BENCHMARK / "analysis/leakage-artifact-analysis.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(leakage["result"], "PASS")
        self.assertLess(
            leakage["quality_controls"][
                "leave_one_scenario_out_bag_of_words_naive_bayes_accuracy"
            ],
            0.70,
        )


if __name__ == "__main__":
    unittest.main()
