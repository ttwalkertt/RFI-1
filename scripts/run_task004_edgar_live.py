#!/usr/bin/env python3
"""Run the complete bounded native EDGAR acceptance and preserve sanitized local evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rfi.acquisition.contracts import ContractError  # noqa: E402
from rfi.acquisition.edgar import (  # noqa: E402
    USER_AGENT_VARIABLE,
    EdgarAdapter,
    load_edgar_profiles,
    user_agent_from_environment,
)
from rfi.acquisition.engine import (  # noqa: E402
    AcquisitionEngine,
    AcquisitionKernel,
    AdapterRegistry,
)
from rfi.acquisition.repository import AcquisitionRepository  # noqa: E402
from rfi.acquisition.runtime_config import load_runtime_configuration  # noqa: E402


def write(path: Path, value: object) -> None:
    """Persist one sanitized evidence object under ignored review runtime state."""
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def inventory(repository: AcquisitionRepository) -> dict[str, object]:
    """Return exact live corpus identities, provenance, and checksums without filing bodies."""
    index = repository.document_index()
    metadata = repository.artifact_metadata()
    filings = []
    for document_id, document in sorted(index["documents"].items()):
        provenance = document["provenance"][0]
        discovery = provenance["discovery"]
        values = discovery["metadata"]
        filings.append(
            {
                "document_id": document_id,
                "artifact_ids": document["artifacts"],
                "source_ids": document["source_ids"],
                "accession_no": values["accession_no"],
                "issuer_cik": values["issuer_cik"],
                "issuer_ticker": values["issuer_ticker"],
                "form_type": values["form_type"],
                "filed_at": values["filed_at"],
                "accepted_at": values["accepted_at"],
                "archive_path": values["complete_submission_archive_path"],
            }
        )
    return {
        "filings": filings,
        "filing_count": len(filings),
        "document_count": len(index["documents"]),
        "artifact_count": len(metadata),
        "artifact_checksums": {
            item["artifact_id"]: item["sha256"] for item in metadata
        },
    }


def main() -> int:
    """Execute first run, equivalent rerun, network-blocked replay, rebuild, and integrity."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--state",
        type=Path,
        default=ROOT / ".artifacts/runtime/TASK-004-edgar",
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        default=ROOT / ".artifacts/runtime/TASK-004-edgar-evidence",
    )
    parser.add_argument(
        "--no-local-config",
        action="store_true",
        help="Ignore .rfi/runtime.env and require the process environment",
    )
    arguments = parser.parse_args()
    if arguments.state.exists() or arguments.evidence.exists():
        print(
            json.dumps(
                {
                    "result": "BLOCKED",
                    "message": (
                        "live state or evidence path already exists; refusing ambiguous reuse"
                    ),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    profiles = load_edgar_profiles(ROOT)
    try:
        runtime = load_runtime_configuration(
            ROOT, allow_local=not arguments.no_local_config
        )
        reference = str(profiles[0].configuration["user_agent_reference"])
        user_agent = user_agent_from_environment(reference, runtime)
    except ContractError as error:
        print(
            json.dumps(
                {
                    "result": "BLOCKED",
                    "runtime_identity_reference": f"env:{USER_AGENT_VARIABLE}",
                    "runtime_identity_present": False,
                    "network_requests": 0,
                    "message": str(error),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    arguments.evidence.mkdir(parents=True)
    repository = AcquisitionRepository(arguments.state)
    for profile in profiles:
        repository.register_source(profile)
    adapter = EdgarAdapter(user_agent)
    engine = AcquisitionEngine(
        repository,
        AdapterRegistry((adapter,)),
        lambda: datetime.now(UTC).isoformat(),
    )
    kernel = AcquisitionKernel(engine, repository)
    first = kernel.run_enabled("native-live-first")
    first_usage = adapter.usage()
    first_inventory = inventory(repository)
    first_result = {
        "runs": [result.to_dict() for result in first],
        "usage": first_usage,
        "inventory": first_inventory,
    }
    write(arguments.evidence / "live-first-run.json", first_result)
    if not all(result.status.value == "complete" for result in first):
        print(json.dumps({"result": "FAIL", **first_result}, indent=2, sort_keys=True))
        return 1
    second = kernel.run_enabled("native-live-second")
    second_usage = adapter.usage()
    second_inventory = inventory(repository)
    second_result = {
        "runs": [result.to_dict() for result in second],
        "usage_cumulative": second_usage,
        "requests_second_run": int(second_usage["requests"]) - int(first_usage["requests"]),
        "inventory": second_inventory,
        "inventory_equal_to_first": second_inventory == first_inventory,
    }
    write(arguments.evidence / "live-second-run.json", second_result)
    os.environ.pop(USER_AGENT_VARIABLE, None)
    runtime.clear()
    del kernel, engine, adapter, user_agent
    integrity_before = repository.verify_integrity()
    repository.delete_derived_state()
    with patch("socket.socket", side_effect=AssertionError("network creation blocked")):
        replay = repository.replay()
        integrity_after = repository.verify_integrity()
    replay_result = {
        "runtime_identity_references_released_before_replay": True,
        "provider_adapter_disabled": True,
        "network_blocked": True,
        "replay": asdict(replay),
        "integrity_before": integrity_before,
        "integrity_after": integrity_after,
        "inventory": inventory(repository),
    }
    write(arguments.evidence / "provider-disabled-replay.json", replay_result)
    passed = (
        all(result.status.value == "complete" for result in second)
        and second_inventory == first_inventory
        and integrity_before["result"] == "PASS"
        and integrity_after["result"] == "PASS"
        and first_inventory["filing_count"] == 10
        and first_inventory["artifact_count"] == 10
    )
    summary = {
        "result": "PASS" if passed else "FAIL",
        "provider": "SEC EDGAR",
        "runtime_identity_value_emitted": False,
        "first": first_result,
        "second": second_result,
        "replay": replay_result,
    }
    write(arguments.evidence / "acceptance-summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
