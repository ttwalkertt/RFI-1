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
from tests.test_task069 import Transport, configured_state, policies  # noqa: E402


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
    command = [
        "pull", "--state", str(state), "--firm", "oracle",
        "--selection", "first_in_date_range",
        "--start-date", "2026-03-10", "--end-date", "2026-06-15",
    ]
    display = (
        "rfi pull --state STATE --firm oracle --selection first_in_date_range "
        "--start-date 2026-03-10 --end-date 2026-06-15"
    )
    with patch("rfi.cli._open_state"), patch(
        "rfi.cli.create_pull_workflow", return_value=workflow
    ):
        first_code, first_stdout, first_stderr = invoke(command)
        second_code, second_stdout, second_stderr = invoke(command)
    first = json.loads(first_stdout)
    second = json.loads(second_stdout)
    successes = tuple(
        item for item in repository.history() if item.get("outcome") == "success"
    )
    checkpoint = next(iter(repository.checkpoints()["sources"].values()))
    repeated = {
        "command": display,
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
        "retained_artifact_ids": [item["artifact_id"] for item in successes],
        "checkpoint": checkpoint,
        "same_command_advanced": (
            selected_date(first) == "2026-03-10"
            and selected_date(second) == "2026-06-15"
            and len({item["artifact_id"] for item in successes}) == 2
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
        or second_code != 0
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
