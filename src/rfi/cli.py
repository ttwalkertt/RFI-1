"""Stable operator command line for the local RFI-1 application."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from rfi.acquisition import AcquisitionRepository
from rfi.admin import create_admin_server
from rfi.catalog_import import (
    CatalogImportError,
    canonical_template,
    import_catalogs,
)
from rfi.concepts import ConceptError, ConceptRepository, sample_concepts
from rfi.firms import FirmError, FirmRepository, sample_firms
from rfi.mailing_lists import (
    AcquisitionLimits,
    LINUX_BLOCK_SOURCE,
    LoreArchive,
    MailingListAcquisitionService,
    MailingListError,
    MailingListQueryService,
    MailingListRepository,
    SelectionCriteria,
)
from rfi.pull import PullError, PullRequest, PullStatus, create_pull_workflow
from rfi.source_profiles import (
    SourceProfileError,
    SourceProfileRepository,
    load_canonical_template,
)
from rfi.storage import (
    DATABASE_NAME,
    RepositoryDatabase,
    StorageError,
    create_backup,
    restore_backup,
)

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
            "  rfi pull --firm seagate\n"
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
    pull = commands.add_parser(
        "pull",
        help="retrieve enabled artifacts through the shared Pull Workflow",
        description=(
            "Run the durable Pull Workflow for selected firms or every firm with a "
            "saved source profile. Each artifact and firm executes independently."
        ),
        epilog=(
            "examples:\n"
            "  rfi pull --firm seagate\n"
            "  rfi pull --firm seagate --firm ibm\n"
            "  rfi pull --all-configured"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_state(pull)
    selection = pull.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--firm",
        action="append",
        default=[],
        metavar="FIRM_ID",
        help="firm to pull (repeat for multiple firms)",
    )
    selection.add_argument(
        "--all-configured",
        action="store_true",
        help="pull every firm with a saved source profile",
    )
    backup = commands.add_parser(
        "backup", help="create a verified SQLite and content-store backup"
    )
    _add_state(backup)
    backup.add_argument("--output", type=_state, required=True, metavar="ZIP")
    restore = commands.add_parser(
        "restore", help="restore a verified backup into fresh state"
    )
    _add_state(restore)
    restore.add_argument("--input", type=_state, required=True, metavar="ZIP")
    verify = commands.add_parser(
        "verify", help="verify SQLite, relationships, and immutable content"
    )
    _add_state(verify)
    mailing = commands.add_parser(
        "mailing-list",
        help="configure, acquire, rebuild, and query bounded mailing-list evidence",
        description=(
            "Operate the bounded development-mailing-list vertical. Acquisition always "
            "requires explicit selection criteria and hard seed/context limits."
        ),
    )
    _add_state(mailing)
    mailing_actions = mailing.add_subparsers(dest="mailing_action", required=True)
    mailing_actions.add_parser("configure-linux-block", help="register the governed Lore source")
    for name in ("preview", "acquire"):
        action = mailing_actions.add_parser(name, help=f"{name} a bounded live Lore acquisition")
        action.add_argument("--source", default=LINUX_BLOCK_SOURCE.source_id)
        action.add_argument("--message-id", action="append", default=[], metavar="MESSAGE_ID")
        action.add_argument("--query")
        action.add_argument("--date-from")
        action.add_argument("--date-through")
        action.add_argument("--topic", action="append", default=[])
        action.add_argument("--seed-limit", type=int, default=10)
        action.add_argument("--context-limit", type=int, default=100)
        action.add_argument("--descendant-depth", type=int, default=0)
        action.add_argument(
            "--live", action="store_true", required=True,
            help="explicitly authorize the separately gated public-archive path",
        )
    sources = mailing_actions.add_parser("sources", help="list configured mailing-list sources")
    discussions = mailing_actions.add_parser("discussions", help="list retained discussions")
    discussions.add_argument("--source", default=LINUX_BLOCK_SOURCE.source_id)
    discussions.add_argument("--limit", type=int, default=25)
    search = mailing_actions.add_parser("search", help="search retained message metadata and text")
    search.add_argument("text")
    search.add_argument("--source")
    search.add_argument("--limit", type=int, default=50)
    mailing_actions.add_parser("incomplete", help="list incomplete or quarantined material")
    mailing_actions.add_parser("rebuild", help="rebuild discussion indexes without network access")
    return value


def initialize(state: Path) -> None:
    """Initialize or validate one fresh authoritative SQLite repository."""
    existed = (state / DATABASE_NAME).is_file()
    try:
        database = RepositoryDatabase.initialize(state)
    except StorageError as error:
        raise ApplicationError(str(error)) from error
    firm_state = state / "firm-catalog"
    source_profile_state = state / "source-profiles"
    template = load_canonical_template()
    ConceptRepository.initialize(state)
    FirmRepository.initialize(firm_state)
    SourceProfileRepository.initialize(source_profile_state, template)
    print(f"RFI-1 state: {state}")
    print(
        "- compatible SQLite repository already existed"
        if existed
        else "- created authoritative SQLite repository and immutable content store"
    )
    print(f"- schema version: {database.validate()['schema_version']}")


def _open_state(
    state: Path,
) -> tuple[ConceptRepository, FirmRepository, SourceProfileRepository]:
    """Open complete application state or explain the required first-run action."""
    try:
        RepositoryDatabase.open(state)
    except StorageError as error:
        raise ApplicationError(str(error)) from error
    template = load_canonical_template()
    source_profile_state = state / "source-profiles"
    source_profiles = SourceProfileRepository.open(source_profile_state, template)
    return (
        ConceptRepository.open(state),
        FirmRepository.open(state / "firm-catalog"),
        source_profiles,
    )


def seed(state: Path, files: tuple[Path, ...] = ()) -> None:
    """Add only missing starter records to verified initialized state."""
    concepts, firms, _source_profiles = _open_state(state)
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


def pull_sources(state: Path, firm_ids: tuple[str, ...], all_configured: bool) -> int:
    """Run the shared Pull Workflow and print its durable structured result."""
    _open_state(state)
    result = create_pull_workflow(state).run(PullRequest(firm_ids, all_configured))
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0 if result.status == PullStatus.COMPLETED else 1


def verify_state(state: Path) -> None:
    """Verify both authorities through repository-owned integrity checks."""
    _open_state(state)
    database = RepositoryDatabase.open(state).validate()
    acquisition = AcquisitionRepository(state / "acquisition")
    result = acquisition.verify_integrity()
    mailing_lists = MailingListRepository(state).validate_connectivity()
    print(json.dumps({"database": database, "repository": result,
                      "mailing_lists": mailing_lists}, indent=2, sort_keys=True))


def mailing_list_operation(arguments: argparse.Namespace) -> None:
    """Run one bounded mailing-list operator action through public contracts."""
    _open_state(arguments.state)
    repository = MailingListRepository(arguments.state)
    action = arguments.mailing_action
    if action == "configure-linux-block":
        created = repository.configure_source(LINUX_BLOCK_SOURCE)
        print(json.dumps({"source": asdict(LINUX_BLOCK_SOURCE), "created": created}, indent=2))
        return
    query = MailingListQueryService(repository)
    if action == "sources":
        print(json.dumps({"items": query.sources()}, indent=2))
        return
    if action == "discussions":
        print(json.dumps({"items": [asdict(item) for item in query.discussions(
            arguments.source, arguments.limit)]}, indent=2, default=str))
        return
    if action == "search":
        print(json.dumps({"items": [asdict(item) for item in query.search(
            arguments.text, arguments.source, arguments.limit)]}, indent=2, default=str))
        return
    if action == "incomplete":
        print(json.dumps({"items": [asdict(item) for item in query.incomplete()]},
                         indent=2, default=str))
        return
    acquisition = MailingListAcquisitionService(
        repository,
        LoreArchive(repository.source(arguments.source).archive_base_url)
        if action in {"preview", "acquire"} else LoreArchive(LINUX_BLOCK_SOURCE.archive_base_url),
    )
    if action == "rebuild":
        print(json.dumps(acquisition.rebuild(), indent=2))
        return
    criteria = SelectionCriteria(
        tuple(arguments.message_id), arguments.query, arguments.date_from,
        arguments.date_through, tuple(arguments.topic),
    )
    limits = AcquisitionLimits(
        arguments.seed_limit, arguments.context_limit, arguments.descendant_depth
    )
    result = (
        acquisition.preview(arguments.source, criteria, limits)
        if action == "preview"
        else acquisition.acquire(arguments.source, criteria, limits)
    )
    print(json.dumps(asdict(result), indent=2, sort_keys=True, default=str))


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
        elif arguments.command == "admin":
            serve(arguments.state, arguments.host, arguments.port)
        elif arguments.command == "pull":
            return pull_sources(
                arguments.state,
                tuple(arguments.firm),
                arguments.all_configured,
            )
        elif arguments.command == "backup":
            _open_state(arguments.state)
            print(json.dumps(create_backup(arguments.state, arguments.output), indent=2))
        elif arguments.command == "restore":
            print(json.dumps(restore_backup(arguments.input, arguments.state), indent=2))
        elif arguments.command == "mailing-list":
            mailing_list_operation(arguments)
        else:
            verify_state(arguments.state)
    except (
        ApplicationError,
        CatalogImportError,
        ConceptError,
        FirmError,
        SourceProfileError,
        PullError,
        MailingListError,
        StorageError,
        OSError,
    ) as error:
        print(f"rfi: error: {error}", file=sys.stderr)
        print("Use 'rfi --help' or 'rfi <command> --help' for usage.", file=sys.stderr)
        return 2
    return 0
