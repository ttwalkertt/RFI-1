#!/usr/bin/env python3
"""Generate deterministic TASK-069 CLI and repeated-pull review evidence."""

from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from rfi.cli import main  # noqa: E402
from rfi.discovery import EarningsTranscriptPullAdapter  # noqa: E402
from rfi.pull import (  # noqa: E402
    PullRunRepository,
    PullWorkflow,
    RetrievalAdapterCapability,
    RetrievalAdapterRegistration,
    RetrievalAdapterRegistry,
)
from tests.test_task069 import (  # noqa: E402
    Q4_URL,
    Transport,
    configured_state,
    policies,
)


class Ids:
    """Stable run identities for human-readable fixture evidence."""

    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"review{self.value:04d}"


def selected_date(result: dict[str, object]) -> str:
    firms = result["firms"]
    assert isinstance(firms, list)
    artifacts = firms[0]["artifacts"]
    attempts = artifacts[0]["attempts"]
    diagnostics = attempts[0]["details"]["engine_diagnostics"]
    terminal = next(
        item for item in diagnostics
        if item.get("terminal_selection_outcome") == "selected"
    )
    return str(terminal["selected_validated_event_date"])


def engine_diagnostics(result: dict[str, object]) -> list[dict[str, object]]:
    firms = result["firms"]
    assert isinstance(firms, list)
    artifacts = firms[0]["artifacts"]
    attempts = artifacts[0]["attempts"]
    return attempts[0]["details"]["engine_diagnostics"]


