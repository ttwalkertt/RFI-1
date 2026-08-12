"""Frozen-corpus loading, reviewer projection, quarantine, and matched-pair partitioning."""

from __future__ import annotations

import hashlib
import json
import random
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_digest(value: Any) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


@dataclass(frozen=True)
class BenchmarkCorpus:
    """Read-only view of the independently authored candidate corpus."""

    root: Path
    cases: tuple[dict[str, Any], ...]
    fixtures: dict[str, dict[str, Any]]
    benchmark_version: str = "rfi-qa-candidates-v1"
    partition: str = "combined"

    @classmethod
    def load(cls, root: Path, *, partition: str = "calibration") -> BenchmarkCorpus:
        resolved = root.resolve()
        if (resolved / "split-manifest.json").exists() and (resolved / "calibration").is_dir():
            if partition not in {"calibration", "validation", "quarantine"}:
                raise ValueError(f"unknown benchmark v2 partition: {partition}")
            case_path = resolved / partition / "cases.jsonl"
            fixture_path = resolved / partition / "fixtures.json"
            if not case_path.exists() or not fixture_path.exists():
                raise ValueError(f"benchmark v2 {partition} partition is physically absent")
            cases = tuple(
                json.loads(line)
                for line in case_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
            fixture_payload = json.loads(fixture_path.read_text(encoding="utf-8"))
            fixtures = {str(item["fixture_id"]): item for item in fixture_payload["fixtures"]}
            manifest = json.loads((resolved / "split-manifest.json").read_text(encoding="utf-8"))
            expected = manifest["partitions"][partition]
            if len(cases) != int(expected["case_count"]) or len(fixtures) != int(
                expected["fixture_count"]
            ):
                raise ValueError(
                    f"benchmark v2 {partition} composition differs from split manifest"
                )
            return cls(
                resolved,
                cases,
                fixtures,
                benchmark_version=str(manifest["benchmark_version"]),
                partition=partition,
            )
        cases = tuple(
            json.loads(line)
            for line in (resolved / "candidate_cases.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        )
        fixture_payload = json.loads((resolved / "fixtures.json").read_text(encoding="utf-8"))
        fixtures = {str(item["fixture_id"]): item for item in fixture_payload["fixtures"]}
        if len(cases) != 66 or len(fixtures) != 35:
            raise ValueError("TASK-075 requires the frozen 66-case, 35-fixture candidate revision")
        return cls(resolved, cases, fixtures)

    @property
    def by_id(self) -> dict[str, dict[str, Any]]:
        return {str(case["case_id"]): case for case in self.cases}

    @property
    def objective(self) -> tuple[dict[str, Any], ...]:
        return tuple(case for case in self.cases if case["adjudicability"]["status"] == "objective")

    @property
    def borderline(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            case for case in self.cases if case["adjudicability"]["status"] == "borderline"
        )

    def reviewer_payload(self, case_id: str) -> dict[str, Any]:
        """Project only ticket-authorized input without hidden reference fields."""
        case = self.by_id[case_id]
        fixture = self.fixtures[str(case["fixture_id"])]
        return {
            "evaluation_id": sha256_bytes(f"task075:{case_id}".encode())[:20],
            "investigation_question": case["investigation_question"],
            "answer_requirements": case["answer_requirements"],
            "evidence": {
                "authority": fixture["authority"],
                "records": fixture["records"],
            },
            "submitted_answer": case["submitted_answer"],
        }

    def allowed_locators(self, case_id: str) -> tuple[str, ...]:
        """Return every exact record or authority locator exposed to the reviewer."""
        case = self.by_id[case_id]
        fixture = self.fixtures[str(case["fixture_id"])]
        values = [str(record["locator"]) for record in fixture["records"]]
        authority_locator = fixture["authority"].get("locator")
        if authority_locator:
            values.append(str(authority_locator))
        return tuple(sorted(values))


def _coverage(
    case_ids: list[str],
    corpus: BenchmarkCorpus,
    config: dict[str, Any],
) -> dict[str, Any]:
    cases = [corpus.by_id[case_id] for case_id in case_ids]
    dispositions = Counter(str(case["reference_qa"]["disposition"]) for case in cases)
    difficulties = Counter(str(case["difficulty"]) for case in cases)
    class_set = {
        str(value)
        for case in cases
        for value in case["reference_qa"]["defect_classes"]
    }
    families = {
        name: sorted(class_set.intersection(values))
        for name, values in config["partition"]["coverage_preflight"]["defect_families"].items()
        if class_set.intersection(values)
    }
    return {
        "case_count": len(cases),
        "pair_count": len({case["pair_id"] for case in cases}),
        "dispositions": dict(sorted(dispositions.items())),
        "difficulties": dict(sorted(difficulties.items())),
        "defect_classes": sorted(class_set),
        "defect_families": families,
    }


def _coverage_errors(coverage: dict[str, Any], config: dict[str, Any]) -> list[str]:
    policy = config["partition"]["coverage_preflight"]
    errors: list[str] = []
    missing = set(policy["required_dispositions_in_each_partition"]) - set(coverage["dispositions"])
    if missing:
        errors.append(f"missing dispositions: {sorted(missing)}")
    if len(coverage["difficulties"]) < int(policy["minimum_difficulty_groups_in_each_partition"]):
        errors.append("insufficient difficulty-group coverage")
    if len(coverage["defect_families"]) < int(policy["minimum_defect_families_in_each_partition"]):
        errors.append("insufficient defect-family coverage")
    return errors


def prepare_control_manifests(
    *,
    corpus_root: Path,
    scoring_path: Path,
    config_path: Path,
    output: Path,
    preregistration_commit: str,
) -> dict[str, Any]:
    """Freeze the corpus and create the fixed-seed whole-pair split exactly once."""
    output.mkdir(parents=True, exist_ok=True)
    for name in (
        "corpus-freeze-manifest.json",
        "quarantine-manifest.json",
        "partition-manifest.json",
    ):
        if (output / name).exists():
            raise ValueError(
                "control manifests already exist; partition regeneration is prohibited"
            )
    corpus = BenchmarkCorpus.load(corpus_root)
    if len(corpus.objective) != 62 or len(corpus.borderline) != 4:
        raise ValueError("unexpected objective/quarantine composition")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    scoring = json.loads(scoring_path.read_text(encoding="utf-8"))
    if not scoring.get("frozen_before_partition"):
        raise ValueError("scoring contract was not frozen before partition")
    pairs: dict[str, list[str]] = defaultdict(list)
    for case in corpus.objective:
        pairs[str(case["pair_id"])].append(str(case["case_id"]))
    if len(pairs) != 31 or any(len(value) != 2 for value in pairs.values()):
        raise ValueError("objective cases are not exactly 31 complete matched pairs")
    seed = int(config["partition"]["random_seed"])
    pair_ids = sorted(pairs)
    random.Random(seed).shuffle(pair_ids)
    calibration_pairs = pair_ids[: int(config["partition"]["calibration_pairs"])]
    validation_pairs = pair_ids[len(calibration_pairs) :]
    calibration_ids = sorted(case_id for pair_id in calibration_pairs for case_id in pairs[pair_id])
    validation_ids = sorted(case_id for pair_id in validation_pairs for case_id in pairs[pair_id])
    calibration_coverage = _coverage(calibration_ids, corpus, config)
    validation_coverage = _coverage(validation_ids, corpus, config)
    errors = {
        "calibration": _coverage_errors(calibration_coverage, config),
        "validation": _coverage_errors(validation_coverage, config),
    }
    if any(errors.values()):
        rejected = {
            "seed": seed,
            "reason": errors,
            "calibration_coverage": calibration_coverage,
            "validation_coverage": validation_coverage,
        }
        (output / "rejected-partition-manifest.json").write_text(
            json.dumps(rejected, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        raise ValueError(f"seed {seed} failed preregistered coverage: {errors}")
    file_names = (
        "candidate_cases.jsonl",
        "fixtures.json",
        "case.schema.json",
        "fixture.schema.json",
        "README.md",
        "coverage-analysis.md",
        "borderline-review.md",
        "validate_candidates.py",
    )
    corpus_files = {
        name: {"sha256": sha256(corpus.root / name), "bytes": (corpus.root / name).stat().st_size}
        for name in file_names
    }
    freeze = {
        "manifest_version": "task075.corpus-freeze.v1",
        "preregistration_commit": preregistration_commit,
        "scoring_contract_sha256": sha256(scoring_path),
        "optimization_config_sha256": sha256(config_path),
        "corpus_files": corpus_files,
        "corpus_digest": canonical_digest(corpus_files),
        "objective_case_count": 62,
        "objective_pair_count": 31,
        "objective_case_digests": {
            str(case["case_id"]): canonical_digest(case) for case in corpus.objective
        },
        "borderline_case_count": 4,
        "benchmark_mutation_permitted": False,
    }
    quarantine = {
        "manifest_version": "task075.quarantine.v1",
        "reason": (
            "judgment-dependent; excluded unchanged from calibration, validation, scoring, "
            "RBF feedback, and success criteria"
        ),
        "cases": [
            {
                "case_id": str(case["case_id"]),
                "sha256": canonical_digest(case),
                "human_review_required": True,
            }
            for case in corpus.borderline
        ],
    }
    partition = {
        "manifest_version": "task075.partition.v1",
        "seed": seed,
        "algorithm": (
            "sort pair IDs; Python random.Random(seed).shuffle; first 20 calibration, "
            "remaining 11 validation"
        ),
        "unit": "matched pair",
        "rerandomized": False,
        "rejected_splits": [],
        "calibration": {
            "pair_ids": sorted(calibration_pairs),
            "case_ids": calibration_ids,
            "coverage": calibration_coverage,
        },
        "validation": {
            "pair_ids": sorted(validation_pairs),
            "case_ids": validation_ids,
            "coverage": validation_coverage,
        },
        "disjoint": not set(calibration_ids).intersection(validation_ids),
        "objective_population_exhausted": set(calibration_ids + validation_ids)
        == {str(case["case_id"]) for case in corpus.objective},
        "held_out_protection": (
            "validation payloads, labels, outputs, and scores are inaccessible to "
            "run-calibration; run-validation requires a matching frozen-gauge manifest "
            "and one-shot marker"
        ),
    }
    for name, payload in (
        ("corpus-freeze-manifest.json", freeze),
        ("quarantine-manifest.json", quarantine),
        ("partition-manifest.json", partition),
    ):
        (output / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return {
        "corpus_digest": freeze["corpus_digest"],
        "objective_cases": 62,
        "quarantined_cases": 4,
        "calibration_pairs": len(calibration_pairs),
        "validation_pairs": len(validation_pairs),
        "coverage_passed": True,
    }


def prepare_v2_control_manifests(
    *,
    corpus_root: Path,
    scoring_path: Path,
    config_path: Path,
    output: Path,
    authoring_commit: str,
) -> dict[str, Any]:
    """Adopt the independently authored visible-only v2 split without recreating it."""
    root = corpus_root.resolve()
    split_path = root / "split-manifest.json"
    split = json.loads(split_path.read_text(encoding="utf-8"))
    if split["benchmark_version"] != "rfi-qa-independent-v2.0.0":
        raise ValueError("unexpected benchmark v2 identity")
    expected_corpus_digest = (
        "09ec5ab31d4f9683e7ce7f9064fb294f388d4846b5f75a68875f69a6c740c54a"
    )
    if split["digests"]["corpus_sha256"] != expected_corpus_digest:
        raise ValueError("benchmark v2 corpus digest differs from the authorized value")
    if split["split"] != {
        "algorithm": (
            "lexicographically sort R2P-001 through R2P-036; Python "
            "random.Random(seed).shuffle; first 22 pairs calibration; remaining 14 "
            "validation"
        ),
        "calibration_pair_target": 22,
        "objective_pair_id_population": {"count": 36, "first": 1, "format": "R2P-NNN", "last": 36},
        "random_seed": 20260811,
        "randomization_unit": "matched_pair",
        "rerandomization_performed": False,
        "validation_pair_target": 14,
    }:
        raise ValueError("benchmark v2 split policy differs from authorization")
    if (root / "validation/cases.jsonl").exists() or (root / "validation/fixtures.json").exists():
        raise ValueError("held-out validation must be physically absent during v2 preparation")
    calibration = BenchmarkCorpus.load(root, partition="calibration")
    quarantine = BenchmarkCorpus.load(root, partition="quarantine")
    if len(calibration.objective) != 44 or len(quarantine.borderline) != 4:
        raise ValueError("benchmark v2 visible population differs from authorization")
    output.mkdir(parents=True, exist_ok=True)
    provenance = output / "provenance/v1"
    provenance.mkdir(parents=True, exist_ok=True)
    for name in (
        "corpus-freeze-manifest.json",
        "quarantine-manifest.json",
        "partition-manifest.json",
    ):
        source = output / name
        target = provenance / name
        if source.exists() and not target.exists():
            shutil.copy2(source, target)
        elif source.exists() and target.exists() and source.read_bytes() != target.read_bytes():
            raise ValueError(f"v1 provenance target differs: {name}")
    expected_files: dict[str, str] = split["digests"]["corpus_files"]
    visible_files = {
        relative: {
            "sha256": expected,
            "bytes": (root / relative).stat().st_size,
        }
        for relative, expected in expected_files.items()
        if not relative.startswith("validation/")
    }
    for relative, identity in visible_files.items():
        if sha256(root / relative) != identity["sha256"]:
            raise ValueError(f"benchmark v2 visible digest mismatch: {relative}")
    freeze = {
        "manifest_version": "task075.corpus-freeze.v2",
        "benchmark_version": split["benchmark_version"],
        "authoring_commit": authoring_commit,
        "scoring_contract_sha256": sha256(scoring_path),
        "optimization_config_sha256": sha256(config_path),
        "source_split_manifest": str(split_path.relative_to(root.parents[1])),
        "source_split_manifest_sha256": sha256(split_path),
        "corpus_digest": split["digests"]["corpus_sha256"],
        "visible_files": visible_files,
        "held_out_files": {
            relative: {"sha256": expected}
            for relative, expected in expected_files.items()
            if relative.startswith("validation/")
        },
        "objective_case_count": 72,
        "objective_pair_count": 36,
        "calibration_case_count": 44,
        "validation_case_count": 28,
        "borderline_case_count": 4,
        "held_out_physically_absent_at_freeze": True,
        "benchmark_mutation_permitted": False,
    }
    quarantine_manifest = {
        "manifest_version": "task075.quarantine.v2",
        "reason": (
            "judgment-dependent; excluded unchanged from calibration, validation, scoring, "
            "RBF feedback, and success criteria"
        ),
        "cases": [
            {
                "case_id": str(case["case_id"]),
                "sha256": canonical_digest(case),
                "human_review_required": True,
            }
            for case in quarantine.borderline
        ],
        "source_cases_sha256": expected_files["quarantine/cases.jsonl"],
        "source_fixtures_sha256": expected_files["quarantine/fixtures.json"],
    }
    partition_manifest = {
        "manifest_version": "task075.partition.v2",
        "source": (
            "independently authored split-manifest.json; not generated or rerandomized "
            "by RBF"
        ),
        "source_split_manifest_sha256": sha256(split_path),
        "seed": 20260811,
        "algorithm": split["split"]["algorithm"],
        "unit": "matched_pair",
        "rerandomized": False,
        "calibration": {
            "case_ids": sorted(str(case["case_id"]) for case in calibration.objective),
            "case_count": 44,
            "pair_count": 22,
            "pair_set_sha256": split["partitions"]["calibration"]["pair_set_sha256"],
            "coverage": split["partitions"]["calibration"],
        },
        "validation": {
            "case_ids": None,
            "case_count": 28,
            "pair_count": 14,
            "pair_set_sha256": split["partitions"]["validation"]["pair_set_sha256"],
            "coverage": split["partitions"]["validation"],
            "physically_absent": True,
        },
        "quarantine_case_count": 4,
        "objective_population_exhausted": True,
        "disjoint": True,
        "held_out_protection": (
            "run-calibration loads only calibration/; run-validation requires a matching "
            "frozen gauge and the exact restored validation file digests; no validation "
            "IDs or content are present before restoration"
        ),
    }
    for name, payload in (
        ("corpus-freeze-manifest.json", freeze),
        ("quarantine-manifest.json", quarantine_manifest),
        ("partition-manifest.json", partition_manifest),
    ):
        (output / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return {
        "benchmark_version": split["benchmark_version"],
        "corpus_digest": freeze["corpus_digest"],
        "calibration_cases": 44,
        "validation_cases_absent": 28,
        "quarantined_cases": 4,
        "rerandomized": False,
    }
