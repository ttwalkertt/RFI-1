"""Immutable revision persistence for firm-owned source-profile configuration."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from rfi.source_profiles.contracts import (
    AcquisitionTemplate,
    RetrievalCandidate,
    SourceProfileDraft,
    SourceProfileError,
    SourceProfileItem,
    SourceProfileRevision,
)
from rfi.storage import RepositoryDatabase, StorageError, state_root_for
from rfi.storage.sqlite import canonical_json

_SCHEMA_VERSION = 1
_LEGACY_DIGEST_SCHEMA_VERSION = 1
_UNVERSIONED_DISCOVERY_CLASS_DIGEST_SCHEMA_VERSION = 2
_PROVIDER_NEUTRAL_DIGEST_SCHEMA_VERSION = 4
_CURRENT_DIGEST_SCHEMA_VERSION = _PROVIDER_NEUTRAL_DIGEST_SCHEMA_VERSION
_PROVIDER_DIGEST_FIELDS = (
    "provider",
    "discovery_hint_kind",
    "discovery_hint_value",
)
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_DOMAIN = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)
_WDC_BUSINESSWIRE_SEARCH = (
    "https://www.businesswire.com/newsroom?"
    "keywords=ENTIRE_RELEASE%3Atrue%3Awdc"
)


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SourceProfileRepository:
    """Independent profile authority persisted in shared SQLite state."""

    def __init__(self, root: Path, template: AcquisitionTemplate) -> None:
        self.root = root
        self.revisions_root = root / "revisions"
        self.pointer = root / "catalog.json"
        self._database = RepositoryDatabase(state_root_for(root))
        self.template = template
        self._artifacts = {item.artifact_id: item for item in template.artifacts}
        self._modes = {item.mode: item for item in template.retrieval_modes}

    @classmethod
    def initialize(
        cls, root: Path, template: AcquisitionTemplate
    ) -> SourceProfileRepository:
        """Initialize empty profile state without overwriting existing history."""
        try:
            RepositoryDatabase.initialize(state_root_for(root))
        except StorageError as error:
            raise SourceProfileError(str(error)) from error
        repository = cls(root, template)
        repository.verify()
        return repository

    @classmethod
    def open(cls, root: Path, template: AcquisitionTemplate) -> SourceProfileRepository:
        """Open only state that passes complete chain and template validation."""
        try:
            RepositoryDatabase.open(state_root_for(root))
        except StorageError as error:
            raise SourceProfileError(str(error)) from error
        repository = cls(root, template)
        repository.verify()
        return repository

    def publish(
        self,
        draft: SourceProfileDraft,
        expected_revision_id: str | None,
        fail_before_publish: bool = False,
    ) -> SourceProfileRevision:
        """Atomically publish a first or subsequent immutable profile revision."""
        with self._database.connect(read_only=True) as connection:
            managed = connection.execute(
                "SELECT 1 FROM firm_config_authorities WHERE firm_id=?", (draft.firm_id,)
            ).fetchone()
        if managed is not None:
            raise SourceProfileError(
                f"firm configuration is externally managed and read-only: {draft.firm_id}"
            )
        state = self._state()
        normalized = self.normalize(draft)
        current_id = state["current_revisions"].get(draft.firm_id)
        if current_id != expected_revision_id:
            raise SourceProfileError(
                "invalid source-profile update: current source-profile revision has changed"
            )
        current = self.get(draft.firm_id) if current_id else None
        timestamp = _now()
        revision = self._revision(
            normalized,
            1 if current is None else current.revision_number + 1,
            current_id,
            timestamp if current is None else current.created_at,
            timestamp,
        )
        if fail_before_publish:
            raise SourceProfileError(
                "injected interrupted write before source-profile publication"
            )
        try:
            with self._database.transaction() as connection:
                self._insert_revision(connection, revision)
                if current_id is None:
                    connection.execute(
                        "INSERT INTO source_profiles VALUES (?,?)",
                        (revision.firm_id, revision.source_profile_revision_id),
                    )
                else:
                    changed = connection.execute(
                        "UPDATE source_profiles SET current_revision_id = ? "
                        "WHERE firm_id = ? AND current_revision_id = ?",
                        (
                            revision.source_profile_revision_id,
                            revision.firm_id,
                            current_id,
                        ),
                    ).rowcount
                    if changed != 1:
                        raise SourceProfileError(
                            "invalid source-profile update: current source-profile revision "
                            "has changed"
                        )
                self._database.advance_revision(connection)
        except StorageError as error:
            raise SourceProfileError(str(error)) from error
        return revision

    def validate(self, draft: SourceProfileDraft) -> None:
        """Fail closed on item identity, candidate shape, and deterministic ordering rules."""
        self.normalize(draft)

    def normalize(self, draft: SourceProfileDraft) -> SourceProfileDraft:
        """Return canonical item and candidate ordering after complete validation."""
        if not _IDENTIFIER.fullmatch(draft.firm_id):
            raise SourceProfileError(f"invalid firm identifier: {draft.firm_id}")
        by_id: dict[str, SourceProfileItem] = {}
        for item in draft.items:
            if item.artifact_id in by_id:
                raise SourceProfileError(
                    f"duplicate source-profile artifact: {item.artifact_id}"
                )
            artifact = self._artifacts.get(item.artifact_id)
            if artifact is None:
                raise SourceProfileError(
                    f"unknown canonical artifact identifier: {item.artifact_id}"
                )
            candidates = tuple(
                sorted(
                    (self._candidate(value, artifact.supported_retrieval_modes)
                     for value in item.retrieval_candidates),
                    key=lambda value: value.priority,
                )
            )
            priorities = tuple(value.priority for value in candidates)
            if len(set(priorities)) != len(priorities):
                raise SourceProfileError(
                    f"retrieval candidate priorities must be unique for {item.artifact_id}"
                )
            by_id[item.artifact_id] = SourceProfileItem(
                item.artifact_id, item.enabled, candidates, item.operator_notes.strip()
            )
        ordered = tuple(
            by_id.get(
                artifact.artifact_id,
                SourceProfileItem(artifact.artifact_id, artifact.default_enabled),
            )
            for artifact in self.template.artifacts
        )
        return SourceProfileDraft(draft.firm_id, ordered, draft.operator_notes.strip())

    def get(
        self, firm_id: str, revision_id: str | None = None
    ) -> SourceProfileRevision | None:
        """Return current or historical profile, or None before the first publication."""
        state = self._state()
        history = state["revision_history"].get(firm_id)
        if not history:
            if revision_id is not None:
                raise SourceProfileError(f"unknown source-profile revision: {revision_id}")
            return None
        target = revision_id or state["current_revisions"][firm_id]
        if target not in history:
            raise SourceProfileError(f"unknown source-profile revision: {target}")
        return self._load_revision(target)

    def history(self, firm_id: str) -> tuple[SourceProfileRevision, ...]:
        """Return immutable profile history in ascending revision order."""
        state = self._state()
        return tuple(
            self._load_revision(item) for item in state["revision_history"].get(firm_id, [])
        )

    def verify(self) -> dict[str, int | str]:
        """Fail closed on schema, digest, chain, pointer, template, or orphan inconsistency."""
        state = self._state()
        referenced: set[str] = set()
        revisions = 0
        for firm_id in sorted(state["revision_history"]):
            history = state["revision_history"][firm_id]
            if not _IDENTIFIER.fullmatch(firm_id) or not isinstance(history, list) or not history:
                raise SourceProfileError(f"invalid source-profile history identity: {firm_id}")
            previous: str | None = None
            for number, revision_id in enumerate(history, start=1):
                revision = self._load_revision(revision_id)
                if revision.firm_id != firm_id or revision.revision_number != number:
                    raise SourceProfileError(
                        f"source-profile revision sequence mismatch: {revision_id}"
                    )
                if revision.supersedes_revision_id != previous:
                    raise SourceProfileError(
                        f"source-profile revision chain mismatch: {revision_id}"
                    )
                if self.normalize(self.to_draft(revision)) != self.to_draft(revision):
                    raise SourceProfileError(
                        f"source-profile revision ordering mismatch: {revision_id}"
                    )
                self._validate_digest(revision)
                referenced.add(revision_id)
                previous = revision_id
                revisions += 1
            if state["current_revisions"].get(firm_id) != history[-1]:
                raise SourceProfileError(f"current source-profile revision mismatch: {firm_id}")
        if set(state["current_revisions"]) != set(state["revision_history"]):
            raise SourceProfileError("source-profile current and history firms differ")
        return {
            "profiles": len(state["current_revisions"]),
            "revisions": revisions,
            "result": "PASS",
        }

    @staticmethod
    def to_draft(revision: SourceProfileRevision) -> SourceProfileDraft:
        """Project immutable profile state into editable intent."""
        return SourceProfileDraft(revision.firm_id, revision.items, revision.operator_notes)

    def _candidate(
        self, candidate: RetrievalCandidate, supported_modes: tuple[str, ...]
    ) -> RetrievalCandidate:
        if candidate.mode not in supported_modes:
            raise SourceProfileError(
                f"unsupported retrieval mode {candidate.mode} for canonical artifact"
            )
        if isinstance(candidate.priority, bool) or candidate.priority < 1:
            raise SourceProfileError("retrieval candidate priority must be a positive integer")
        preferred = self._unique_strings(candidate.preferred_domains, "preferred domains")
        hints = self._unique_strings(candidate.discovery_hints, "discovery hints")
        for domain in preferred:
            if not _DOMAIN.fullmatch(domain.casefold()):
                raise SourceProfileError(f"invalid preferred domain: {domain}")
        url = candidate.url.strip()
        if url:
            parsed = urlsplit(url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
            ):
                raise SourceProfileError(f"invalid retrieval URL: {url}")
        normalized = RetrievalCandidate(
            candidate.mode,
            candidate.priority,
            url,
            candidate.locator.strip(),
            tuple(value.casefold() for value in preferred),
            hints,
            candidate.expected_media_type.strip(),
            candidate.parser_hint.strip(),
            candidate.operator_notes.strip(),
            candidate.discovery_class.strip(),
            candidate.provider.strip().casefold(),
            candidate.discovery_hint_kind.strip().casefold(),
            candidate.discovery_hint_value.strip(),
        )
        provider_fields = (
            normalized.provider,
            normalized.discovery_hint_kind,
            normalized.discovery_hint_value,
        )
        if any(provider_fields) and not all(provider_fields):
            raise SourceProfileError(
                "provider-backed retrieval requires provider, discovery hint kind, and value"
            )
        if normalized.provider and normalized.provider not in {
            "stockanalysis", "wdc_press_release"
        }:
            raise SourceProfileError(f"unknown acquisition provider: {normalized.provider}")
        if normalized.provider == "stockanalysis":
            if normalized.discovery_hint_kind != "provider_identifier":
                raise SourceProfileError(
                    "StockAnalysis supports discovery hint kind provider_identifier"
                )
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,15}", normalized.discovery_hint_value):
                raise SourceProfileError("StockAnalysis provider identifier is invalid")
        if normalized.provider == "wdc_press_release" and (
            normalized.discovery_hint_kind != "configured_search_url"
            or normalized.discovery_hint_value != _WDC_BUSINESSWIRE_SEARCH
        ):
            raise SourceProfileError(
                "wdc_press_release requires the configured Business Wire search URL"
            )
        mode = self._modes[candidate.mode]
        values: dict[str, Any] = asdict(normalized)
        populated = {
            key
            for key, value in values.items()
            if key != "mode" and value not in ("", (), [], None)
        }
        unsupported = populated.difference(mode.supported_fields)
        if unsupported:
            raise SourceProfileError(
                f"retrieval mode {mode.mode} does not support fields: "
                f"{', '.join(sorted(unsupported))}"
            )
        missing = set(mode.required_fields).difference(populated)
        if missing:
            raise SourceProfileError(
                f"retrieval mode {mode.mode} requires fields: {', '.join(sorted(missing))}"
            )
        if mode.required_any and not populated.intersection(mode.required_any):
            raise SourceProfileError(
                f"retrieval mode {mode.mode} requires one of: "
                f"{', '.join(mode.required_any)}"
            )
        return normalized

    @staticmethod
    def _unique_strings(values: tuple[str, ...], label: str) -> tuple[str, ...]:
        result = tuple(value.strip() for value in values if value.strip())
        if len({value.casefold() for value in result}) != len(result):
            raise SourceProfileError(f"retrieval candidate {label} must be unique")
        return result

    def _revision(
        self,
        draft: SourceProfileDraft,
        number: int,
        supersedes: str | None,
        created_at: str,
        updated_at: str,
        digest_schema_version: int = _CURRENT_DIGEST_SCHEMA_VERSION,
    ) -> SourceProfileRevision:
        material: dict[str, Any] = {
            **asdict(draft),
            "revision_number": number,
            "created_at": created_at,
            "updated_at": updated_at,
            "supersedes_revision_id": supersedes,
        }
        if digest_schema_version == _LEGACY_DIGEST_SCHEMA_VERSION:
            for item in material["items"]:
                for candidate in item["retrieval_candidates"]:
                    candidate.pop("discovery_class")
                    for field in _PROVIDER_DIGEST_FIELDS:
                        candidate.pop(field)
        elif digest_schema_version == _UNVERSIONED_DISCOVERY_CLASS_DIGEST_SCHEMA_VERSION:
            for item in material["items"]:
                for candidate in item["retrieval_candidates"]:
                    for field in _PROVIDER_DIGEST_FIELDS:
                        candidate.pop(field)
        elif digest_schema_version == 3:
            for item in material["items"]:
                for candidate in item["retrieval_candidates"]:
                    for field in _PROVIDER_DIGEST_FIELDS:
                        candidate.pop(field)
            material["digest_schema_version"] = digest_schema_version
        elif digest_schema_version == _CURRENT_DIGEST_SCHEMA_VERSION:
            material["digest_schema_version"] = digest_schema_version
        else:
            raise SourceProfileError(
                f"unsupported source-profile digest schema: {digest_schema_version}"
            )
        revision_id = "source-profile-revision-" + hashlib.sha256(
            _canonical(material)
        ).hexdigest()
        return SourceProfileRevision(
            draft.firm_id,
            revision_id,
            number,
            draft.items,
            draft.operator_notes,
            created_at,
            updated_at,
            supersedes,
            digest_schema_version,
        )

    def _validate_digest(self, revision: SourceProfileRevision) -> None:
        expected = self._revision(
            self.to_draft(revision),
            revision.revision_number,
            revision.supersedes_revision_id,
            revision.created_at,
            revision.updated_at,
            revision.digest_schema_version,
        ).source_profile_revision_id
        if expected != revision.source_profile_revision_id:
            raise SourceProfileError(
                f"source-profile revision digest mismatch: "
                f"{revision.source_profile_revision_id}"
            )

    def _state(self) -> dict[str, Any]:
        with self._database.connect(read_only=True) as connection:
            current = connection.execute(
                "SELECT firm_id,current_revision_id FROM source_profiles ORDER BY firm_id"
            ).fetchall()
            revisions = connection.execute(
                "SELECT firm_id,revision_id FROM source_profile_revisions "
                "ORDER BY firm_id,revision_number"
            ).fetchall()
        history: dict[str, list[str]] = {}
        for row in revisions:
            history.setdefault(str(row[0]), []).append(str(row[1]))
        return {
            "schema_version": _SCHEMA_VERSION,
            "current_revisions": {str(row[0]): str(row[1]) for row in current},
            "revision_history": history,
        }

    def _revision_path(self, revision_id: str) -> Path:
        if not revision_id.startswith("source-profile-revision-"):
            raise SourceProfileError("unsafe source-profile revision path rejected")
        return self.revisions_root / f"{revision_id}.json"

    def _write_revision(self, revision: SourceProfileRevision) -> None:
        raise SourceProfileError("source-profile revisions require transactional publication")

    def _load_revision(self, revision_id: str) -> SourceProfileRevision:
        with self._database.connect(read_only=True) as connection:
            row = connection.execute(
                "SELECT canonical_json FROM source_profile_revisions WHERE revision_id = ?",
                (revision_id,),
            ).fetchone()
        if row is None:
            raise SourceProfileError(f"unknown source-profile revision: {revision_id}")
        try:
            value = json.loads(str(row[0]))
        except json.JSONDecodeError as error:
            raise SourceProfileError("cannot read source-profile structured state") from error

        candidates = tuple(
            candidate
            for item in value.get("items", ())
            for candidate in item.get("retrieval_candidates", ())
        )
        candidate_shapes = {
            "discovery_class" in candidate
            for candidate in candidates
        }
        if len(candidate_shapes) > 1:
            raise SourceProfileError(
                "source-profile revision mixes candidate digest schemas"
            )
        implicit_schema = (
            _UNVERSIONED_DISCOVERY_CLASS_DIGEST_SCHEMA_VERSION
            if candidate_shapes == {True}
            else _LEGACY_DIGEST_SCHEMA_VERSION
        )
        if "digest_schema_version" in value and value["digest_schema_version"] not in {
            3, _CURRENT_DIGEST_SCHEMA_VERSION
        }:
            raise SourceProfileError("source-profile digest schema marker is not authenticated")
        digest_schema_version = value.get("digest_schema_version", implicit_schema)
        if digest_schema_version not in {
            _LEGACY_DIGEST_SCHEMA_VERSION,
            _UNVERSIONED_DISCOVERY_CLASS_DIGEST_SCHEMA_VERSION,
            _CURRENT_DIGEST_SCHEMA_VERSION,
            3,
        }:
            raise SourceProfileError(
                f"unsupported source-profile digest schema: {digest_schema_version}"
            )
        provider_shapes = {
            tuple(field in candidate for field in _PROVIDER_DIGEST_FIELDS)
            for candidate in candidates
        }
        if any(any(shape) and not all(shape) for shape in provider_shapes):
            raise SourceProfileError(
                "source-profile candidate has partial provider digest fields"
            )
        if digest_schema_version <= 3 and any(all(shape) for shape in provider_shapes):
            raise SourceProfileError(
                "legacy source-profile candidate contains provider digest fields"
            )
        if digest_schema_version == _CURRENT_DIGEST_SCHEMA_VERSION and any(
            not all(shape) for shape in provider_shapes
        ):
            raise SourceProfileError(
                "current source-profile candidate lacks provider digest fields"
            )
        self._validate_persisted_digest(value, digest_schema_version)

        def candidate(value: dict[str, Any]) -> RetrievalCandidate:
            fields = dict(value)
            has_discovery_class = "discovery_class" in fields
            if digest_schema_version == _LEGACY_DIGEST_SCHEMA_VERSION and has_discovery_class:
                raise SourceProfileError(
                    "legacy source-profile candidate contains discovery_class"
                )
            if digest_schema_version in {
                _UNVERSIONED_DISCOVERY_CLASS_DIGEST_SCHEMA_VERSION,
                3,
                _CURRENT_DIGEST_SCHEMA_VERSION,
            } and not has_discovery_class:
                raise SourceProfileError(
                    "current source-profile candidate lacks discovery_class"
                )
            fields["preferred_domains"] = tuple(fields.get("preferred_domains", ()))
            fields["discovery_hints"] = tuple(fields.get("discovery_hints", ()))
            return RetrievalCandidate(**fields)

        value["items"] = tuple(
            SourceProfileItem(
                item["artifact_id"],
                item["enabled"],
                tuple(
                    candidate(value) for value in item["retrieval_candidates"]
                ),
                item.get("operator_notes", ""),
            )
            for item in value["items"]
        )
        value["digest_schema_version"] = digest_schema_version
        return SourceProfileRevision(**value)

    @staticmethod
    def _validate_persisted_digest(
        value: dict[str, Any], digest_schema_version: int
    ) -> None:
        """Authenticate exact stored JSON before current dataclass defaults are applied."""
        revision_id = value.get("source_profile_revision_id")
        if not isinstance(revision_id, str):
            raise SourceProfileError("source-profile revision identity is malformed")
        has_marker = "digest_schema_version" in value
        if has_marker != (digest_schema_version >= 3):
            raise SourceProfileError(
                "source-profile digest schema marker is not authenticated"
            )
        material = {
            key: item
            for key, item in value.items()
            if key != "source_profile_revision_id"
        }
        expected = "source-profile-revision-" + hashlib.sha256(
            _canonical(material)
        ).hexdigest()
        if expected != revision_id:
            raise SourceProfileError(
                f"source-profile revision digest mismatch: {revision_id}"
            )

    def _insert_revision(self, connection: Any, revision: SourceProfileRevision) -> None:
        """Insert one immutable revision inside a caller-owned transaction."""
        payload = canonical_json(asdict(revision))
        connection.execute(
            "INSERT INTO source_profile_revisions VALUES (?,?,?,?,?,?)",
            (
                revision.source_profile_revision_id,
                revision.firm_id,
                revision.revision_number,
                revision.supersedes_revision_id,
                revision.created_at,
                payload,
            ),
        )
        for ordinal, item in enumerate(revision.items):
            connection.execute(
                "INSERT INTO source_profile_items VALUES (?,?,?,?,?)",
                (
                    revision.source_profile_revision_id,
                    item.artifact_id,
                    ordinal,
                    int(item.enabled),
                    item.operator_notes,
                ),
            )
            connection.executemany(
                "INSERT INTO retrieval_candidates VALUES (?,?,?,?,?)",
                (
                    (
                        revision.source_profile_revision_id,
                        item.artifact_id,
                        candidate.priority,
                        candidate.mode,
                        canonical_json(asdict(candidate)),
                    )
                    for candidate in item.retrieval_candidates
                ),
            )
