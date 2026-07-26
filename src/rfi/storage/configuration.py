"""Configuration-only export and transactional import for clean-state resets."""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from rfi.firms import (
    FirmDraft, FirmIdentifier, FirmRepository, FirmStatus, SourceDiscoveryHint,
)
from rfi.mailing_lists import (
    LoreTransportPolicy, MailingListRepository, MailingListSource,
)
from rfi.sec import SecApplicability, SecRepository, SecSourceKnowledge
from rfi.source_profiles import (
    RetrievalCandidate, SourceProfileDraft, SourceProfileItem,
    SourceProfileRepository, load_canonical_template,
)
from rfi.storage.sqlite import RepositoryDatabase, StorageError
from rfi.streams import StreamDraft, StreamRepository, StreamService

FORMAT = "rfi-config"
VERSION = 1
_ROOT_KEYS = {"format", "version", "firms", "source_profiles", "sources", "sec_sources", "streams"}


class ConfigurationError(RuntimeError):
    """Actionable configuration package failure."""


def _json(value: str) -> dict[str, Any]:
    decoded = json.loads(value)
    if not isinstance(decoded, dict):
        raise ConfigurationError("stored configuration is not an object")
    return decoded


def export_configuration(state: Path) -> str:
    """Return deterministic current effective configuration without evidence state."""
    database = RepositoryDatabase.open(state)
    with database.connect(read_only=True) as connection:
        firms = [_firm_export(_json(str(row[0]))) for row in connection.execute(
            "SELECT r.canonical_json FROM firms f JOIN firm_revisions r "
            "ON r.revision_id=f.current_revision_id ORDER BY f.firm_id"
        )]
        profiles = [_profile_export(_json(str(row[0]))) for row in connection.execute(
            "SELECT r.canonical_json FROM source_profiles p JOIN source_profile_revisions r "
            "ON r.revision_id=p.current_revision_id ORDER BY p.firm_id"
        )]
        sources = [_json(str(row[0])) for row in connection.execute(
            "SELECT canonical_json FROM mailing_list_sources ORDER BY source_id"
        )]
        sec_sources = [_json(str(row[0])) for row in connection.execute(
            "SELECT canonical_json FROM sec_sources ORDER BY firm_id"
        )]
        streams = [_json(str(row[0])) for row in connection.execute(
            "SELECT r.canonical_json FROM artifact_streams s JOIN artifact_stream_revisions r "
            "ON r.revision_id=s.current_revision_id ORDER BY s.stream_id"
        )]
    value = {
        "format": FORMAT, "version": VERSION, "firms": firms,
        "source_profiles": profiles, "sources": sources,
        "sec_sources": sec_sources, "streams": streams,
    }
    return yaml.safe_dump(value, sort_keys=False, allow_unicode=True, width=100)


def import_configuration(state: Path, text: str) -> dict[str, int]:
    """Validate completely, reject conflicts, then apply configuration atomically."""
    target = RepositoryDatabase.open(state)
    value = _parse(text)
    with tempfile.TemporaryDirectory(prefix="rfi-config-import-") as temporary:
        staging_root = Path(temporary) / "state"
        _build_staging(staging_root, value)
        staging = RepositoryDatabase.open(staging_root)
        with target.transaction() as connection:
            existing = _semantic_state(connection)
            incoming = _semantic_state_from_database(staging)
            for category in incoming:
                for identity, item in incoming[category].items():
                    if identity in existing[category] and existing[category][identity] != item:
                        raise ConfigurationError(
                            f"configuration conflict in {category} for {identity!r}; "
                            "target differs from import package"
                        )
            created = _copy_missing(connection, staging, existing, incoming)
            if any(created.values()):
                target.advance_revision(connection)
    return created


def _parse(text: str) -> dict[str, Any]:
    try:
        value = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ConfigurationError(f"malformed configuration YAML: {error}") from error
    if not isinstance(value, dict):
        raise ConfigurationError("configuration package must be a YAML object")
    unknown = set(value) - _ROOT_KEYS
    if unknown:
        raise ConfigurationError(f"unknown configuration field: {sorted(unknown)[0]}")
    if value.get("format") != FORMAT or value.get("version") != VERSION:
        raise ConfigurationError(
            f"unsupported configuration format/version; expected {FORMAT} version {VERSION}"
        )
    for key in _ROOT_KEYS - {"format", "version"}:
        if not isinstance(value.get(key), list):
            raise ConfigurationError(f"{key} must be a list")
    return value


