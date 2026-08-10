#!/usr/bin/env python3
"""Run the five bounded TASK-073 Codex Work investigations through local RFI MCP."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "sentiment": (
        "How has management sentiment about the business outlook changed across the retained "
        "earnings calls, and what transcript evidence supports that assessment?"
    ),
    "demand": (
        "How did management’s characterization of cloud and nearline demand, customer behavior, "
        "and supply constraints change from late 2024 through the latest retained calls?"
    ),
    "technology": (
        "How did management describe HAMR and Mozaic qualification, launch timing, and "
        "production progress across the retained calls?"
    ),
    "chronology": (
        "When did the retained transcripts first and most recently discuss 40-terabyte products, "
        "and how did the discussion change?"
    ),
    "insufficient": (
        "What did CEO Dave Mosley say about employee attrition by geography across the retained "
        "calls?"
    ),
}
ORIENTATION = (
    "RFI is the retained-evidence source for this task. Answer this research question using only "
    "RFI retained evidence:"
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def state_fingerprint(state: Path) -> dict[str, Any]:
    """Fingerprint retained authority without exposing content paths in MCP responses."""
    database = state / "repository.sqlite3"
    content = state / "content/sha256"
    files = sorted(path for path in content.rglob("*") if path.is_file())
    return {
        "database_sha256": digest(database),
        "database_bytes": database.stat().st_size,
        "content_files": len(files),
        "content_manifest_sha256": hashlib.sha256(
            "\n".join(
                f"{path.name}:{digest(path)}:{path.stat().st_size}" for path in files
            ).encode()
        ).hexdigest(),
    }


def run_case(
    case: str,
    question: str,
    *,
    state: Path,
    output: Path,
    model: str | None,
) -> dict[str, Any]:
    """Run one unfamiliar Codex process with only the RFI MCP server configured."""
    prompt = f"{ORIENTATION}\n\n{question}"
    events = output / "codex" / f"{case}.jsonl"
    final = output / "answers" / f"{case}.md"
    access_trace = output / "mcp" / f"{case}.jsonl"
    for parent in (events.parent, final.parent, access_trace.parent):
        parent.mkdir(parents=True, exist_ok=True)
    server_args = [
        "-m",
        "rfi.mcp.server",
        "--state",
        str(state),
        "--trace",
        str(access_trace),
    ]
    command = [
        "codex",
        "exec",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--json",
        "--output-last-message",
        str(final),
        "-c",
        f"mcp_servers.rfi.command={json.dumps(str(ROOT / '.venv/bin/python'))}",
        "-c",
        f"mcp_servers.rfi.args={json.dumps(server_args)}",
        "-c",
        f"mcp_servers.rfi.cwd={json.dumps(str(ROOT))}",
        "-c",
        f"mcp_servers.rfi.env={{PYTHONPATH={json.dumps(str(ROOT / 'src'))}}}",
        "-c",
        "mcp_servers.rfi.required=true",
        "-c",
        "mcp_servers.rfi.startup_timeout_sec=60",
        "-c",
        "mcp_servers.rfi.tool_timeout_sec=60",
        "-c",
        'mcp_servers.rfi.default_tools_approval_mode="auto"',
    ]
    if model:
        command.extend(("--model", model))
    started = datetime.now(UTC)
    with tempfile.TemporaryDirectory(prefix=f"task073-{case}-") as workspace:
        command.extend(("--cd", workspace, prompt))
        with events.open("w", encoding="utf-8") as stream:
            result = subprocess.run(
                command,
                cwd=ROOT,
                env=os.environ,
                stdout=stream,
                stderr=subprocess.PIPE,
                text=True,
                timeout=1800,
                check=False,
            )
    ended = datetime.now(UTC)
    stderr_path = output / "codex" / f"{case}.stderr.txt"
    stderr_path.write_text(result.stderr, encoding="utf-8")
    return {
        "case": case,
        "question": question,
        "prompt": prompt,
        "orientation": ORIENTATION,
        "command": command[:-1] + ["<PROMPT RECORDED ABOVE>"],
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "duration_seconds": round((ended - started).total_seconds(), 3),
        "exit_code": result.returncode,
        "events": str(events.relative_to(output)),
        "answer": str(final.relative_to(output)),
        "mcp_trace": str(access_trace.relative_to(output)),
        "stderr": str(stderr_path.relative_to(output)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model")
    parser.add_argument("--case", choices=tuple(CASES), action="append")
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=True)
    version = subprocess.run(
        ["codex", "--version"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    ).stdout.strip()
    before = state_fingerprint(arguments.state)
    selected = arguments.case or list(CASES)
    results = [
        run_case(
            case,
            CASES[case],
            state=arguments.state,
            output=arguments.output,
            model=arguments.model,
        )
        for case in selected
    ]
    after = state_fingerprint(arguments.state)
    manifest = {
        "experiment_version": "task073.codex-work.v1",
        "codex_version": version,
        "model_override": arguments.model,
        "source_policy": "RFI retained evidence only; no internet or external transcript files",
        "rfi_specific_prompt_material": ORIENTATION,
        "procedural_prompt_material": None,
        "repository_before": before,
        "repository_after": after,
        "repository_unchanged": before == after,
        "cases": results,
    }
    (arguments.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if before == after and all(item["exit_code"] == 0 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
