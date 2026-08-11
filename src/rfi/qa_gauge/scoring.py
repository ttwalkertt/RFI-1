"""Frozen TASK-075 consensus, accuracy, grounding, pair, and repeatability scoring."""

from __future__ import annotations

import itertools
import math
from collections import Counter, defaultdict
from dataclasses import asdict
from statistics import pvariance
from typing import Any, Iterable

from rfi.qa_gauge.contracts import GaugeFinding, GaugeReview


def _safe_ratio(numerator: int | float, denominator: int | float, metric: str) -> float:
    if denominator == 0:
        raise ValueError(f"undefined denominator for {metric}")
    return float(numerator) / float(denominator)


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    return len(left.intersection(right)) / len(left.union(right))


def consensus_review(reviews: tuple[GaugeReview, ...], *, required_runs: int) -> GaugeReview:
    """Create the preregistered strict-majority consensus without reference truth."""
    if len(reviews) != required_runs:
        raise ValueError("a terminal consensus requires every preregistered independent run")
    if len({review.evaluation_id for review in reviews}) != 1:
        raise ValueError("cannot combine reviews from different evaluations")
    disposition_counts = Counter(review.disposition for review in reviews)
    disposition, count = disposition_counts.most_common(1)[0]
    if count <= required_runs // 2:
        raise ValueError("no strict-majority disposition")
    by_class: dict[str, list[GaugeFinding]] = defaultdict(list)
    for review in reviews:
        for finding in review.findings:
            by_class[finding.defect_class].append(finding)
    selected = [
        (defect_class, findings)
        for defect_class, findings in sorted(by_class.items())
        if len(findings) > required_runs // 2
    ]
    findings = tuple(
        GaugeFinding(
            finding_id=f"F{index:03d}",
            defect_class=defect_class,
            affected_claim=min(item.affected_claim for item in items),
            finding=min(item.finding for item in items),
            evidence_locators=tuple(sorted({locator for item in items for locator in item.evidence_locators})),
        )
        for index, (defect_class, items) in enumerate(selected, start=1)
    )
    if disposition == "supported" and findings:
        raise ValueError("consensus produced findings beside a supported majority")
    if disposition != "supported" and not findings:
        raise ValueError("consensus non-supported disposition has no majority finding")
    return GaugeReview(
        schema_version=reviews[0].schema_version,
        evaluation_id=reviews[0].evaluation_id,
        disposition=disposition,
        findings=findings,
        rationale=f"Strict-majority consensus from {required_runs} independent runs.",
    )


def _match_findings(
    predicted: tuple[GaugeFinding, ...], reference: list[dict[str, Any]]
) -> tuple[list[tuple[GaugeFinding, dict[str, Any], bool]], list[GaugeFinding], list[dict[str, Any]]]:
    """Stable one-to-one class matching, preferring decisive-locator overlap."""
    unused = list(reference)
    matched: list[tuple[GaugeFinding, dict[str, Any], bool]] = []
    unsupported: list[GaugeFinding] = []
    for finding in predicted:
        candidates = [item for item in unused if item["defect_class"] == finding.defect_class]
        if not candidates:
            unsupported.append(finding)
            continue
        candidates.sort(
            key=lambda item: (
                -len(set(finding.evidence_locators).intersection(item["evidence_locators"])),
                item["finding_id"],
            )
        )
        selected = candidates[0]
        unused.remove(selected)
        grounded = bool(set(finding.evidence_locators).intersection(selected["evidence_locators"]))
        matched.append((finding, selected, grounded))
    return matched, unsupported, unused


