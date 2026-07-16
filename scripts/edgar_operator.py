#!/usr/bin/env python3
"""Offline scope inspection and explicitly gated native EDGAR acquisition workflow."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
    AdapterFailure,
    AdapterRegistry,
)
from rfi.acquisition.repository import AcquisitionRepository  # noqa: E402
from rfi.acquisition.runtime_config import load_runtime_configuration  # noqa: E402


def render(value: Any) -> None:
    """Print stable JSON that never contains the runtime User-Agent value."""
    print(json.dumps(value, indent=2, sort_keys=True))


def scope() -> dict[str, Any]:
    """Describe the bounded corpus without resolving operator identity or using network."""
    profiles = load_edgar_profiles(ROOT)
    return {
        "mode": "offline-no-network",
        "provider": "SEC EDGAR",
        "mechanism": "sec-edgar",
        "runtime_identity_reference": f"env:{USER_AGENT_VARIABLE}",
        "runtime_identity_value_in_profile": False,
        "profiles": [profile.to_dict() for profile in profiles],
        "maximum_filings_per_issuer": 5,
        "maximum_filings_complete_corpus": 10,
        "live_operations_use_official_sec_hosts": True,
    }


def inventory(repository: AcquisitionRepository) -> dict[str, Any]:
    """Return filing identities and checksums without exact filing content."""
    index = repository.document_index()
    artifacts = repository.artifact_metadata()
    return {
        "documents": len(index["documents"]),
        "artifacts": len(artifacts),
        "document_ids": sorted(index["documents"]),
        "artifact_checksums": {
            item["artifact_id"]: item["sha256"] for item in artifacts
        },
        "integrity": repository.verify_integrity(),
    }


def main() -> int:
    """Run one native EDGAR operator command."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=("scope", "live-config", "run-source", "run-all", "inventory"),
    )
    parser.add_argument("--state", type=Path)
    parser.add_argument("--source", choices=("source-edgar-stx", "source-edgar-wdc"))
    parser.add_argument("--run-key", default="live")
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Perform one paced official submissions request during configuration validation",
    )
    parser.add_argument(
        "--no-local-config",
        action="store_true",
        help="Ignore .rfi/runtime.env (used by offline validation and environment-only runs)",
    )
    arguments = parser.parse_args()
    if arguments.command == "scope":
        render(scope())
        return 0
    if arguments.command == "inventory":
        if arguments.state is None:
            parser.error("--state is required for inventory")
        render(inventory(AcquisitionRepository(arguments.state)))
        return 0
    if arguments.command in {"run-source", "run-all"} and arguments.state is None:
        parser.error("--state is required for native EDGAR acquisition")
    profiles = load_edgar_profiles(ROOT)
    try:
        runtime = load_runtime_configuration(
            ROOT, allow_local=not arguments.no_local_config
        )
        reference = str(profiles[0].configuration["user_agent_reference"])
        user_agent = user_agent_from_environment(reference, runtime)
    except ContractError as error:
        render(
            {
                "result": "BLOCKED",
                "provider": "SEC EDGAR",
                "runtime_identity_reference": f"env:{USER_AGENT_VARIABLE}",
                "runtime_identity_present": False,
                "runtime_identity_value_emitted": False,
                "network_requests": 0,
                "message": str(error),
            }
        )
        return 2
    adapter = EdgarAdapter(user_agent)
    if arguments.command == "live-config":
        result: dict[str, Any] = {
            "result": "PASS",
            "provider": "SEC EDGAR",
            "runtime_identity_reference": f"env:{USER_AGENT_VARIABLE}",
            "runtime_identity_present": True,
            "runtime_identity_value_emitted": False,
            "probe_performed": arguments.probe,
        }
        try:
            if arguments.probe:
                page = adapter.discover(profiles[0], None)
                result["probe"] = {
                    "returned": len(page.candidates),
                    "next_token_present": bool(page.next_token),
                }
        except AdapterFailure as error:
            result.update({"result": "FAIL", "message": str(error)})
            result["usage"] = adapter.usage()
            render(result)
            return 1
        result["usage"] = adapter.usage()
        render(result)
        return 0
    assert arguments.state is not None
    repository = AcquisitionRepository(arguments.state)
    for profile in profiles:
        repository.register_source(profile)
    engine = AcquisitionEngine(
        repository,
        AdapterRegistry((adapter,)),
        lambda: datetime.now(UTC).isoformat(),
    )
    if arguments.command == "run-source":
        if arguments.source is None:
            parser.error("--source is required for run-source")
        runs = [engine.run_source(arguments.source, arguments.run_key).to_dict()]
    else:
        results = AcquisitionKernel(engine, repository).run_enabled(arguments.run_key)
        runs = [result.to_dict() for result in results]
    render({"runs": runs, "usage": adapter.usage(), "inventory": inventory(repository)})
    return 0 if all(run["status"] == "complete" for run in runs) else 1


if __name__ == "__main__":
    sys.exit(main())
