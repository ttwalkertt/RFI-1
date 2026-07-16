"""Application service joining the workspace to the public intelligence executor port."""

from __future__ import annotations

from time import monotonic_ns
from typing import Any

from rfi.intelligence import InformationNeed, IntelligenceBudget

from rfi.workspace.contracts import IntelligenceExecutor, OperationalMetrics
from rfi.workspace.repository import WorkspaceRepository


class WorkspaceService:
    """Run and journal intelligence without importing any upstream storage implementation."""

    def __init__(self, repository: WorkspaceRepository, executor: IntelligenceExecutor) -> None:
        self.repository = repository
        self.executor = executor

    def execute(
        self,
        investigation_id: str,
        question: str,
        budget: IntelligenceBudget | None = None,
        configuration: dict[str, Any] | None = None,
        usage: dict[str, int | float | str | None] | None = None,
    ) -> str:
        """Journal intent, run TASK-007 through its port, and append terminal state."""
        config = {
            "budget": budget.__dict__ if budget else IntelligenceBudget().__dict__,
            **(configuration or {}),
        }
        execution_id = self.repository.begin_execution(
            investigation_id, question, configuration=config
        )
        started = monotonic_ns()
        try:
            record = self.executor.execute(InformationNeed(question), budget)
        except (Exception, KeyboardInterrupt) as error:
            elapsed = (monotonic_ns() - started) // 1_000_000
            self.repository.fail_execution(
                investigation_id,
                execution_id,
                f"executor failure: {type(error).__name__}: {error}",
                interrupted=isinstance(error, KeyboardInterrupt),
                metrics=OperationalMetrics(execution_ms=elapsed),
            )
            if isinstance(error, KeyboardInterrupt):
                raise
            return execution_id
        elapsed = (monotonic_ns() - started) // 1_000_000
        supplied = usage or {}
        metrics = OperationalMetrics(
            execution_ms=elapsed,
            planning_ms=self._optional_int(supplied.get("planning_ms")),
            retrieval_ms=self._optional_int(supplied.get("retrieval_ms")),
            model_ms=self._optional_int(supplied.get("model_ms")),
            evidence_bytes=sum(item.bytes_used for item in record.trace.evidence_packages),
            retrieval_count=len(record.trace.retrieval_queries),
            iteration_count=record.trace.iterations,
            model_calls=self._optional_int(supplied.get("model_calls")),
            input_tokens=self._optional_int(supplied.get("input_tokens")),
            output_tokens=self._optional_int(supplied.get("output_tokens")),
            estimated_cost=self._optional_float(supplied.get("estimated_cost")),
            cost_currency=(
                str(supplied["cost_currency"]) if supplied.get("cost_currency") else None
            ),
        )
        self.repository.complete_execution(investigation_id, execution_id, record, metrics)
        return execution_id

    @staticmethod
    def _optional_int(value: int | float | str | None) -> int | None:
        return int(value) if value is not None else None

    @staticmethod
    def _optional_float(value: int | float | str | None) -> float | None:
        return float(value) if value is not None else None