def _repeatability(
    cases: list[dict[str, Any]],
    reviews_by_case: dict[str, tuple[GaugeReview, ...]],
) -> dict[str, float]:
    if any(
        str(case["case_id"]) not in reviews_by_case
        or len(reviews_by_case[str(case["case_id"])]) != 3
        for case in cases
    ):
        return {
            "disposition_full_agreement": 0.0,
            "disposition_pairwise_agreement": 0.0,
            "material_detection_full_agreement": 0.0,
            "defect_class_mean_jaccard": 0.0,
            "evidence_reference_mean_jaccard": 0.0,
            "supported_false_positive_count_variance": float("inf"),
        }
    full_disposition = 0
    disposition_agree = disposition_total = 0
    full_detection = 0
    class_jaccards: list[float] = []
    evidence_jaccards: list[float] = []
    supported_variances: list[float] = []
    for case in cases:
        case_id = str(case["case_id"])
        reviews = reviews_by_case[case_id]
        dispositions = [review.disposition for review in reviews]
        detections = [bool(review.findings) for review in reviews]
        full_disposition += len(set(dispositions)) == 1
        full_detection += len(set(detections)) == 1
        for left, right in itertools.combinations(reviews, 2):
            disposition_agree += left.disposition == right.disposition
            disposition_total += 1
            left_classes = {finding.defect_class for finding in left.findings}
            right_classes = {finding.defect_class for finding in right.findings}
            class_jaccards.append(_jaccard(left_classes, right_classes))
            for defect_class in sorted(left_classes.intersection(right_classes)):
                left_refs = next(set(item.evidence_locators) for item in left.findings if item.defect_class == defect_class)
                right_refs = next(set(item.evidence_locators) for item in right.findings if item.defect_class == defect_class)
                evidence_jaccards.append(_jaccard(left_refs, right_refs))
        if case["reference_qa"]["disposition"] == "supported":
            supported_variances.append(pvariance([len(review.findings) for review in reviews]))
    return {
        "disposition_full_agreement": _safe_ratio(full_disposition, len(cases), "disposition_full_agreement"),
        "disposition_pairwise_agreement": _safe_ratio(disposition_agree, disposition_total, "disposition_pairwise_agreement"),
        "material_detection_full_agreement": _safe_ratio(full_detection, len(cases), "material_detection_full_agreement"),
        "defect_class_mean_jaccard": sum(class_jaccards) / len(class_jaccards),
        "evidence_reference_mean_jaccard": (
            sum(evidence_jaccards) / len(evidence_jaccards) if evidence_jaccards else 0.0
        ),
        "supported_false_positive_count_variance": sum(supported_variances) / len(supported_variances),
    }


def _thresholds(metrics: dict[str, float], contract: dict[str, Any]) -> dict[str, Any]:
    outcomes: dict[str, Any] = {}
    for name, rule in contract["success_thresholds"].items():
        observed = metrics.get(name)
        if observed is None or not math.isfinite(observed):
            passed = False
        elif rule["operator"] == ">=":
            passed = observed >= float(rule["value"])
        elif rule["operator"] == "<=":
            passed = observed <= float(rule["value"])
        else:
            raise ValueError(f"unknown threshold operator for {name}")
        outcomes[name] = {"observed": observed, **rule, "passed": passed}
    return outcomes


