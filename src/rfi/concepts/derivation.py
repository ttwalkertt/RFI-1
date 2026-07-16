"""Typed deterministic observation derivation independent of catalog persistence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from typing import Any

from rfi.concepts.contracts import (
    CalculationError,
    ConceptRevision,
    LineageReference,
    MethodKind,
    Observation,
    ObservationMethod,
    ObservationOrigin,
    Reconciliation,
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def _identifier(prefix: str, value: Any) -> str:
    return f"{prefix}-{hashlib.sha256(_canonical(value)).hexdigest()}"


class ObservationService:
    """Create typed observations and evaluate a deliberately small operation contract."""

    def observe(
        self,
        concept: ConceptRevision,
        method_id: str,
        value: Any,
        *,
        origin: ObservationOrigin = ObservationOrigin.EXTRACTED,
        unit: str | None = None,
        dimensions: dict[str, str] | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
        effective_at: str | None = None,
        scope: str | None = None,
        provenance: tuple[dict[str, Any], ...] = (),
        confidence: float | None = None,
    ) -> Observation:
        """Create an observation pinned to exact concept and method revisions."""
        method = self._method(concept, method_id)
        if origin == ObservationOrigin.CALCULATED:
            raise CalculationError("calculated observations must use deterministic evaluation")
        if method.units and unit not in method.units:
            raise CalculationError(f"unit {unit!r} is not admissible for {method_id}")
        if confidence is not None and not 0.0 <= confidence <= 1.0:
            raise CalculationError("confidence must be between zero and one")
        material = {
            "concept_id": concept.concept_id,
            "concept_revision_id": concept.revision_id,
            "method_id": method_id,
            "origin": origin,
            "result_shape": method.result_shape,
            "value": value,
            "unit": unit,
            "dimensions": dimensions or {},
            "period_start": period_start,
            "period_end": period_end,
            "effective_at": effective_at,
            "scope": scope,
            "provenance": provenance,
            "confidence": confidence,
        }
        return Observation(
            observation_id=_identifier("observation", material),
            lineage=(),
            warnings=(),
            **material,
        )

    def calculate(
        self,
        concept: ConceptRevision,
        method_id: str,
        inputs: dict[str, Observation],
    ) -> Observation:
        """Evaluate deterministic inputs with checks and preserved exact lineage."""
        method = self._method(concept, method_id)
        if method.kind != MethodKind.DETERMINISTIC:
            raise CalculationError(f"method is not deterministic: {method_id}")
        specification = method.configuration
        declared = specification["inputs"]
        required_roles = {item["role"] for item in declared if item.get("required", True)}
        missing = required_roles - set(inputs)
        if missing:
            raise CalculationError("missing required inputs: " + ", ".join(sorted(missing)))
        unexpected = set(inputs) - {item["role"] for item in declared}
        if unexpected:
            raise CalculationError("unknown calculation inputs: " + ", ".join(sorted(unexpected)))
        used = {role: inputs[role] for role in inputs}
        self._check_inputs(declared, used, method)
        values = {role: self._decimal(item.value, role) for role, item in used.items()}
        result = self._evaluate(specification["operation"], values, specification)
        output_unit = specification.get("output_unit")
        output_value: int | float = float(result)
        if method.result_shape == "integer":
            output_value = int(result)
        lineage = tuple(
            LineageReference(
                observation_id=item.observation_id,
                concept_id=item.concept_id,
                concept_revision_id=item.concept_revision_id,
                method_id=item.method_id,
                role=role,
            )
            for role, item in sorted(used.items())
        )
        first = next(iter(used.values()))
        material = {
            "concept_id": concept.concept_id,
            "concept_revision_id": concept.revision_id,
            "method_id": method.method_id,
            "origin": ObservationOrigin.CALCULATED,
            "result_shape": method.result_shape,
            "value": output_value,
            "unit": output_unit,
            "dimensions": first.dimensions,
            "period_start": first.period_start,
            "period_end": first.period_end,
            "effective_at": first.effective_at,
            "scope": first.scope,
            "provenance": tuple(
                {
                    "kind": "deterministic-derivation",
                    "method_id": method.method_id,
                    "concept_revision_id": concept.revision_id,
                    "input_observation_ids": [item.observation_id for item in used.values()],
                },
            ),
            "lineage": lineage,
        }
        return Observation(
            observation_id=_identifier("observation", material),
            confidence=None,
            warnings=method.warnings,
            **material,
        )

    def reconcile(
        self,
        left: Observation,
        right: Observation,
        tolerance: float,
    ) -> Reconciliation:
        """Compare observations without selecting, merging, or overwriting either one."""
        if left.concept_id != right.concept_id:
            raise CalculationError("only observations of the same concept can be compared")
        if left.unit != right.unit:
            raise CalculationError("reconciliation requires compatible units")
        if (left.period_start, left.period_end) != (right.period_start, right.period_end):
            raise CalculationError("reconciliation requires compatible periods")
        difference = abs(float(self._decimal(left.value, "left")) - float(
            self._decimal(right.value, "right")
        ))
        return Reconciliation(
            left_observation_id=left.observation_id,
            right_observation_id=right.observation_id,
            absolute_difference=difference,
            within_tolerance=difference <= tolerance,
            tolerance=tolerance,
            unit=left.unit,
        )

    def _method(self, concept: ConceptRevision, method_id: str) -> ObservationMethod:
        for method in concept.methods:
            if method.method_id == method_id:
                return method
        raise CalculationError(f"unknown method for concept revision: {method_id}")

    def _check_inputs(
        self,
        declared: list[dict[str, Any]],
        inputs: dict[str, Observation],
        method: ObservationMethod,
    ) -> None:
        periods = {(item.period_start, item.period_end) for item in inputs.values()}
        if method.period_expectation and len(periods) > 1:
            raise CalculationError("incompatible input periods")
        scopes = {item.scope for item in inputs.values()}
        if method.scope_expectation and len(scopes) > 1:
            raise CalculationError("incompatible input scopes")
        dimensions = {tuple(sorted(item.dimensions.items())) for item in inputs.values()}
        if len(dimensions) > 1:
            raise CalculationError("incompatible input dimensions")
        for specification in declared:
            role = specification["role"]
            if role not in inputs:
                continue
            item = inputs[role]
            if item.concept_id != specification["concept_id"]:
                raise CalculationError(f"input concept mismatch for role: {role}")
            expected_unit = specification.get("unit")
            if expected_unit and item.unit != expected_unit:
                raise CalculationError(f"incompatible input unit for role: {role}")

    def _evaluate(
        self,
        operation: str,
        values: dict[str, Decimal],
        configuration: dict[str, Any],
    ) -> Decimal:
        roles = [item["role"] for item in configuration["inputs"] if item["role"] in values]
        try:
            if operation == "add":
                return sum((values[role] for role in roles), Decimal(0))
            if operation == "subtract":
                return values[roles[0]] - values[roles[1]]
            if operation == "multiply":
                result = Decimal(1)
                for role in roles:
                    result *= values[role]
                return result
            if operation in {"divide", "percentage"}:
                result = values[roles[0]] / values[roles[1]]
                return result * Decimal(100) if operation == "percentage" else result
            if operation == "margin-from-cost":
                revenue = values["revenue"]
                return (revenue - values["cost_of_revenue"]) / revenue * Decimal(100)
        except (ArithmeticError, IndexError) as error:
            raise CalculationError(f"calculation failure: {error}") from error
        raise CalculationError(f"unsupported deterministic operation: {operation}")

    def _decimal(self, value: Any, role: str) -> Decimal:
        if isinstance(value, bool):
            raise CalculationError(f"nonnumeric calculation input: {role}")
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError) as error:
            raise CalculationError(f"nonnumeric calculation input: {role}") from error
