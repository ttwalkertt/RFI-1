#!/usr/bin/env python3
"""Validate local Markdown links without network access."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LINK_PATTERN = re.compile(r"(?<!!)\[[^]]*]\(([^)]+)\)")
HELP_TOPIC_PATTERN = re.compile(r"^<!-- help-topic: ([a-z][a-z0-9-]*) -->$", re.MULTILINE)


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
    help_topic_links_checked = 0
    topics: list[str] = []
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
    guide = ROOT / "docs/operator-guide.md"
    if guide.is_file():
        content = guide.read_text(encoding="utf-8")
        topics = HELP_TOPIC_PATTERN.findall(content)
        if len(topics) != len(set(topics)):
            errors.append("docs/operator-guide.md: duplicate explicit help topic identifier")
        for target in re.findall(r"]\(#([a-z][a-z0-9-]*)\)", content):
            help_topic_links_checked += 1
            if target not in topics:
                errors.append(
                    f"docs/operator-guide.md: missing explicit help topic target: #{target}"
                )
    print(f"markdown files checked: {len(markdown_files())}")
    print(f"local links checked: {links_checked}")
    print(f"explicit help topics checked: {len(topics)}")
    print(f"help topic links checked: {help_topic_links_checked}")
    if errors:
        print("result: FAIL")
        print("\n".join(errors))
        return 1
    print("result: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
