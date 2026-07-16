#!/usr/bin/env python3
"""Validate local Markdown links without network access."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LINK_PATTERN = re.compile(r"(?<!!)\[[^]]*]\(([^)]+)\)")


def markdown_files() -> list[Path]:
    """Return reviewable Markdown sources, excluding generated and environment directories."""
    excluded = {".artifacts", ".git", ".venv"}
    return sorted(
        path for path in ROOT.rglob("*.md") if not any(part in excluded for part in path.parts)
    )


def local_target(source: Path, raw_target: str) -> Path | None:
    """Resolve a local link target or return None for non-file targets."""
    target = raw_target.strip().strip("<>")
    if not target or target.startswith(("#", "http://", "https://", "mailto:")):
        return None
    path_text = unquote(target.split("#", maxsplit=1)[0])
    return (source.parent / path_text).resolve()


def main() -> int:
    """Check that every local Markdown link resolves inside the repository."""
    errors: list[str] = []
    links_checked = 0
    for source in markdown_files():
        content = source.read_text(encoding="utf-8")
        for match in LINK_PATTERN.finditer(content):
            target = local_target(source, match.group(1))
            if target is None:
                continue
            links_checked += 1
            if not target.is_relative_to(ROOT):
                errors.append(
                    f"{source.relative_to(ROOT)}: link escapes repository: {match.group(1)}"
                )
            elif not target.exists():
                errors.append(f"{source.relative_to(ROOT)}: missing target: {match.group(1)}")
    print(f"markdown files checked: {len(markdown_files())}")
    print(f"local links checked: {links_checked}")
    if errors:
        print("result: FAIL")
        print("\n".join(errors))
        return 1
    print("result: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
