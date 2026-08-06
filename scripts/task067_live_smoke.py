#!/usr/bin/env python3
"""Capture bounded diagnostic RSS and Atom validation without changing operator state."""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from rfi.feeds import FeedService
from rfi.storage import RepositoryDatabase

SOURCES = (
    ("rss", "NASA breaking news", "https://www.nasa.gov/rss/dyn/breaking_news.rss"),
    ("atom", "CPython commits", "https://github.com/python/cpython/commits/main.atom"),
)


def capture() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="rfi-task067-live-") as directory:
        state = Path(directory)
        RepositoryDatabase.initialize(state)
        service = FeedService(state)
        results = []
        for expected, name, url in SOURCES:
            validation = service.validate(url)
            results.append({
                "name": name, "url": url, "expected_format": expected,
                "valid": validation.valid, "observed_format": validation.format,
                "title": validation.title, "entry_count": validation.entry_count,
                "diagnostic": validation.diagnostic,
                "format_matches": validation.format == expected,
            })
    return {
        "captured_at": datetime.now(UTC).isoformat(),
        "bounded_validation_only": True,
        "sources": results,
        "passed": all(item["valid"] and item["format_matches"] for item in results),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        value = json.loads(args.verify.read_text(encoding="utf-8"))
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0 if isinstance(value.get("sources"), list) else 1
    value = capture()
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
