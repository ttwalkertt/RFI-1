#!/usr/bin/env python3
"""Build and verify a deterministic TASK-001 source snapshot."""

from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".artifacts" / "build" / "rfi-1-source.zip"
EXCLUDED_PARTS = {
    ".artifacts",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
}


def source_files() -> list[Path]:
    """Return repository source files included in the bootstrap snapshot."""
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
        and not path.name.endswith((".pyc", ".pyo"))
    )


def digest(path: Path) -> str:
    """Return a file SHA-256 digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    """Create a deterministic ZIP with normalized metadata."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in source_files():
            relative = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def main() -> int:
    """Build the archive, verify CRCs, and report reproducible evidence."""
    build()
    with zipfile.ZipFile(OUTPUT) as archive:
        bad_member = archive.testzip()
        members = archive.namelist()
    if bad_member is not None:
        print(f"result: FAIL; corrupt member: {bad_member}")
        return 1
    print(f"archive: {OUTPUT.relative_to(ROOT)}")
    print(f"members: {len(members)}")
    print(f"bytes: {OUTPUT.stat().st_size}")
    print(f"sha256: {digest(OUTPUT)}")
    print("integrity: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
