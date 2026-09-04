#!/usr/bin/env python3
"""Generate deterministic aggregate benchmark and evidence-withheld analyses."""

from __future__ import annotations

import json, math, re, statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOKEN = re.compile(r"[a-z0-9][a-z0-9+.-]+")
UNCERTAIN = re.compile(r"\b(cannot|indeterminate|insufficient|uncertain|limitation|bounded|provisional)\b", re.I)


def rows(relative):
    return [json.loads(x) for x in (ROOT / relative).read_text().splitlines() if x]


def emit(name, value):
    path = ROOT / "analysis" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def toks(text):
    return TOKEN.findall(text.lower())


def binary_nb(cases):
    groups = defaultdict(list)
    for case in cases:
        groups[case["scenario_id"]].append(case)
    correct = total = 0
    for held, members in groups.items():
        train = [c for c in cases if c["scenario_id"] != held]
        counts = {q: Counter() for q in ("acceptable", "defective")}
        totals, vocab = Counter(), set()
        for case in train:
            bag = Counter(toks(case["submitted_answer"])); label = case["pair_member"]
            counts[label].update(bag); totals[label] += sum(bag.values()); vocab.update(bag)
        for case in members:
            bag = Counter(toks(case["submitted_answer"])); scores = {}
            for label in counts:
                score = math.log(.5); denom = totals[label] + len(vocab)
                score += sum(n * math.log((counts[label][word] + 1) / denom) for word, n in bag.items())
                scores[label] = score
            correct += max(scores, key=scores.get) == case["pair_member"]; total += 1
    return correct / total


def defect_nb(defective, refmap):
    labels = sorted({refmap[c["case_id"]]["primary_failure"] for c in defective}); correct = 0
    for held in defective:
        train = [c for c in defective if c is not held]
        counts = {label: Counter() for label in labels}; totals, priors, vocab = Counter(), Counter(), set()
        for case in train:
            label = refmap[case["case_id"]]["primary_failure"]; bag = Counter(toks(case["submitted_answer"]))
            counts[label].update(bag); totals[label] += sum(bag.values()); priors[label] += 1; vocab.update(bag)
        bag = Counter(toks(held["submitted_answer"])); scores = {}
        for label in labels:
            score = math.log((priors[label] + 1) / (len(train) + len(labels))); denom = totals[label] + len(vocab)
            score += sum(n * math.log((counts[label][word] + 1) / denom) for word, n in bag.items()); scores[label] = score
        correct += max(scores, key=scores.get) == refmap[held["case_id"]]["primary_failure"]
    return correct / len(defective), len(labels)


def pair_heuristic(pairs, feature):
    score = 0
    for pair in pairs.values():
        q = {x["pair_member"]: feature(x) for x in pair}
        score += 1 if q["acceptable"] > q["defective"] else .5 if q["acceptable"] == q["defective"] else 0
    return score / len(pairs)