def _build_staging(root: Path, value: dict[str, Any]) -> None:
    RepositoryDatabase.initialize(root)
    firms = FirmRepository.initialize(root / "firm-catalog")
    profiles = SourceProfileRepository.initialize(
        root / "source-profiles", load_canonical_template()
    )
    try:
        for item in value["firms"]:
            firms.create(_firm_draft(item))
        for item in value["source_profiles"]:
            profiles.publish(_profile_draft(item), None)
        mailing = MailingListRepository(root)
        for item in value["sources"]:
            mailing.configure_source(_mailing_source(item))
        sec = SecRepository(root)
        for item in value["sec_sources"]:
            sec.persist_source(_sec_source(item), None)
        pending = {_object(item, "stream")["stream_id"]: item for item in value["streams"]}
        service = StreamService(StreamRepository(root))
        while pending:
            progressed = False
            for stream_id, item in tuple(pending.items()):
                draft = _stream_draft(item)
                if draft.input_kind == "streams" and any(key in pending for key in draft.input_ids):
                    continue
                service.save(draft)
                del pending[stream_id]
                progressed = True
            if not progressed:
                raise ConfigurationError("stream dependencies are cyclic or unresolved")
    except (KeyError, TypeError, ValueError, StorageError) as error:
        raise ConfigurationError(f"invalid configuration package: {error}") from error


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{label} entry must be an object")
    return value


def _firm_export(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value[key] for key in (
        "firm_id", "canonical_name", "valid_from", "legal_name", "aliases",
        "identifiers", "domains", "headquarters", "jurisdiction", "sector", "industry",
        "technology_focus", "source_hints", "notes", "relevance", "status", "valid_through",
    )}


def _firm_draft(raw: Any) -> FirmDraft:
    value = _object(raw, "firm")
    fields = dict(value)
    fields["identifiers"] = tuple(
        FirmIdentifier(**item) for item in fields.get("identifiers", ())
    )
    fields["source_hints"] = tuple(
        SourceDiscoveryHint(**item) for item in fields.get("source_hints", ())
    )
    for key in ("aliases", "domains", "technology_focus"):
        fields[key] = tuple(fields.get(key, ()))
    fields["status"] = FirmStatus(fields.get("status", "draft"))
    return FirmDraft(**fields)


def _profile_export(value: dict[str, Any]) -> dict[str, Any]:
    return {"firm_id": value["firm_id"], "items": value["items"],
            "operator_notes": value["operator_notes"]}


def _profile_draft(raw: Any) -> SourceProfileDraft:
    value = _object(raw, "source profile")
    items = []
    for raw_item in value.get("items", ()):
        item = _object(raw_item, "source profile item")
        candidates = []
        for raw_candidate in item.get("retrieval_candidates", ()):
            candidate = dict(_object(raw_candidate, "retrieval candidate"))
            candidate["preferred_domains"] = tuple(candidate.get("preferred_domains", ()))
            candidate["discovery_hints"] = tuple(candidate.get("discovery_hints", ()))
            candidates.append(RetrievalCandidate(**candidate))
        items.append(SourceProfileItem(
            item["artifact_id"], bool(item["enabled"]), tuple(candidates),
            str(item.get("operator_notes", "")),
        ))
    return SourceProfileDraft(value["firm_id"], tuple(items), value.get("operator_notes", ""))


def _mailing_source(raw: Any) -> MailingListSource:
    value = _object(raw, "source")
    transport = LoreTransportPolicy(**_object(value.get("transport", {}), "transport"))
    return MailingListSource(
        value["source_id"], value["list_id"], value["display_name"],
        value["archive_base_url"], value.get("provider", "lore-public-inbox"), transport,
    )


def _sec_source(raw: Any) -> SecSourceKnowledge:
    value = dict(_object(raw, "SEC source"))
    value["applicability"] = SecApplicability(value["applicability"])
    return SecSourceKnowledge(**value)


def _stream_draft(raw: Any) -> StreamDraft:
    value = _object(raw, "stream")
    fields = dict(value)
    fields["input_ids"] = tuple(fields.get("input_ids", ()))
    return StreamDraft(**fields)


