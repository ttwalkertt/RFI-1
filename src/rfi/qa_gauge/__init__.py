"""TASK-075 reference-truth QA gauge experiment."""

from rfi.qa_gauge.benchmark import BenchmarkCorpus, prepare_control_manifests
from rfi.qa_gauge.contracts import (
    DEFECT_CLASSES,
    GAUGE_SCHEMA_VERSION,
    GaugeFinding,
    GaugeReview,
    gauge_output_schema,
    parse_gauge_review,
)
from rfi.qa_gauge.scoring import consensus_review, score_partition

__all__ = [
    "BenchmarkCorpus",
    "DEFECT_CLASSES",
    "GAUGE_SCHEMA_VERSION",
    "GaugeFinding",
    "GaugeReview",
    "consensus_review",
    "gauge_output_schema",
    "parse_gauge_review",
    "prepare_control_manifests",
    "score_partition",
]
