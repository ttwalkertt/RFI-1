#!/usr/bin/env python3
"""Validate the imported governing design baseline and repository boundaries."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "design-baseline.json"


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    """Verify imported files, recorded hashes, structure, and the product-code boundary."""
    errors: list[str] = []
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    documents = data.get("documents", [])
    if len(documents) != 8:
        errors.append(f"expected 8 design documents, found {len(documents)}")
    for document in documents:
        destination = ROOT / document["destination"]
        if not destination.is_file():
            errors.append(f"missing design document: {document['destination']}")
            continue
        digest = sha256(destination)
        if digest != document["destination_sha256"]:
            errors.append(
                f"destination hash mismatch: {document['destination']} "
                f"expected {document['destination_sha256']} got {digest}"
            )
        size = destination.stat().st_size
        if size != document["destination_size"]:
            errors.append(
                f"destination size mismatch: {document['destination']} "
                f"expected {document['destination_size']} got {size}"
            )
        unchanged = document["content_change"] == "none"
        if unchanged and document["source_sha256"] != document["destination_sha256"]:
            errors.append(f"unchanged document has unequal hashes: {document['destination']}")
    required_paths = (
        "src/rfi/__init__.py",
        "tests/test_foundation.py",
        "docs/development.md",
        "fixtures/README.md",
        "data/README.md",
        "scripts/generate_review_package.py",
    )
    for required in required_paths:
        if not (ROOT / required).is_file():
            errors.append(f"missing repository boundary: {required}")
    product_files = sorted(
        path.relative_to(ROOT / "src" / "rfi").as_posix()
        for path in (ROOT / "src" / "rfi").rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.name != ".DS_Store"
    )
    expected_product_files = [
        "__init__.py",
        "__main__.py",
        "acquisition/__init__.py",
        "acquisition/contracts.py",
        "acquisition/demo.py",
        "acquisition/direct_url.py",
        "acquisition/edgar.py",
        "acquisition/engine.py",
        "acquisition/fixture_adapters.py",
        "acquisition/persistence.py",
        "acquisition/repository.py",
        "acquisition/runtime_config.py",
        "acquisition/sec_api.py",
        "acquisition/sec_form_10k.py",
        "acquisition/sec_form_10q.py",
        "acquisition/sec_form_20f.py",
        "acquisition/sec_form_6k.py",
        "acquisition/sec_form_8k.py",
        "acquisition/sec_numbered_form.py",
        "acquisition/sec_provider.py",
        "admin/__init__.py",
        "admin/admin_preferences.js",
        "admin/artifact_browser.html",
        "admin/console.html",
        "admin/field_definitions.py",
        "admin/firms.html",
        "admin/pull_sources.html",
        "admin/server.py",
        "admin/source_profiles.html",
        "artifacts/__init__.py",
        "artifacts/contracts.py",
        "artifacts/service.py",
        "catalog_import.py",
        "cli.py",
        "concepts/__init__.py",
        "concepts/contracts.py",
        "concepts/derivation.py",
        "concepts/repository.py",
        "concepts/samples.py",
        "concepts/service.py",
        "firms/__init__.py",
        "firms/contracts.py",
        "firms/repository.py",
        "firms/samples.py",
        "firms/service.py",
        "intelligence/__init__.py",
        "intelligence/contracts.py",
        "intelligence/deterministic.py",
        "intelligence/inspection.py",
        "intelligence/orchestration.py",
        "knowledge/__init__.py",
        "knowledge/contracts.py",
        "knowledge/derivation.py",
        "knowledge/repository.py",
        "mailing_lists/__init__.py",
        "mailing_lists/contracts.py",
        "mailing_lists/parser.py",
        "mailing_lists/provider.py",
        "mailing_lists/repository.py",
        "mailing_lists/service.py",
        "pull/__init__.py",
        "pull/adapters.py",
        "pull/contracts.py",
        "pull/planning.py",
        "pull/repository.py",
        "pull/workflow.py",
        "py.typed",
        "resources/source-profile-template.yaml",
        "retrieval/__init__.py",
        "retrieval/contracts.py",
        "retrieval/evidence.py",
        "retrieval/replaceability.py",
        "retrieval/repository.py",
        "retrieval/vector.py",
        "source_objects/__init__.py",
        "source_objects/contracts.py",
        "source_objects/parser.py",
        "source_objects/repository.py",
        "source_profiles/__init__.py",
        "source_profiles/contracts.py",
        "source_profiles/repository.py",
        "source_profiles/service.py",
        "source_profiles/template.py",
        "storage/__init__.py",
        "storage/backup.py",
        "storage/sqlite.py",
        "workspace/__init__.py",
        "workspace/contracts.py",
        "workspace/repository.py",
        "workspace/service.py",
    ]
    if product_files != expected_product_files:
        errors.append(f"unexpected product implementation files: {product_files}")
    print(f"design documents checked: {len(documents)}")
    print(f"repository boundaries checked: {len(required_paths)}")
    print(f"product package files: {', '.join(product_files)}")
    if errors:
        print("result: FAIL")
        print("\n".join(errors))
        return 1
    print("result: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