def invoke(arguments: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            code = main(arguments)
        except SystemExit as error:
            code = int(error.code)
    return code, stdout.getvalue(), stderr.getvalue()


def generate(output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    state = output / "evidence-state"
    if state.exists():
        shutil.rmtree(state)
    firms, profiles, template, repository = configured_state(state)
    transport = Transport()
    adapter = EarningsTranscriptPullAdapter(
        policies(),
        transport=transport,
        repository=repository,
        clock=lambda: "2026-08-07T12:00:00+00:00",
    )
    workflow = PullWorkflow(
        firms,
        profiles,
        template,  # type: ignore[arg-type]
        repository,
        RetrievalAdapterRegistry((RetrievalAdapterRegistration(
            RetrievalAdapterCapability(
                adapter.adapter_id, adapter.artifact_ids, adapter.retrieval_modes
            ),
            adapter,
        ),)),
        PullRunRepository(state / "pull-workflows"),
        lambda: "2026-08-07T12:00:00+00:00",
        Ids(),
    )
    latest_command = ["pull", "--state", str(state), "--firm", "oracle"]
    command = [
        "pull", "--state", str(state), "--firm", "oracle",
        "--selection", "first_in_date_range",
        "--start-date", "2025-06-03", "--end-date", "2026-06-15",
    ]
    display = (
        "rfi pull --state STATE --firm oracle --selection first_in_date_range "
        "--start-date 2025-06-03 --end-date 2026-06-15"
    )
    with patch("rfi.cli._open_state"), patch(
        "rfi.cli.create_pull_workflow", return_value=workflow
    ):
        latest_code, latest_stdout, latest_stderr = invoke(latest_command)
        staged_successes = tuple(
            item for item in repository.history() if item.get("outcome") == "success"
        )
        if len(staged_successes) != 1:
            raise RuntimeError("default latest staging did not retain exactly one transcript")
        newest_success = staged_successes[0]
        first_code, first_stdout, first_stderr = invoke(command)
        second_code, second_stdout, second_stderr = invoke(command)
        third_code, third_stdout, third_stderr = invoke(command)
    latest = json.loads(latest_stdout)
    first = json.loads(first_stdout)
    second = json.loads(second_stdout)
    third = json.loads(third_stdout)
    successes = tuple(
        item for item in repository.history() if item.get("outcome") == "success"
    )
    checkpoint = next(iter(repository.checkpoints()["sources"].values()))
    direct_trials = tuple(
        item
        for result in (first, second, third)
        for item in engine_diagnostics(result)
        if item.get("provider_surface") == "direct_document"
    )
    selected_dates = [selected_date(result) for result in (first, second, third)]
    repeated = {
        "command": display,
        "precondition": {
            "command": "rfi pull --state STATE --firm oracle",
            "exit_code": latest_code,
            "stderr": latest_stderr,
            "summary": latest["summary"],
            "retained_newest_trusted_event_date": newest_success["diagnostics"][
                "trusted_event_date"
            ],
        },
        "first": {
            "exit_code": first_code,
            "stderr": first_stderr,
            "selected_validated_event_date": selected_date(first),
            "summary": first["summary"],
        },
        "second": {
            "exit_code": second_code,
            "stderr": second_stderr,
            "selected_validated_event_date": selected_date(second),
            "summary": second["summary"],
        },
        "third": {
            "exit_code": third_code,
            "stderr": third_stderr,
            "selected_validated_event_date": selected_date(third),
            "summary": third["summary"],
        },
        "retained_artifact_ids": [item["artifact_id"] for item in successes],
        "checkpoint": checkpoint,
        "learned_direct_document": {
            "trial_count": len(direct_trials),
            "candidate_evaluated_counts": [
                item["candidate_evaluated_count"] for item in direct_trials
            ],
            "newest_document_http_request_count": transport.requests.count(Q4_URL),
            "conclusion": (
                "learned direct-document occurrences were deduplicated before "
                "retrieval; the newest transcript was fetched only during staging"
            ),
        },
        "same_command_advanced": (
            latest_code == 0
            and latest_stderr == ""
            and latest["summary"]["success"] == 1
            and newest_success["diagnostics"]["trusted_event_date"] == "2026-06-15"
            and selected_dates == ["2025-06-03", "2025-09-08", "2025-12-09"]
            and len({item["artifact_id"] for item in successes}) == 4
            and transport.requests.count(Q4_URL) == 1
            and bool(direct_trials)
            and all(item["candidate_evaluated_count"] == 0 for item in direct_trials)
        ),
    }
    (output / "successful-cli.txt").write_text(
        f"$ {display}\n\n{first_stdout}\nexit_code: {first_code}\n",
        encoding="utf-8",
    )
    (output / "repeated-pulls.json").write_text(
        json.dumps(repeated, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    invalid_commands = (
        ["pull", "--firm", "oracle", "--selection", "first_in_date_range"],
        [
            "pull", "--firm", "oracle", "--selection", "first_in_date_range",
            "--start-date", "2026-08-08", "--end-date", "2026-08-07",
        ],
        [
            "pull", "--firm", "oracle", "--selection", "first_in_date_range",
            "--start-date", "not-a-date", "--end-date", "2026-08-07",
        ],
        ["pull", "--firm", "oracle", "--selection", "unsupported"],
        [
            "pull", "--firm", "oracle", "--selection", "latest",
            "--start-date", "2026-01-01", "--end-date", "2026-08-07",
        ],
    )
    failures = []
    with patch("rfi.cli.pull_sources") as acquisition:
        for arguments in invalid_commands:
            code, stdout, stderr = invoke(list(arguments))
            failures.append({
                "command": "rfi " + " ".join(arguments),
                "exit_code": code,
                "stdout": stdout,
                "stderr": stderr,
            })
        acquisition_not_called = acquisition.call_count == 0
    validation = {
        "failures": failures,
        "all_failed_before_acquisition": (
            acquisition_not_called
            and all(item["exit_code"] == 2 for item in failures)
        ),
    }
    (output / "validation-failures.json").write_text(
        json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result = {
        "successful_cli_exit_code": first_code,
        "repeated_pull": repeated,
        "validation": validation,
    }
    if (
        first_code != 0
        or latest_code != 0
        or second_code != 0
        or third_code != 0
        or not repeated["same_command_advanced"]
        or not validation["all_failed_before_acquisition"]
    ):
        raise RuntimeError("TASK-069 deterministic review evidence failed")
    return result


def main_entry() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".artifacts/task069-validation"
    )
    arguments = parser.parse_args()
    print(json.dumps(generate(arguments.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main_entry())