def main():
    calibration, held = rows("calibration/cases.jsonl"), rows("withheld/payload/cases.jsonl")
    refs = rows("calibration/reference.jsonl") + rows("withheld/payload/reference.jsonl")
    cases, refmap = calibration + held, {x["case_id"]: x for x in refs}
    pairs = defaultdict(list)
    for case in cases: pairs[case["scenario_id"]].append(case)
    assignments = json.loads((ROOT / "withheld/payload/private-split-manifest.json").read_text())["scenario_assignments"]
    family = Counter(x["question_family"] for x in assignments)
    structures = Counter(x["reasoning_structure"] for x in assignments)
    mechanisms = Counter(x["failure_mechanism"] for x in assignments)
    diversity = {
        "nominal_answer_cases": len(cases), "independent_question_evidence_scenarios": len(pairs),
        "estimated_independent_semantic_templates": len(pairs),
        "estimation_basis": "Each scenario has a separately authored question, evidence universe, reasoning structure, and material mutation; pair members are one template.",
        "question_family_count": len(family), "question_families": dict(sorted(family.items())),
        "reasoning_structure_count": len(structures), "reasoning_structures": dict(sorted(structures.items())),
        "failure_mechanism_count": len(mechanisms), "failure_mechanisms": dict(sorted(mechanisms.items())),
        "largest_family_share": max(family.values()) / len(pairs),
        "semantic_template_concentration_result": "PASS" if max(family.values()) / len(pairs) <= .15 else "REVIEW",
    }
    emit("diversity-analysis.json", diversity)

    evidence_counts, cited_docs, cited_dates = [], set(), set()
    for pair in pairs.values():
        ref = refmap[pair[0]["case_id"]]; evidence_counts.append(len(ref["evidence"]))
        cited_docs.update(e["document_id"] for e in ref["evidence"]); cited_dates.update(e["event_date"] for e in ref["evidence"])
    corpus = json.loads((ROOT / "corpus/seagate-transcript-corpus-manifest.json").read_text())
    doc_spans = [len(x["evidence_documents"]) for x in assignments]; date_spans = [len(x["evidence_dates"]) for x in assignments]
    volume = {
        "evidence_per_scenario": {"minimum": min(evidence_counts), "maximum": max(evidence_counts), "mean": statistics.mean(evidence_counts), "median": statistics.median(evidence_counts), "distribution": dict(sorted(Counter(evidence_counts).items()))},
        "transcript_span_per_scenario": {"minimum": min(doc_spans), "maximum": max(doc_spans), "mean": statistics.mean(doc_spans), "distribution": dict(sorted(Counter(doc_spans).items()))},
        "date_span_per_scenario": {"minimum": min(date_spans), "maximum": max(date_spans), "mean": statistics.mean(date_spans), "distribution": dict(sorted(Counter(date_spans).items()))},
        "corpus_date_from": corpus["date_from"], "corpus_date_through": corpus["date_through"], "cited_date_from": min(cited_dates), "cited_date_through": max(cited_dates),
        "unique_cited_transcripts": len(cited_docs), "corpus_transcripts": corpus["transcript_count"], "transcript_coverage_fraction": len(cited_docs) / corpus["transcript_count"], "unique_cited_dates": len(cited_dates),
    }
    emit("evidence-volume-date-span-analysis.json", volume)

    word = defaultdict(list); char = defaultdict(list); locators = defaultdict(list); deltas = []; same_q = same_e = 0
    for pair in pairs.values():
        p = {x["pair_member"]: x for x in pair}
        for quality, case in p.items():
            word[quality].append(len(case["submitted_answer"].split())); char[quality].append(len(case["submitted_answer"])); locators[quality].append(len(case["submitted_evidence_ids"]))
        deltas.append(word["acceptable"][-1] - word["defective"][-1]); same_q += p["acceptable"]["question"] == p["defective"]["question"]; same_e += p["acceptable"]["submitted_evidence_ids"] == p["defective"]["submitted_evidence_ids"]
    symmetry = {
        "pairs": len(pairs), "same_question_pairs": same_q, "same_evidence_universe_pairs": same_e,
        "answer_word_count": {q: {"mean": statistics.mean(v), "median": statistics.median(v), "minimum": min(v), "maximum": max(v)} for q,v in word.items()},
        "answer_character_count": {q: {"mean": statistics.mean(v), "median": statistics.median(v)} for q,v in char.items()},
        "paired_word_delta_acceptable_minus_defective": {"mean": statistics.mean(deltas), "median": statistics.median(deltas), "max_absolute": max(abs(x) for x in deltas)},
        "locator_count": {q: {"mean": statistics.mean(v), "distribution": dict(sorted(Counter(v).items()))} for q,v in locators.items()},
        "result": "PASS" if same_e == len(pairs) and abs(statistics.mean(deltas)) <= 2 else "REVIEW",
    }
    emit("pair-symmetry-analysis.json", symmetry)

    controls = {
        "longer_answer_pair_heuristic_accuracy": pair_heuristic(pairs, lambda c: len(c["submitted_answer"].split())),
        "more_locators_pair_heuristic_accuracy": pair_heuristic(pairs, lambda c: len(c["submitted_evidence_ids"])),
        "more_uncertainty_terms_pair_heuristic_accuracy": pair_heuristic(pairs, lambda c: len(UNCERTAIN.findall(c["submitted_answer"]))),
        "leave_one_scenario_out_bag_of_words_naive_bayes_accuracy": binary_nb(cases), "chance_accuracy": .5,
    }
    defect_accuracy, class_count = defect_nb([c for c in cases if c["pair_member"] == "defective"], refmap)
    leakage = {
        "protocol": "Evidence-withheld controls use answer text and locator counts only; each held-out scenario's evidence, rationales, and labels are unavailable to its classifier.",
        "quality_controls": controls,
        "defect_family_control": {"leave_one_case_out_bag_of_words_naive_bayes_accuracy": defect_accuracy, "uniform_chance_accuracy": 1/class_count, "class_count": class_count},
        "acceptance_threshold": "No answer-quality control may reach 0.70 accuracy; defect-family text accuracy must remain below 0.35.",
        "result": "PASS" if max(v for k,v in controls.items() if k != "chance_accuracy") < .70 and defect_accuracy < .35 else "FAIL",
        "interpretation": "Passing reduces obvious shortcut signal in this authored corpus; it does not prove absence of every possible leakage channel.",
    }
    emit("leakage-artifact-analysis.json", leakage)
    emit("distributions.json", {
        "proposition_state": dict(sorted(Counter(r["proposition_state"] for r in refs).items())),
        "answer_quality": dict(sorted(Counter(r["answer_quality"] for r in refs).items())),
        "primary_failure": dict(sorted(Counter(r["primary_failure"] for r in refs if r["primary_failure"]).items())),
        "acceptable_failure_class_coverage": dict(sorted(Counter(c for r in refs for c in r["acceptable_failure_classes"]).items())),
        "partition": {"calibration_cases": len(calibration), "held_out_verification_cases": len(held), "quarantine_cases": len(rows("quarantine/cases.jsonl"))},
    })
    summary = ["# Benchmark authoring analyses", "", f"- Independent scenarios: **{len(pairs)}**; answer cases: **{len(cases)}**.", f"- Estimated independent semantic templates: **{len(pairs)}**.", f"- Question families: **{len(family)}**; reasoning structures: **{len(structures)}**; failure mechanisms: **{len(mechanisms)}**.", f"- Transcript coverage: **{len(cited_docs)}/{corpus['transcript_count']}**; cited dates span **{min(cited_dates)} to {max(cited_dates)}**.", f"- Pair symmetry: **{symmetry['result']}**; mean length delta **{statistics.mean(deltas):.2f} words**.", f"- Evidence-withheld leakage: **{leakage['result']}**; bag-of-words accuracy **{controls['leave_one_scenario_out_bag_of_words_naive_bayes_accuracy']:.3f}**.", "", "Outputs are aggregate and do not reveal held-out case payloads."]
    (ROOT / "analysis/README.md").write_text("\n".join(summary) + "\n")
    print(json.dumps({"result": leakage["result"], "scenarios":len(pairs), "cases":len(cases), "bow_accuracy":controls["leave_one_scenario_out_bag_of_words_naive_bayes_accuracy"]}, sort_keys=True))


if __name__ == "__main__": main()
