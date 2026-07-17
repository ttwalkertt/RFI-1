"""Stable operator command line for the local RFI-1 application."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from rfi.admin import create_admin_server
from rfi.catalog_import import (
    CatalogImportError,
    canonical_template,
    import_catalogs,
)
from rfi.concepts import ConceptError, ConceptRepository, sample_concepts
from rfi.firms import FirmError, FirmRepository, sample_firms

DEFAULT_STATE = Path(".artifacts/runtime/rfi-1")


class ApplicationError(RuntimeError):
    """An actionable operator-facing application lifecycle error."""


def _state(value: str) -> Path:
    """Return a normalized operator-selected state path."""
    return Path(value).expanduser().resolve()


def _add_state(parser: argparse.ArgumentParser) -> None:
    """Add the common state-location option with its documented default."""
    parser.add_argument(
        "--state",
        type=_state,
        default=_state(str(DEFAULT_STATE)),
        metavar="PATH",
        help=f"application state directory (default: {DEFAULT_STATE})",
    )


def parser() -> argparse.ArgumentParser:
    """Build the discoverable stable application command hierarchy."""
    value = argparse.ArgumentParser(
        prog="rfi",
        description="RFI-1 local application and integrated admin-console operator CLI.",
        epilog=(
            "examples:\n"
            "  rfi init\n"
            "  rfi seed\n"
            "  rfi admin\n"
            "  python -m rfi admin --state /path/to/state --port 9000\n\n"
            "Run init once for a state location. Seed is optional and always explicit. "
            "Use admin for normal repeat operation."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = value.add_subparsers(dest="command", required=True, title="commands")
    initialize = commands.add_parser(
        "init",
        help="initialize empty local application state (run once)",
        description="Initialize empty RFI-1 concept and target-firm catalogs safely.",
        epilog="example: rfi init --state .artifacts/runtime/rfi-1",
    )
    _add_state(initialize)
    seed = commands.add_parser(
        "seed",
        help="explicitly add missing starter data (optional, repeat-safe)",
        description="Add missing RFI-1 starter concepts and target firms to initialized state.",
        epilog=(
            "examples:\n"
            "  rfi seed --state .artifacts/runtime/rfi-1\n"
            "  rfi seed --state .artifacts/runtime/rfi-1 --file firms.yaml\n"
            "  rfi seed --print-schema"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_state(seed)
    seed.add_argument(
        "-f",
        "--file",
        action="append",
        type=_state,
        default=[],
        metavar="FILE",
        help="external YAML catalog to import (repeat for multiple files)",
    )
    seed.add_argument(
        "--print-schema",
        action="store_true",
        help="print the canonical YAML import template without reading or changing state",
    )
    admin = commands.add_parser(
        "admin",
        help="launch the integrated concept and target-firm admin console",
        description=(
            "Launch the RFI-1 admin console using existing initialized state. "
            "This command never seeds records. Press Ctrl-C to stop cleanly."
        ),
        epilog="example: rfi admin --host 127.0.0.1 --port 8765",
    )
    _add_state(admin)
    admin.add_argument("--host", default="127.0.0.1", help="server bind host (default: 127.0.0.1)")
    admin.add_argument("--port", type=int, default=8765, help="server port (default: 8765)")
    return value


def initialize(state: Path) -> None:
    """Initialize missing catalogs without changing valid existing catalogs."""
    concept_exists = (state / "catalog.json").exists()
    firm_state = state / "firm-catalog"
    firm_exists = (firm_state / "catalog.json").exists()
    if concept_exists:
        ConceptRepository.open(state)
    if firm_exists:
        FirmRepository.open(firm_state)
    if not concept_exists:
        ConceptRepository.initialize(state)
    if not firm_exists:
        FirmRepository.initialize(firm_state)
    changes = []
    concept_change = (
        "concept catalog already existed" if concept_exists else "created concept catalog"
    )
    firm_change = (
        "target-firm catalog already existed" if firm_exists else "created target-firm catalog"
    )
    changes.extend((concept_change, firm_change))
    print(f"RFI-1 state: {state}")
    for change in changes:
        print(f"- {change}")


def _open_state(state: Path) -> tuple[ConceptRepository, FirmRepository]:
    """Open complete application state or explain the required first-run action."""
    missing = []
    if not (state / "catalog.json").is_file():
        missing.append("concept catalog")
    if not (state / "firm-catalog/catalog.json").is_file():
        missing.append("target-firm catalog")
    if missing:
        raise ApplicationError(
            f"state is not initialized at {state} (missing {', '.join(missing)}); "
            "run 'rfi init' with the same --state path"
        )
    return ConceptRepository.open(state), FirmRepository.open(state / "firm-catalog")


def seed(state: Path, files: tuple[Path, ...] = ()) -> None:
    """Add only missing starter records to verified initialized state."""
    concepts, firms = _open_state(state)
    imported = import_catalogs(files, firms, sample_firms()) if files else None
    existing_concepts = {item.concept_id for item in concepts.lookup()}
    existing_firms = {item.firm_id for item in firms.lookup()}
    concept_created = []
    firm_created = []
    for draft in sample_concepts():
        if draft.concept_id not in existing_concepts:
            concepts.create(draft)
            concept_created.append(draft.concept_id)
    for draft in sample_firms():
        if draft.firm_id not in existing_firms:
            firms.create(draft)
            firm_created.append(draft.firm_id)
    print(f"RFI-1 state: {state}")
    print(f"- starter concepts created: {len(concept_created)}; already present: "
          f"{len(existing_concepts.intersection(item.concept_id for item in sample_concepts()))}")
    print(f"- starter target firms created: {len(firm_created)}; already present: "
          f"{len(existing_firms.intersection(item.firm_id for item in sample_firms()))}")
    if imported is not None:
        print(
            f"- external catalogs validated: {imported.files}; target firms created: "
            f"{len(imported.created)}; already present: {len(imported.already_present)}"
        )


def serve(state: Path, host: str, port: int) -> None:
    """Run the integrated admin console until interrupted by the operator."""
    _open_state(state)
    server = create_admin_server(state, host, port)
    bound_host, bound_port = server.server_address[:2]
    display_host = "127.0.0.1" if bound_host in {"0.0.0.0", "::"} else bound_host
    print("RFI-1 admin console", flush=True)
    print(f"Local URL: http://{display_host}:{bound_port}/", flush=True)
    print(f"State: {state}", flush=True)
    print("Stop: press Ctrl-C", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nRFI-1 admin console stopped.")
    finally:
        server.server_close()


def main(argv: Sequence[str] | None = None) -> int:
    """Run one stable RFI-1 application operation with actionable failures."""
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "init":
            initialize(arguments.state)
        elif arguments.command == "seed":
            if arguments.print_schema:
                if arguments.file:
                    raise ApplicationError("--print-schema cannot be combined with --file")
                print(canonical_template(), end="")
            else:
                seed(arguments.state, tuple(arguments.file))
        else:
            serve(arguments.state, arguments.host, arguments.port)
    except (ApplicationError, CatalogImportError, ConceptError, FirmError, OSError) as error:
        print(f"rfi: error: {error}", file=sys.stderr)
        print("Use 'rfi --help' or 'rfi <command> --help' for usage.", file=sys.stderr)
        return 2
    return 0
