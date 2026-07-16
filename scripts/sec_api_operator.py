#!/usr/bin/env python3
"""Explicit offline-scope and gated live SEC-API.io operator workflow."""

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
from rfi.acquisition.engine import (  # noqa: E402
    AcquisitionEngine,
    AcquisitionKernel,
    AdapterRegistry,
)
from rfi.acquisition.repository import AcquisitionRepository  # noqa: E402
from rfi.acquisition.runtime_config import load_runtime_configuration  # noqa: E402
from rfi.acquisition.sec_api import (  # noqa: E402
    ENVIRONMENT_VARIABLE,
    SecApiAdapter,
    credential_from_environment,
    load_live_profiles,
)


def render(value: Any) -> None:
    """Print deterministic sanitized JSON."""
    print(json.dumps(value, indent=2, sort_keys=True))


def scope() -> dict[str, Any]:
    """Describe the immutable live boundary without resolving a credential or using network."""
    profiles = load_live_profiles(ROOT)
    return {
        "mode": "offline-no-network",
        "provider": "SEC-API.io",
        "mechanism": "sec-api-io",
        "credential_reference": f"env:{ENVIRONMENT_VARIABLE}",
        "credential_value_in_profile": False,
        "profiles": [profile.to_dict() for profile in profiles],
        "maximum_filings_per_issuer": 5,
        "maximum_filings_complete_corpus": 10,
        "live_operations_are_quota_consuming": True,
    }


def inventory(repository: AcquisitionRepository) -> dict[str, Any]:
    """Return identity and checksum inventory without emitting filing bytes."""
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
    """Run an offline inspection or an explicitly gated quota-consuming operation."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=("scope", "live-config", "run-source", "run-all", "inventory", "usage"),
    )
    parser.add_argument("--state", type=Path)
    parser.add_argument("--source", choices=("source-sec-stx", "source-sec-wdc"))
    parser.add_argument("--run-key", default="live")
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Perform one quota-consuming provider discovery request during live-config",
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
    if arguments.state is None and arguments.command in {"run-source", "run-all"}:
        parser.error("--state is required for live acquisition")
    profiles = load_live_profiles(ROOT)
    try:
        runtime = load_runtime_configuration(
            ROOT, allow_local=not arguments.no_local_config
        )
        reference = str(profiles[0].configuration["credential_reference"])
        api_key = credential_from_environment(reference, runtime)
    except ContractError as error:
        render(
            {
                "result": "BLOCKED",
                "provider": "SEC-API.io",
                "credential_reference": f"env:{ENVIRONMENT_VARIABLE}",
                "credential_present": False,
                "network_requests": 0,
                "message": str(error),
            }
        )
        return 2
    adapter = SecApiAdapter(api_key)
    if arguments.command == "live-config":
        result: dict[str, Any] = {
            "result": "PASS",
            "provider": "SEC-API.io",
            "credential_reference": f"env:{ENVIRONMENT_VARIABLE}",
            "credential_present": True,
            "credential_value_emitted": False,
            "probe_performed": arguments.probe,
        }
        if arguments.probe:
            page = adapter.discover(profiles[0], None)
            result["probe"] = {
                "returned": len(page.candidates),
                "next_token_present": bool(page.next_token),
            }
        result["usage"] = adapter.usage()
        render(result)
        return 0
    if arguments.command == "usage":
        render(adapter.usage())
        return 0
    assert arguments.state is not None
    repository = AcquisitionRepository(arguments.state)
    for profile in profiles:
        repository.register_source(profile)
    registry = AdapterRegistry((adapter,))
    clock = lambda: datetime.now(UTC).isoformat()
    engine = AcquisitionEngine(repository, registry, clock)
    if arguments.command == "run-source":
        if arguments.source is None:
            parser.error("--source is required for run-source")
        runs = [engine.run_source(arguments.source, arguments.run_key).to_dict()]
    else:
        results = AcquisitionKernel(engine, repository).run_enabled(arguments.run_key)
        runs = [item.to_dict() for item in results]
    render({"runs": runs, "usage": adapter.usage(), "inventory": inventory(repository)})
    return 0 if all(item["status"] == "complete" for item in runs) else 1


if __name__ == "__main__":
    sys.exit(main())