def _semantic_state(connection: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {key: {} for key in (
        "firms", "source_profiles", "sources", "sec_sources", "streams"
    )}
    for row in connection.execute(
        "SELECT f.firm_id,r.canonical_json FROM firms f JOIN firm_revisions r "
        "ON r.revision_id=f.current_revision_id"
    ):
        result["firms"][str(row[0])] = _firm_export(_json(str(row[1])))
    for row in connection.execute(
        "SELECT p.firm_id,r.canonical_json FROM source_profiles p JOIN source_profile_revisions r "
        "ON r.revision_id=p.current_revision_id"
    ):
        result["source_profiles"][str(row[0])] = _profile_export(_json(str(row[1])))
    for category, table, key in (
        ("sources", "mailing_list_sources", "source_id"),
        ("sec_sources", "sec_sources", "firm_id"),
    ):
        for row in connection.execute(f"SELECT {key},canonical_json FROM {table}"):
            result[category][str(row[0])] = _json(str(row[1]))
    for row in connection.execute(
        "SELECT s.stream_id,r.canonical_json FROM artifact_streams s "
        "JOIN artifact_stream_revisions r ON r.revision_id=s.current_revision_id"
    ):
        result["streams"][str(row[0])] = _json(str(row[1]))
    return result


def _semantic_state_from_database(database: RepositoryDatabase) -> dict[str, dict[str, Any]]:
    with database.connect(read_only=True) as connection:
        return _semantic_state(connection)


def _copy_missing(
    target: Any, staging: RepositoryDatabase, existing: dict[str, dict[str, Any]],
    incoming: dict[str, dict[str, Any]],
) -> dict[str, int]:
    missing = {key: set(incoming[key]) - set(existing[key]) for key in incoming}
    with staging.connect(read_only=True) as source:
        _copy_firms(target, source, missing["firms"])
        _copy_profiles(target, source, missing["source_profiles"])
        _copy_sources(target, source, missing["sources"])
        _copy_sec(target, source, missing["sec_sources"])
        _copy_streams(target, source, missing["streams"])
    return {key: len(value) for key, value in missing.items()}


def _rows(connection: Any, query: str, parameters: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    return [tuple(row) for row in connection.execute(query, parameters)]


def _copy_firms(target: Any, source: Any, identities: set[str]) -> None:
    for identity in sorted(identities):
        revision = _rows(
            source, "SELECT current_revision_id FROM firms WHERE firm_id=?", (identity,)
        )[0][0]
        target.execute("INSERT INTO firms VALUES (?,?)", (identity, revision))
        target.execute(
            "INSERT INTO firm_revisions VALUES (?,?,?,?,?,?,?)",
            _rows(source, "SELECT * FROM firm_revisions WHERE revision_id=?", (revision,))[0],
        )
        target.executemany(
            "INSERT INTO firm_identifiers VALUES (?,?,?,?)",
            _rows(source, "SELECT * FROM firm_identifiers WHERE revision_id=?", (revision,)),
        )
        target.executemany(
            "INSERT INTO firm_domains VALUES (?,?)",
            _rows(source, "SELECT * FROM firm_domains WHERE revision_id=?", (revision,)),
        )


def _copy_profiles(target: Any, source: Any, identities: set[str]) -> None:
    for identity in sorted(identities):
        revision = _rows(
            source, "SELECT current_revision_id FROM source_profiles WHERE firm_id=?",
            (identity,),
        )[0][0]
        target.execute("INSERT INTO source_profiles VALUES (?,?)", (identity, revision))
        target.execute(
            "INSERT INTO source_profile_revisions VALUES (?,?,?,?,?,?)",
            _rows(
                source, "SELECT * FROM source_profile_revisions WHERE revision_id=?",
                (revision,),
            )[0],
        )
        target.executemany(
            "INSERT INTO source_profile_items VALUES (?,?,?,?,?)",
            _rows(source, "SELECT * FROM source_profile_items WHERE revision_id=?", (revision,)),
        )
        target.executemany(
            "INSERT INTO retrieval_candidates VALUES (?,?,?,?,?)",
            _rows(source, "SELECT * FROM retrieval_candidates WHERE revision_id=?", (revision,)),
        )


def _copy_sources(target: Any, source: Any, identities: set[str]) -> None:
    for identity in sorted(identities):
        target.execute(
            "INSERT INTO governed_sources VALUES (?,?,?,?)",
            _rows(source, "SELECT * FROM governed_sources WHERE source_id=?", (identity,))[0],
        )
        target.execute(
            "INSERT INTO mailing_list_sources VALUES (?,?,?,?,?)",
            _rows(source, "SELECT * FROM mailing_list_sources WHERE source_id=?", (identity,))[0],
        )


def _copy_sec(target: Any, source: Any, identities: set[str]) -> None:
    for identity in sorted(identities):
        target.execute(
            "INSERT INTO sec_sources VALUES (?,?,?,?,?,?,?,?,?)",
            _rows(source, "SELECT * FROM sec_sources WHERE firm_id=?", (identity,))[0],
        )


def _copy_streams(target: Any, source: Any, identities: set[str]) -> None:
    revisions: list[Any] = []
    for identity in sorted(identities):
        revision = _rows(
            source, "SELECT current_revision_id FROM artifact_streams WHERE stream_id=?",
            (identity,),
        )[0][0]
        revisions.append(revision)
        target.execute("INSERT INTO artifact_streams VALUES (?,?)", (identity, revision))
        target.execute(
            "INSERT INTO artifact_stream_revisions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            _rows(
                source, "SELECT * FROM artifact_stream_revisions WHERE revision_id=?",
                (revision,),
            )[0],
        )
    for revision in revisions:
        target.executemany(
            "INSERT INTO artifact_stream_dependencies VALUES (?,?,?)",
            _rows(
                source, "SELECT * FROM artifact_stream_dependencies WHERE revision_id=?",
                (revision,),
            ),
        )
