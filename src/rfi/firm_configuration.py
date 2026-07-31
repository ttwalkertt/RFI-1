"""Externally owned firm JSON validation and transactional SQLite projection."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from rfi.firms import (
    FirmDraft,
    FirmError,
    FirmExternalIdentity,
    FirmIdentifier,
    FirmRepository,
    FirmStatus,
    SourceDiscoveryHint,
)
from rfi.source_profiles import (
    RetrievalCandidate,
    SourceProfileDraft,
    SourceProfileError,
    SourceProfileItem,
    SourceProfileRepository,
    load_canonical_template,
)
from rfi.source_profiles.synthesis import synthesized_candidate
from rfi.storage import RepositoryDatabase
from rfi.storage.sqlite import canonical_json, utc_now

CONFIG_DIRECTORY = "firm-config"
CONFIG_PATTERN = "*.firm-config.json"


class FirmConfigurationError(RuntimeError):
    """One or more deterministic external configuration diagnostics."""

    def __init__(self, diagnostics: tuple[str, ...]) -> None:
        self.diagnostics = diagnostics
        super().__init__("\n".join(diagnostics))


@dataclass(frozen=True)
class LoadedFirmConfiguration:
    source_name: str
    value: dict[str, Any]
    firm: FirmDraft
    identity: FirmExternalIdentity | None
    profile: SourceProfileDraft


@dataclass(frozen=True)
class MaterializationResult:
    files: int
    firms: int
    profiles: int
    external_identities: int
    authority: str = "external-json"


def configuration_directory(state: Path) -> Path:
    """Return the one documented state-relative external configuration location."""
    return state / CONFIG_DIRECTORY


def _schema() -> dict[str, Any]:
    target = resources.files("rfi").joinpath("resources/firm-config-v1.schema.json")
    value = json.loads(target.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(value)
    return value


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate object field {key!r}")
        value[key] = item
    return value


def _pointer(path: Any) -> str:
    parts = tuple(path)
    if not parts:
        return "/"
    return "/" + "/".join(
        str(item).replace("~", "~0").replace("/", "~1") for item in parts
    )


def _leaf_validation_errors(error: Any) -> tuple[Any, ...]:
    """Expose actionable nested oneOf failures instead of an opaque parent diagnostic."""
    if not error.context:
        return (error,)
    return tuple(
        leaf
        for child in error.context
        for leaf in _leaf_validation_errors(child)
    )


def _load_structural(state: Path) -> tuple[tuple[str, dict[str, Any]], ...]:
    directory = configuration_directory(state)
    paths = tuple(sorted(directory.glob(CONFIG_PATTERN))) if directory.is_dir() else ()
    validator = Draft202012Validator(_schema(), format_checker=FormatChecker())
    diagnostics: list[str] = []
    decoded: list[tuple[str, dict[str, Any]]] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
            value = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            diagnostics.append(f"{path.name}:/: malformed JSON: {error}")
            continue
        if not isinstance(value, dict):
            diagnostics.append(f"{path.name}:/: configuration root must be an object")
            continue
        errors = sorted(
            (
                leaf
                for error in validator.iter_errors(value)
                for leaf in _leaf_validation_errors(error)
            ),
            key=lambda item: (_pointer(item.absolute_path), item.message),
        )
        diagnostics.extend(
            f"{path.name}:{_pointer(error.absolute_path)}: {error.message}"
            for error in errors
        )
        if not errors:
            decoded.append((path.name, value))
    if diagnostics:
        raise FirmConfigurationError(tuple(sorted(diagnostics)))
    return tuple(decoded)


def _draft(value: dict[str, Any]) -> FirmDraft:
    firm = value["firm"]
    return FirmDraft(
        firm_id=firm["id"],
        canonical_name=firm["display_name"],
        valid_from=firm["valid_from"],
        legal_name=firm["legal_name"],
        subtitle=firm["subtitle"],
        aliases=tuple(firm["aliases"]),
        identifiers=tuple(FirmIdentifier(**item) for item in firm["identifiers"]),
        domains=tuple(firm["domains"]),
        headquarters=firm.get("headquarters", ""),
        jurisdiction=firm["jurisdiction"],
        sector=firm.get("sector", ""),
        industry=firm.get("industry", ""),
        technology_focus=tuple(firm.get("technology_focus", ())),
        source_hints=tuple(
            SourceDiscoveryHint(item["kind"], item["value"], item.get("comments", ""))
            for item in firm.get("source_hints", ())
        ),
        notes=firm.get("comments", ""),
        relevance=firm["priority"],
        status=FirmStatus(value["status"]),
        valid_through=firm.get("valid_through"),
    )


def _identity(value: dict[str, Any]) -> FirmExternalIdentity | None:
    sec = value["sources"]["sec"]
    if sec is None:
        return None
    verification = sec["verification"]
    return FirmExternalIdentity(
        provider="sec",
        legal_name=sec["registrant_name"],
        identifier=sec["cik"],
        regime=sec["filing_regime"],
        verification_status=verification["status"],
        verified_at=verification["verified_at"],
        verification_source=verification["source"],
    )


def _profile(value: dict[str, Any]) -> SourceProfileDraft:
    sec = value["sources"]["sec"]
    enabled = set(sec["artifacts"]) if sec is not None and sec["enabled"] else set()
    transcripts = value["sources"].get("earnings_transcript")
    releases = value["sources"].get("press_release")
    template = load_canonical_template()
    firm = value["firm"]
    hints = tuple(dict.fromkeys((
        firm["display_name"], firm["legal_name"], *firm["aliases"],
        *(item["value"] for item in firm["identifiers"]),
        *(item["value"] for item in firm.get("source_hints", ())),
    )))

    def discovery_candidate(source: dict[str, Any] | None) -> tuple[RetrievalCandidate, ...]:
        if source is None:
            return ()
        return (RetrievalCandidate(
            "discovery", 1,
            preferred_domains=tuple(firm["domains"]),
            discovery_hints=hints,
            discovery_class=source.get("discovery_class", "standard"),
        ),)

    transcript_candidates = discovery_candidate(transcripts)
    release_candidates = discovery_candidate(releases)
    return SourceProfileDraft(
        value["firm"]["id"],
        tuple(
            SourceProfileItem(
                artifact.artifact_id,
                artifact.artifact_id in enabled or (
                    artifact.artifact_id == "earnings_transcript"
                    and transcripts is not None
                ) or (artifact.artifact_id == "press_release" and releases is not None),
                transcript_candidates if artifact.artifact_id == "earnings_transcript"
                else release_candidates if artifact.artifact_id == "press_release" else (),
            )
            for artifact in template.artifacts
        ),
        value.get("comments", ""),
    )


def load_firm_configurations(
    state: Path, database: RepositoryDatabase
) -> tuple[LoadedFirmConfiguration, ...]:
    """Validate the complete file set structurally and semantically without mutation."""
    raw = _load_structural(state)
    diagnostics: list[str] = []
    config_ids: dict[str, str] = {}
    firm_ids: dict[str, str] = {}
    ciks: dict[str, str] = {}
    identifiers: dict[tuple[str, str, str], tuple[str, str]] = {}
    domains: dict[str, tuple[str, str]] = {}
    loaded: list[LoadedFirmConfiguration] = []
    firms = FirmRepository(state / "firm-catalog")
    profiles = SourceProfileRepository(
        state / "source-profiles", load_canonical_template()
    )
    current_firm_ids = {item.firm_id for item in firms.lookup()}
    for source_name, value in raw:
        config_id = value["config_id"]
        firm_id = value["firm"]["id"]
        if config_id != firm_id:
            diagnostics.append(
                f"{source_name}:/config_id: must equal /firm/id ({firm_id!r})"
            )
        for label, identity, seen in (
            ("config_id", config_id, config_ids),
            ("firm/id", firm_id, firm_ids),
        ):
            prior = seen.get(identity)
            if prior is not None:
                diagnostics.append(
                    f"{source_name}:/{label}: duplicate stable identity {identity!r}; "
                    f"already supplied by {prior}"
                )
            else:
                seen[identity] = source_name
        firm = _draft(value)
        for index, identifier in enumerate(firm.identifiers):
            key = (
                identifier.kind.casefold(),
                (identifier.market or "").casefold(),
                identifier.value.casefold(),
            )
            prior = identifiers.get(key)
            if prior is not None and prior[1] != firm_id:
                diagnostics.append(
                    f"{source_name}:/firm/identifiers/{index}: conflicts with "
                    f"{prior[0]} for firm {prior[1]!r}"
                )
            else:
                identifiers[key] = (source_name, firm_id)
        for index, domain in enumerate(firm.domains):
            key = domain.casefold()
            prior = domains.get(key)
            if prior is not None and prior[1] != firm_id:
                diagnostics.append(
                    f"{source_name}:/firm/domains/{index}: conflicts with "
                    f"{prior[0]} for firm {prior[1]!r}"
                )
            else:
                domains[key] = (source_name, firm_id)
        identity = _identity(value)
        sec = value["sources"]["sec"]
        if sec is not None and sec["enabled"]:
            for index, artifact_id in enumerate(sec["artifacts"]):
                candidate = synthesized_candidate(identity, artifact_id)
                if candidate is None or not candidate.locator:
                    diagnostics.append(
                        f"{source_name}:/sources/sec/artifacts/{index}: enabled SEC "
                        "artifact requires a verified 10-digit CIK that synthesizes an "
                        "executable identifier candidate"
                    )
        if identity is not None:
            firm_ciks = {
                item.value for item in firm.identifiers if item.kind.casefold() == "cik"
            }
            if firm_ciks != {identity.identifier}:
                diagnostics.append(
                    f"{source_name}:/sources/sec/cik: must match the firm's single CIK identifier"
                )
            prior = ciks.get(identity.identifier)
            if prior is not None:
                diagnostics.append(
                    f"{source_name}:/sources/sec/cik: duplicate external SEC identity "
                    f"{identity.identifier!r}; already supplied by {prior}"
                )
            else:
                ciks[identity.identifier] = source_name
        try:
            firms.validate(firm, firm_id if firm_id in current_firm_ids else None)
            profile = profiles.normalize(_profile(value))
        except (FirmError, SourceProfileError) as error:
            diagnostics.append(f"{source_name}:/: {error}")
            continue
        loaded.append(LoadedFirmConfiguration(source_name, value, firm, identity, profile))

    loaded_ids = {item.firm.firm_id for item in loaded}
    with database.connect(read_only=True) as connection:
        managed = {
            str(row[0]): str(row[1])
            for row in connection.execute(
                "SELECT firm_id,source_name FROM firm_config_authorities ORDER BY firm_id"
            )
        }
        existing_ciks = {
            str(row[0]): str(row[1])
            for row in connection.execute(
                "SELECT identifier,firm_id FROM firm_external_identities "
                "WHERE provider='sec' ORDER BY identifier"
            )
            if str(row[1]) not in loaded_ids
        }
    for firm_id, source_name in sorted(managed.items()):
        if firm_id not in loaded_ids:
            diagnostics.append(
                f"{source_name}:/: externally managed firm file is missing for {firm_id!r}"
            )
    for item in loaded:
        if item.identity is None:
            continue
        owner = existing_ciks.get(item.identity.identifier)
        if owner is not None:
            diagnostics.append(
                f"{item.source_name}:/sources/sec/cik: external SEC identity "
                f"{item.identity.identifier!r} already belongs to {owner!r}"
            )
    if diagnostics:
        raise FirmConfigurationError(tuple(sorted(diagnostics)))
    return tuple(sorted(loaded, key=lambda item: item.firm.firm_id))


def materialize_firm_configurations(
    state: Path,
    database: RepositoryDatabase,
    configurations: tuple[LoadedFirmConfiguration, ...],
    *,
    fail_after_firms: int | None = None,
) -> MaterializationResult:
    """Overwrite current file-owned projections in one all-or-nothing transaction."""
    if not configurations:
        return MaterializationResult(0, 0, 0, 0)
    firms = FirmRepository(state / "firm-catalog")
    profiles = SourceProfileRepository(
        state / "source-profiles", load_canonical_template()
    )
    timestamp = utc_now()
    firm_revisions = []
    profile_revisions = []
    for item in configurations:
        try:
            current_firm = firms.get(item.firm.firm_id)
        except FirmError:
            current_firm = None
        firm_revisions.append(
            firms._revision(  # noqa: SLF001 - one repository-owned transaction boundary
                item.firm,
                1 if current_firm is None else current_firm.revision_number + 1,
                None if current_firm is None else current_firm.revision_id,
                timestamp if current_firm is None else current_firm.created_at,
                timestamp,
            )
        )
        current_profile = profiles.get(item.firm.firm_id)
        profile_revisions.append(
            profiles._revision(  # noqa: SLF001 - one repository-owned transaction boundary
                item.profile,
                1 if current_profile is None else current_profile.revision_number + 1,
                None if current_profile is None else current_profile.source_profile_revision_id,
                timestamp if current_profile is None else current_profile.created_at,
                timestamp,
            )
        )

    with database.transaction() as connection:
        for count, (item, firm_revision, profile_revision) in enumerate(
            zip(configurations, firm_revisions, profile_revisions), start=1
        ):
            firms._insert_revision(connection, firm_revision)  # noqa: SLF001
            if firm_revision.supersedes_revision_id is None:
                connection.execute(
                    "INSERT INTO firms(firm_id,current_revision_id) VALUES (?,?)",
                    (firm_revision.firm_id, firm_revision.revision_id),
                )
            else:
                changed = connection.execute(
                    "UPDATE firms SET current_revision_id=? WHERE firm_id=? "
                    "AND current_revision_id=?",
                    (
                        firm_revision.revision_id,
                        firm_revision.firm_id,
                        firm_revision.supersedes_revision_id,
                    ),
                ).rowcount
                if changed != 1:
                    raise FirmConfigurationError((
                        f"{item.source_name}:/: current firm revision changed during startup",
                    ))
            if item.identity is None:
                connection.execute(
                    "DELETE FROM firm_external_identities WHERE firm_id=? AND provider='sec'",
                    (item.firm.firm_id,),
                )
            else:
                identity_json = canonical_json(asdict(item.identity))
                connection.execute(
                    "INSERT INTO firm_external_identities VALUES (?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(firm_id,provider) DO UPDATE SET legal_name=excluded.legal_name,"
                    "identifier=excluded.identifier,regime=excluded.regime,"
                    "verification_status=excluded.verification_status,"
                    "verified_at=excluded.verified_at,"
                    "verification_source=excluded.verification_source,"
                    "catalog_version=excluded.catalog_version,"
                    "canonical_json=excluded.canonical_json",
                    (
                        item.firm.firm_id,
                        "sec",
                        item.identity.legal_name,
                        item.identity.identifier,
                        item.identity.regime,
                        item.identity.verification_status,
                        item.identity.verified_at,
                        item.identity.verification_source,
                        1,
                        identity_json,
                    ),
                )
            profiles._insert_revision(connection, profile_revision)  # noqa: SLF001
            if profile_revision.supersedes_revision_id is None:
                connection.execute(
                    "INSERT INTO source_profiles VALUES (?,?)",
                    (item.firm.firm_id, profile_revision.source_profile_revision_id),
                )
            else:
                changed = connection.execute(
                    "UPDATE source_profiles SET current_revision_id=? WHERE firm_id=? "
                    "AND current_revision_id=?",
                    (
                        profile_revision.source_profile_revision_id,
                        item.firm.firm_id,
                        profile_revision.supersedes_revision_id,
                    ),
                ).rowcount
                if changed != 1:
                    raise FirmConfigurationError(
                        (
                            f"{item.source_name}:/: current source-profile revision "
                            "changed during startup",
                        )
                    )
            connection.execute(
                "INSERT INTO firm_config_authorities VALUES (?,?,?,?,?) "
                "ON CONFLICT(firm_id) DO UPDATE SET config_id=excluded.config_id,"
                "schema_version=excluded.schema_version,source_name=excluded.source_name,"
                "canonical_json=excluded.canonical_json",
                (
                    item.firm.firm_id,
                    item.value["config_id"],
                    item.value["schema_version"],
                    item.source_name,
                    canonical_json(item.value),
                ),
            )
            if fail_after_firms is not None and count >= fail_after_firms:
                raise FirmConfigurationError(("injected materialization failure",))
        database.advance_revision(connection)
    identities = sum(item.identity is not None for item in configurations)
    return MaterializationResult(
        len(configurations), len(configurations), len(configurations), identities
    )


def prepare_firm_configuration(
    state: Path, *, fail_after_firms: int | None = None
) -> MaterializationResult:
    """Validate and materialize external configuration into initialized current-schema state."""
    database = RepositoryDatabase.open(state)
    configurations = load_firm_configurations(state, database)
    return materialize_firm_configurations(
        state, database, configurations, fail_after_firms=fail_after_firms
    )


def validate_firm_configuration(state: Path) -> tuple[LoadedFirmConfiguration, ...]:
    """Validate and load external configuration without changing its SQLite projection."""
    database = RepositoryDatabase.open(state)
    return load_firm_configurations(state, database)