def score_partition(
    *,
    cases: Iterable[dict[str, Any]],
    reviews_by_case: dict[str, tuple[GaugeReview, ...]],
    contract: dict[str, Any],
    required_runs: int,
) -> dict[str, Any]:
    """Score consensus and repeats against hidden reference truth."""
    case_list = list(cases)
    valid_consensus: dict[str, GaugeReview] = {}
    invalid: dict[str, str] = {}
    per_case: list[dict[str, Any]] = []
    matched_total = grounded_total = unsupported_total = expected_total = predicted_total = 0
    locator_hits = locator_total = 0
    confusion: Counter[tuple[str, str]] = Counter()
    class_expected: Counter[str] = Counter()
    class_predicted: Counter[str] = Counter()
    class_matched: Counter[str] = Counter()
    for case in case_list:
        case_id = str(case["case_id"])
        try:
            consensus = consensus_review(reviews_by_case[case_id], required_runs=required_runs)
        except (KeyError, ValueError) as exc:
            invalid[case_id] = str(exc)
            continue
        valid_consensus[case_id] = consensus
        reference = case["reference_qa"]
        predicted = consensus.findings
        expected = list(reference["material_findings"])
        matched, unsupported, missed = _match_findings(predicted, expected)
        matched_total += len(matched)
        grounded_total += sum(grounded for _, _, grounded in matched)
        unsupported_total += len(unsupported)
        expected_total += len(expected)
        predicted_total += len(predicted)
        confusion[(str(reference["disposition"]), consensus.disposition)] += 1
        class_expected.update(str(item["defect_class"]) for item in expected)
        class_predicted.update(item.defect_class for item in predicted)
        class_matched.update(item.defect_class for item, _, _ in matched)
        for predicted_finding, reference_finding, _ in matched:
            locator_total += len(predicted_finding.evidence_locators)
            locator_hits += len(set(predicted_finding.evidence_locators).intersection(reference_finding["evidence_locators"]))
        per_case.append(
            {
                "case_id": case_id,
                "pair_id": case["pair_id"],
                "reference_disposition": reference["disposition"],
                "consensus_disposition": consensus.disposition,
                "disposition_correct": reference["disposition"] == consensus.disposition,
                "expected_classes": list(reference["defect_classes"]),
                "predicted_classes": [item.defect_class for item in predicted],
                "matched_classes": [item.defect_class for item, _, _ in matched],
                "grounded_matches": [item.defect_class for item, _, grounded in matched if grounded],
                "unsupported_classes": [item.defect_class for item in unsupported],
                "missed_classes": [str(item["defect_class"]) for item in missed],
            }
        )
    valid_count = len(valid_consensus)
    defective = [case for case in case_list if case["reference_qa"]["disposition"] == "defective"]
    supported = [case for case in case_list if case["reference_qa"]["disposition"] == "supported"]
    indeterminate = [case for case in case_list if case["reference_qa"]["disposition"] == "indeterminate"]
    disposition_correct = sum(item["disposition_correct"] for item in per_case)
    false_accepts = sum(
        valid_consensus.get(str(case["case_id"]), object()).disposition == "supported"
        for case in defective
        if str(case["case_id"]) in valid_consensus
    )
    false_rejects = sum(
        valid_consensus.get(str(case["case_id"]), object()).disposition != "supported"
        for case in supported
        if str(case["case_id"]) in valid_consensus
    )
    indeterminate_correct = sum(
        valid_consensus.get(str(case["case_id"]), object()).disposition == "indeterminate"
        for case in indeterminate
        if str(case["case_id"]) in valid_consensus
    )
    pair_rows: list[dict[str, Any]] = []
    for pair_id in sorted({str(case["pair_id"]) for case in case_list}):
        members = [item for item in per_case if str(item["pair_id"]) == pair_id]
        passed = False
        if len(members) == 2 and all(item["disposition_correct"] for item in members):
            non_supported = next(item for item in members if item["reference_disposition"] != "supported")
            passed = bool(non_supported["grounded_matches"])
        pair_rows.append({"pair_id": pair_id, "passed": passed})
    precision = _safe_ratio(matched_total, predicted_total, "defect precision") if predicted_total else 0.0
    recall = _safe_ratio(matched_total, expected_total, "material_finding_recall")
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    metrics = {
        "valid_evaluation_rate": valid_count / len(case_list),
        "disposition_accuracy": (
            _safe_ratio(disposition_correct, valid_count, "disposition_accuracy")
            if valid_count
            else 0.0
        ),
        "material_false_accept_rate": _safe_ratio(false_accepts, len(defective), "material_false_accept_rate"),
        "supported_false_reject_rate": _safe_ratio(false_rejects, len(supported), "supported_false_reject_rate"),
        "material_finding_recall": recall,
        "defect_class_attribution_f1": f1,
        "evidence_grounding_rate": (
            _safe_ratio(grounded_total, matched_total, "evidence_grounding_rate")
            if matched_total
            else 0.0
        ),
        "unsupported_finding_rate": unsupported_total / predicted_total if predicted_total else 0.0,
        "indeterminate_accuracy": _safe_ratio(indeterminate_correct, len(indeterminate), "indeterminate_accuracy"),
        "matched_pair_discrimination": _safe_ratio(sum(item["passed"] for item in pair_rows), len(pair_rows), "matched_pair_discrimination"),
    }
    if required_runs == 3:
        metrics.update(_repeatability(case_list, reviews_by_case))
    thresholds = _thresholds(metrics, contract)
    return {
        "scoring_contract_version": contract["contract_version"],
        "case_count": len(case_list),
        "valid_case_count": valid_count,
        "invalid_cases": invalid,
        "metrics": metrics,
        "thresholds": thresholds,
        "all_thresholds_passed": len(thresholds) == len(contract["success_thresholds"])
        and all(item["passed"] for item in thresholds.values()),
        "counts": {
            "false_accepts": false_accepts,
            "false_rejects": false_rejects,
            "expected_findings": expected_total,
            "predicted_findings": predicted_total,
            "matched_findings": matched_total,
            "grounded_matches": grounded_total,
            "unsupported_findings": unsupported_total,
            "evidence_locator_hits": locator_hits,
            "evidence_locators_predicted_on_matches": locator_total,
        },
        "whole_answer_confusion_matrix": {
            f"{reference}->{predicted}": count
            for (reference, predicted), count in sorted(confusion.items())
        },
        "defect_classes": {
            defect_class: {
                "expected": class_expected[defect_class],
                "predicted": class_predicted[defect_class],
                "matched": class_matched[defect_class],
                "recall": class_matched[defect_class] / class_expected[defect_class]
                if class_expected[defect_class]
                else None,
                "precision": class_matched[defect_class] / class_predicted[defect_class]
                if class_predicted[defect_class]
                else None,
            }
            for defect_class in sorted(set(class_expected).union(class_predicted))
        },
        "matched_pairs": pair_rows,
        "cases": sorted(per_case, key=lambda item: item["case_id"]),
        "consensus": {
            case_id: asdict(review) for case_id, review in sorted(valid_consensus.items())
        },
    }
