"""Stable operator command line for the local RFI-1 application."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from rfi.acquisition import (
    AcquisitionRepository, SecForm10KAdapter, SecProviderClient,
    user_agent_from_environment,
)
from rfi.admin import create_admin_server
from rfi.catalog_import import (
    CatalogImportError,
    canonical_template,
    import_catalogs,
)
from rfi.concepts import ConceptError, ConceptRepository, sample_concepts
from rfi.firms import FirmError, FirmRepository, sample_firms
from rfi.firm_configuration import (
    FirmConfigurationError,
    prepare_firm_configuration,
)
from rfi.mailing_lists import (
    AcquisitionLimits,
    LINUX_BLOCK_SOURCE,
    LoreArchive,
    LoreTransportPolicy,
    MailingListAcquisitionService,
    MailingListError,
    MailingListQueryService,
    MailingListRepository,
    MailingListSourceService,
    SelectionCriteria,
)
from rfi.pull import PullError, PullRequest, PullStatus, create_pull_workflow
from rfi.sec import (
    FirmIdentifierSecResolver, SecRepository, SecRetrievalWorkflow, SecWorkflowError,
    SecWorkflowOutcome,
)
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
from rfi.storage.configuration import (
    ConfigurationError, export_configuration, import_configuration,
)
from rfi.streams import StreamError, StreamRepository, StreamService, draft_from_dict, template_yaml

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
    sec = commands.add_parser(
        "sec-retrieve",
        help="run the authoritative bounded SEC Form 10-K workflow",
        description=(
            "Resolve or reuse durable SEC issuer knowledge, retrieve one deterministic "
            "Form 10-K, and ingest it through immutable repository authority."
        ),
    )
    _add_state(sec)
    sec.add_argument("--firm", required=True, metavar="FIRM_ID")
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
    config = commands.add_parser(
        "config", help="export or import configuration without artifact state"
    )
    _add_state(config)
    config_actions = config.add_subparsers(dest="config_action", required=True)
    config_export = config_actions.add_parser(
        "export", help="export deterministic acquisition configuration YAML"
    )
    config_export.add_argument("--output", type=_state, required=True, metavar="YAML")
    config_import = config_actions.add_parser(
        "import", help="import configuration into initialized current-schema state"
    )
    config_import.add_argument("--file", type=_state, required=True, metavar="YAML")
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
    mailing_actions.add_parser("configure-linux-block", help="register the default governed source")
    configure_lore = mailing_actions.add_parser(
        "configure-lore-source", help="register one governed Lore source and transport policy"
    )
    configure_lore.add_argument("--source", required=True)
    configure_lore.add_argument("--list-id", required=True)
    configure_lore.add_argument("--display-name", required=True)
    configure_lore.add_argument("--archive-base-url", required=True)
    configure_lore.add_argument("--user-agent", default=LoreTransportPolicy.user_agent)
    configure_lore.add_argument(
        "--minimum-request-interval", type=float,
        default=LoreTransportPolicy.minimum_request_interval_seconds,
    )
    configure_lore.add_argument(
        "--maximum-concurrency", type=int, default=LoreTransportPolicy.maximum_concurrency
    )
    configure_lore.add_argument(
        "--timeout", type=float, default=LoreTransportPolicy.timeout_seconds
    )
    configure_lore.add_argument(
        "--maximum-response-bytes", type=int,
        default=LoreTransportPolicy.maximum_response_bytes,
    )
    configure_lore.add_argument(
        "--maximum-attempts", type=int,
        default=LoreTransportPolicy.maximum_attempts_per_request,
    )
    configure_lore.add_argument(
        "--backoff-initial", type=float, default=LoreTransportPolicy.backoff_initial_seconds
    )
    configure_lore.add_argument(
        "--backoff-maximum", type=float, default=LoreTransportPolicy.backoff_maximum_seconds
    )
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
            "--continuation-id",
            help="durable continuation identity; reuse it to resume the same seed page",
        )
        action.add_argument("--discovery-offset", type=int, default=0)
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
    streams = commands.add_parser(
        "stream",
        help="configure, validate, execute, inspect, and rebuild artifact streams",
        description="Operate revisioned bounded artifact streams through shared service contracts.",
    )
    _add_state(streams)
    stream_actions = streams.add_subparsers(dest="stream_action", required=True)
    stream_actions.add_parser("list", help="list current stream definitions and status")
    stream_actions.add_parser("capabilities", help="list registered schema fields and expansions")
    stream_actions.add_parser(
        "schema", help="print the canonical versioned stream YAML schema/template"
    )
    validate = stream_actions.add_parser(
        "validate", help="validate and normalize a canonical stream YAML file without saving"
    )
    validate.add_argument("--file", type=_state, required=True, metavar="YAML")
    import_action = stream_actions.add_parser(
        "import", help="explicitly import canonical YAML as a new stream or new revision"
    )
    import_action.add_argument("--file", type=_state, required=True, metavar="YAML")
    import_mode = import_action.add_mutually_exclusive_group(required=True)
    import_mode.add_argument("--new", action="store_true", help="create a new stable identity")
    import_mode.add_argument(
        "--revision", action="store_true", help="create a revision of an existing identity"
    )
    import_action.add_argument(
        "--expected-revision", help="optional optimistic current revision identity"
    )
    export = stream_actions.add_parser(
        "export", help="export a saved stream revision as deterministic canonical YAML"
    )
    export.add_argument("--stream", dest="stream_id", required=True, metavar="STREAM_ID")
    export.add_argument("--revision-id")
    export.add_argument("--output", type=_state, metavar="YAML")
    for name in ("preview", "save"):
        action = stream_actions.add_parser(
            name, help=f"{name} a legacy JSON stream draft through the shared contract"
        )
        action.add_argument("--file", type=_state, required=True, metavar="JSON")
        if name == "save":
            action.add_argument("--expected-revision")
        else:
            action.add_argument("--limit", type=int, default=25)
    for name in ("run", "run-chain", "memberships"):
        action = stream_actions.add_parser(name, help=f"{name} for one saved stream")
        action.add_argument("stream_id")
        if name == "memberships":
            action.add_argument("--run-id")
            action.add_argument("--limit", type=int, default=100)
    inspect = stream_actions.add_parser("inspect-run", help="inspect one durable stream run")
    inspect.add_argument("run_id")
    stream_actions.add_parser("rebuild", help="rebuild memberships and lineage without network")
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
    prepare_firm_configuration(state)
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
    prepare_firm_configuration(state)
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


def sec_retrieve(state: Path, firm_id: str) -> int:
    """Run the independently invocable authoritative SEC workflow."""
    _open_state(state)
    provider = SecProviderClient(user_agent_from_environment)
    workflow = SecRetrievalWorkflow(
        FirmRepository.open(state / "firm-catalog"), SecRepository(state),
        AcquisitionRepository(state / "acquisition"), FirmIdentifierSecResolver(provider),
        SecForm10KAdapter(provider, lambda: datetime.now(UTC).isoformat()),
    )
    result = workflow.run(firm_id)
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0 if result.outcome in {
        SecWorkflowOutcome.SUCCESS, SecWorkflowOutcome.SUCCESS_WITH_SOURCE_BOOTSTRAP,
        SecWorkflowOutcome.NON_APPLICABLE, SecWorkflowOutcome.NO_QUALIFYING_FILING,
    } else 1


def verify_state(state: Path) -> None:
    """Verify both authorities through repository-owned integrity checks."""
    _open_state(state)
    database = RepositoryDatabase.open(state).validate()
    acquisition = AcquisitionRepository(state / "acquisition")
    result = acquisition.verify_integrity()
    mailing_lists = MailingListRepository(state).validate_connectivity()
    print(json.dumps({"database": database, "repository": result,
                      "mailing_lists": mailing_lists}, indent=2, sort_keys=True))


def config_operation(arguments: argparse.Namespace) -> None:
    """Export or transactionally import configuration-only state."""
    if arguments.config_action == "export":
        rendered = export_configuration(arguments.state)
        arguments.output.write_text(rendered, encoding="utf-8")
        print(json.dumps({"output": str(arguments.output), "format": "rfi-config", "version": 1}))
        return
    try:
        text = arguments.file.read_text(encoding="utf-8")
    except OSError as error:
        raise ApplicationError(f"cannot read configuration file: {arguments.file}") from error
    print(json.dumps(import_configuration(arguments.state, text), indent=2, sort_keys=True))


def mailing_list_operation(arguments: argparse.Namespace) -> None:
    """Run one bounded mailing-list operator action through public contracts."""
    _open_state(arguments.state)
    repository = MailingListRepository(arguments.state)
    source_service = MailingListSourceService(repository)
    action = arguments.mailing_action
    if action == "configure-linux-block":
        configured, created = source_service.create(asdict(LINUX_BLOCK_SOURCE))
        print(json.dumps({"source": asdict(configured), "created": created}, indent=2))
        return
    if action == "configure-lore-source":
        policy = LoreTransportPolicy(
            arguments.user_agent,
            arguments.minimum_request_interval,
            arguments.maximum_concurrency,
            arguments.timeout,
            arguments.maximum_response_bytes,
            arguments.maximum_attempts,
            arguments.backoff_initial,
            arguments.backoff_maximum,
        )
        configured, created = source_service.create({
            "source_id": arguments.source,
            "list_id": arguments.list_id,
            "display_name": arguments.display_name,
            "archive_base_url": arguments.archive_base_url,
            "provider": "lore-public-inbox",
            "transport": asdict(policy),
        })
        print(json.dumps({"source": asdict(configured), "created": created}, indent=2))
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
        LoreArchive(repository.source(arguments.source))
        if action in {"preview", "acquire"} else LoreArchive(LINUX_BLOCK_SOURCE),
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
        else acquisition.acquire(
            arguments.source, criteria, limits,
            discovery_offset=arguments.discovery_offset,
            coverage_batch_id=arguments.continuation_id,
        )
    )
    print(json.dumps(asdict(result), indent=2, sort_keys=True, default=str))


def stream_operation(arguments: argparse.Namespace) -> None:
    """Run one stream operation through the same service used by the admin page."""
    if arguments.stream_action == "schema":
        print(template_yaml(), end="")
        return
    _open_state(arguments.state)
    service = StreamService(StreamRepository(arguments.state))
    action = arguments.stream_action
    if action == "list":
        value: object = {"items": [asdict(item) for item in service.list_streams()]}
    elif action == "capabilities":
        value = {"items": [asdict(item) for item in service.capabilities()]}
    elif action == "validate":
        try:
            text = arguments.file.read_text(encoding="utf-8")
        except OSError as error:
            raise ApplicationError(f"cannot read stream YAML: {arguments.file}") from error
        review = service.review_yaml(text)
        if not review.valid:
            first = review.errors[0]
            raise StreamError(first["code"], first["message"], first.get("path"))
        value = asdict(review)
    elif action == "import":
        try:
            text = arguments.file.read_text(encoding="utf-8")
        except OSError as error:
            raise ApplicationError(f"cannot read stream YAML: {arguments.file}") from error
        mode = "new" if arguments.new else "revision"
        value = asdict(service.import_yaml(text, mode, arguments.expected_revision))
    elif action == "export":
        rendered = service.export_yaml(arguments.stream_id, arguments.revision_id)
        if arguments.output:
            arguments.output.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
        return
    elif action in {"preview", "save"}:
        try:
            raw = json.loads(arguments.file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ApplicationError("stream definition must be a readable JSON object") from error
        if not isinstance(raw, dict):
            raise ApplicationError("stream definition JSON must be an object")
        draft = draft_from_dict(raw)
        if action == "preview":
            value = asdict(service.preview(draft, arguments.limit))
        else:
            value = asdict(service.save(draft, arguments.expected_revision))
    elif action == "run":
        value = asdict(service.run(arguments.stream_id))
    elif action == "run-chain":
        value = {"items": [asdict(item) for item in service.run_chain(arguments.stream_id)]}
    elif action == "memberships":
        value = {"items": [asdict(item) for item in service.repository.memberships(
            arguments.stream_id, arguments.run_id, arguments.limit
        )]}
    elif action == "inspect-run":
        value = asdict(service.repository.run(arguments.run_id))
    else:
        value = service.rebuild()
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


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
        elif arguments.command == "sec-retrieve":
            return sec_retrieve(arguments.state, arguments.firm)
        elif arguments.command == "backup":
            _open_state(arguments.state)
            print(json.dumps(create_backup(arguments.state, arguments.output), indent=2))
        elif arguments.command == "restore":
            print(json.dumps(restore_backup(arguments.input, arguments.state), indent=2))
        elif arguments.command == "config":
            config_operation(arguments)
        elif arguments.command == "mailing-list":
            mailing_list_operation(arguments)
        elif arguments.command == "stream":
            stream_operation(arguments)
        else:
            verify_state(arguments.state)
    except (
        ApplicationError,
        CatalogImportError,
        ConceptError,
        FirmError,
        FirmConfigurationError,
        SourceProfileError,
        PullError,
        SecWorkflowError,
        MailingListError,
        StreamError,
        StorageError,
        ConfigurationError,
        OSError,
    ) as error:
        print(f"rfi: error: {error}", file=sys.stderr)
        print("Use 'rfi --help' or 'rfi <command> --help' for usage.", file=sys.stderr)
        return 2
    return 0
