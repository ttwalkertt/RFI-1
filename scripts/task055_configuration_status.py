#!/usr/bin/env python3
"""Produce reproducible TASK-055 configuration-status evidence."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from rfi.cli import initialize
from rfi.firm_configuration import inspect_firm_configuration_status, prepare_firm_configuration

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "docs/microsoft.firm-config.example.json"


def status(state: Path) -> dict[str, object]:
    value = inspect_firm_configuration_status(state)
    return {
        "status": value.status,
        "fingerprints_match": value.imported_fingerprint == value.external_fingerprint,
        "imported_fingerprint": value.imported_fingerprint,
        "external_fingerprint": value.external_fingerprint,
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        state = Path(temporary) / "state"
        directory = state / "firm-config"
        directory.mkdir(parents=True)
        path = directory / "microsoft.firm-config.json"
        path.write_bytes(EXAMPLE.read_bytes())
        initialize(state)
        current = status(state)
        stat = path.stat()
        os.utime(path, (stat.st_atime + 60, stat.st_mtime + 60))
        timestamp_only = status(state)
        path.write_bytes(path.read_bytes() + b"\n")
        changed = status(state)
        prepare_firm_configuration(state)
        reloaded = status(state)
        proof = {
            "current": current,
            "timestamp_only": timestamp_only,
            "byte_change": changed,
            "after_reload": reloaded,
            "timestamp_ignored": (
                current["external_fingerprint"] == timestamp_only["external_fingerprint"]
            ),
        }
        print(json.dumps(proof, indent=2, sort_keys=True))
        assert current["status"] == "current"
        assert timestamp_only["status"] == "current"
        assert changed["status"] == "changes_available"
        assert reloaded["status"] == "current"
        assert proof["timestamp_ignored"] is True
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
