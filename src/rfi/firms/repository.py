"""Immutable-revision JSON persistence for the independent target-firm catalog."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from rfi.firms.contracts import (
    FirmDraft,
    FirmError,
    FirmIdentifier,
    FirmRevision,
    FirmStatus,
    SourceDiscoveryHint,
)
from rfi.storage import RepositoryDatabase, StorageError, state_root_for
from rfi.storage.sqlite import canonical_json

_SCHEMA_VERSION = 2
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_TOKEN = re.compile(r"^[a-z][a-z0-9_-]*$")
_DOMAIN = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_date(value: str | None, label: str, required: bool = False) -> date | None:
    if value is None or value == "":
        if required:
            raise FirmError(f"{label} is required")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise FirmError(f"{label} must be an ISO date") from error


def _unique(values: tuple[str, ...], label: str) -> tuple[str, ...]:
    cleaned = tuple(value.strip() for value in values if value.strip())
    if len({value.casefold() for value in cleaned}) != len(cleaned):
        raise FirmError(f"{label} must not contain duplicates")
    return cleaned


class FirmRepository:
    """Firm authority with immutable revisions in shared SQLite state."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.revisions_root = root / "revisions"  # retained only as a legacy diagnostic path
        self.pointer = root / "catalog.json"  # retained only as a legacy diagnostic path
        self._database = RepositoryDatabase(state_root_for(root))

    @classmethod
    def initialize(cls, root: Path) -> FirmRepository:
        """Initialize empty state without overwriting an existing catalog."""
        try:
            RepositoryDatabase.initialize(state_root_for(root))
        except StorageError as error:
            raise FirmError(str(error)) from error
        repository = cls(root)
        repository.verify()
        return repository

    @classmethod
    def open(cls, root: Path) -> FirmRepository:
        """Open only state that passes complete integrity validation."""
        try:
            RepositoryDatabase.open(state_root_for(root))
        except StorageError as error:
            raise FirmError(str(error)) from error
        repository = cls(root)
        repository.verify()
        return repository

    def create(self, draft: FirmDraft, fail_before_publish: bool = False) -> FirmRevision:
        """Create a firm identity and its first immutable revision."""
        self.validate(draft)
        if draft.firm_id in self._state()["current_revisions"]:
            raise FirmError(f"duplicate firm identifier: {draft.firm_id}")
        revision = self._revision(draft, 1, None, _now(), _now())
        if fail_before_publish:
            raise FirmError("injected interrupted write before firm catalog publication")
        self._publish(revision, create=True)
        return revision

    def create_batch(
        self,
        drafts: tuple[FirmDraft, ...],
        fail_after_revision_count: int | None = None,
    ) -> tuple[FirmRevision, ...]:
        """Publish first revisions together or restore the exact pre-call repository."""
        state = self._state()
        ordered = tuple(sorted(drafts, key=lambda item: item.firm_id))
        if not ordered:
            return ()
        if len({draft.firm_id for draft in ordered}) != len(ordered):
            raise FirmError("batch contains duplicate firm identifiers")
        planned_identifiers: dict[tuple[str, str, str], str] = {}
        planned_domains: dict[str, str] = {}
        for draft in ordered:
            self.validate(draft)
            if draft.firm_id in state["current_revisions"]:
                raise FirmError(f"duplicate firm identifier: {draft.firm_id}")
            for identifier in draft.identifiers:
                key = self._identifier_key(identifier)
                owner = planned_identifiers.get(key)
                if owner is not None:
                    raise FirmError(
                        f"conflicting firm identifier in batch belongs to {owner} and "
                        f"{draft.firm_id}"
                    )
                planned_identifiers[key] = draft.firm_id
            for domain in draft.domains:
                key = domain.casefold()
                owner = planned_domains.get(key)
                if owner is not None:
                    raise FirmError(
                        f"conflicting firm domain in batch belongs to {owner} and "
                        f"{draft.firm_id}"
                    )
                planned_domains[key] = draft.firm_id
        timestamp = _now()
        revisions = tuple(
            self._revision(draft, 1, None, timestamp, timestamp) for draft in ordered
        )
        try:
            with self._database.transaction() as connection:
                for count, revision in enumerate(revisions, start=1):
                    self._insert_revision(connection, revision)
                    connection.execute(
                        "INSERT INTO firms(firm_id,current_revision_id) VALUES (?,?)",
                        (revision.firm_id, revision.revision_id),
                    )
                    if fail_after_revision_count is not None and count >= fail_after_revision_count:
                        raise FirmError("injected batch persistence failure before publication")
                self._database.advance_revision(connection)
        except StorageError as error:
            raise FirmError(str(error)) from error
        return revisions

    def validate(self, draft: FirmDraft, current_firm_id: str | None = None) -> None:
        """Validate local fields plus identifiers and domains unique among current firms."""
        self._validate_draft(draft)
        identifiers = {self._identifier_key(item) for item in draft.identifiers}
        domains = {item.casefold() for item in draft.domains}
        for other in self.lookup():
            if other.firm_id == (current_firm_id or draft.firm_id):
                continue
            overlap = identifiers.intersection(
                self._identifier_key(item) for item in other.identifiers
            )
            if overlap:
                kind, market, value = sorted(overlap)[0]
                qualifier = f" on {market}" if market else ""
                raise FirmError(
                    f"conflicting firm identifier: {kind} {value}{qualifier} belongs to "
                    f"{other.firm_id}"
                )
            domain_overlap = domains.intersection(value.casefold() for value in other.domains)
            if domain_overlap:
                raise FirmError(
                    f"conflicting firm domain: {sorted(domain_overlap)[0]} belongs to "
                    f"{other.firm_id}"
                )

    def revise(
        self,
        firm_id: str,
        draft: FirmDraft,
        expected_revision_id: str,
        fail_before_publish: bool = False,
    ) -> FirmRevision:
        """Append a revision using optimistic current-revision validation."""
        if firm_id != draft.firm_id:
            raise FirmError("a revision cannot change the stable firm identifier")
        state = self._state()
        current = self.get(firm_id)
        if current.revision_id != expected_revision_id:
            raise FirmError("invalid revision update: current firm revision has changed")
        self.validate(draft, firm_id)
        revision = self._revision(
            draft,
            current.revision_number + 1,
            current.revision_id,
            current.created_at,
            _now(),
        )
        if fail_before_publish:
            raise FirmError("injected interrupted write before firm catalog publication")
        self._publish(revision, create=False)
        return revision

    def retire(self, firm_id: str, expected_revision_id: str) -> FirmRevision:
        """Retire through a new immutable revision."""
        current = self.get(firm_id)
        return self.revise(
            firm_id,
            self.to_draft(current, FirmStatus.RETIRED),
            expected_revision_id,
        )

    def get(self, firm_id: str, revision_id: str | None = None) -> FirmRevision:
        """Return a current or named immutable revision."""
        state = self._state()
        history = state["revision_history"].get(firm_id)
        if not history:
            raise FirmError(f"unknown firm: {firm_id}")
        target = revision_id or state["current_revisions"][firm_id]
        if target not in history:
            raise FirmError(f"unknown firm revision: {target}")
        return self._load_revision(target)

    def history(self, firm_id: str) -> tuple[FirmRevision, ...]:
        """Return all immutable revisions in ascending order."""
        state = self._state()
        identifiers = state["revision_history"].get(firm_id)
        if not identifiers:
            raise FirmError(f"unknown firm: {firm_id}")
        return tuple(self._load_revision(item) for item in identifiers)

    def lookup(
        self,
        query: str = "",
        status: FirmStatus | None = None,
        sector: str | None = None,
        industry: str | None = None,
        minimum_relevance: float | None = None,
    ) -> tuple[FirmRevision, ...]:
        """Search current records by identity, recognition, classification, and notes."""
        needle = query.strip().casefold()
        result: list[FirmRevision] = []
        state = self._state()
        for firm_id in sorted(state["current_revisions"]):
            item = self.get(firm_id)
            searchable = " ".join(
                (
                    item.firm_id,
                    item.canonical_name,
                    item.legal_name,
                    item.headquarters,
                    item.jurisdiction,
                    item.sector,
                    item.industry,
                    item.notes,
                    str(item.relevance),
                    *item.aliases,
                    *item.domains,
                    *item.technology_focus,
                    *(value.value for value in item.identifiers),
                    *(value.value for value in item.source_hints),
                )
            ).casefold()
            if needle and needle not in searchable:
                continue
            if status and item.status != status:
                continue
            if sector and sector.casefold() not in item.sector.casefold():
                continue
            if industry and industry.casefold() not in item.industry.casefold():
                continue
            if minimum_relevance is not None and item.relevance < minimum_relevance:
                continue
            result.append(item)
        return tuple(sorted(result, key=lambda item: (-item.relevance, item.firm_id)))

    def verify(self) -> dict[str, int | str]:
        """Fail closed on schema, chain, digest, pointer, or file inconsistencies."""
        state = self._state()
        referenced: set[str] = set()
        revisions = 0
        for firm_id, history in state["revision_history"].items():
            if not _IDENTIFIER.fullmatch(firm_id) or not history:
                raise FirmError(f"invalid firm catalog history identity: {firm_id}")
            previous: str | None = None
            for number, revision_id in enumerate(history, start=1):
                revision = self._load_revision(revision_id)
                if revision.firm_id != firm_id or revision.revision_number != number:
                    raise FirmError(f"firm revision sequence mismatch: {revision_id}")
                if revision.supersedes_revision_id != previous:
                    raise FirmError(f"firm revision chain mismatch: {revision_id}")
                self._validate_revision_digest(revision)
                self._validate_draft(self.to_draft(revision))
                previous = revision_id
                referenced.add(revision_id)
                revisions += 1
            if state["current_revisions"].get(firm_id) != history[-1]:
                raise FirmError(f"current firm revision mismatch: {firm_id}")
        return {"firms": len(state["current_revisions"]), "revisions": revisions, "result": "PASS"}

    @staticmethod
    def to_draft(revision: FirmRevision, status: FirmStatus | None = None) -> FirmDraft:
        """Project immutable state into editable intent."""
        fields = asdict(revision)
        for name in (
            "revision_id",
            "revision_number",
            "created_at",
            "updated_at",
            "supersedes_revision_id",
        ):
            fields.pop(name)
        fields["status"] = status or revision.status
        fields["identifiers"] = revision.identifiers
        fields["source_hints"] = revision.source_hints
        return FirmDraft(**fields)

    def _validate_draft(self, draft: FirmDraft) -> None:
        if not _IDENTIFIER.fullmatch(draft.firm_id):
            raise FirmError(f"invalid firm identifier: {draft.firm_id}")
        if not draft.canonical_name.strip():
            raise FirmError("canonical name is required")
        start = _parse_date(draft.valid_from, "valid_from", required=True)
        end = _parse_date(draft.valid_through, "valid_through")
        if start and end and end < start:
            raise FirmError("invalid firm validity interval")
        aliases = _unique(draft.aliases, "aliases")
        domains = _unique(tuple(value.casefold() for value in draft.domains), "domains")
        _unique(draft.technology_focus, "technology focus")
        if draft.canonical_name.casefold() in {value.casefold() for value in aliases}:
            raise FirmError("aliases must not repeat the canonical name")
        for domain in domains:
            if not _DOMAIN.fullmatch(domain):
                raise FirmError(f"invalid domain: {domain}")
        identifier_keys: set[tuple[str, str, str]] = set()
        for item in draft.identifiers:
            if not _TOKEN.fullmatch(item.kind):
                raise FirmError(f"invalid identifier kind: {item.kind}")
            if not item.value.strip():
                raise FirmError("firm identifier value is required")
            key = self._identifier_key(item)
            if key in identifier_keys:
                raise FirmError("identifiers must not contain duplicates")
            identifier_keys.add(key)
        for hint in draft.source_hints:
            if not _TOKEN.fullmatch(hint.kind) or not hint.value.strip():
                raise FirmError("source hints require a valid kind and value")
        if (
            isinstance(draft.relevance, bool)
            or not isinstance(draft.relevance, (int, float))
            or not math.isfinite(draft.relevance)
            or not 0 <= draft.relevance <= 100
        ):
            raise FirmError("relevance must be a finite number from 0 through 100")

    @staticmethod
    def _identifier_key(item: FirmIdentifier) -> tuple[str, str, str]:
        return (item.kind.casefold(), (item.market or "").casefold(), item.value.casefold())

    def _revision(
        self,
        draft: FirmDraft,
        number: int,
        supersedes: str | None,
        created_at: str,
        updated_at: str,
    ) -> FirmRevision:
        material = {
            **asdict(draft),
            "status": draft.status.value,
            "revision_number": number,
            "created_at": created_at,
            "updated_at": updated_at,
            "supersedes_revision_id": supersedes,
        }
        revision_id = "firm-revision-" + hashlib.sha256(_canonical(material)).hexdigest()
        fields = asdict(draft)
        fields["status"] = draft.status
        fields["identifiers"] = draft.identifiers
        fields["source_hints"] = draft.source_hints
        return FirmRevision(
            revision_id=revision_id,
            revision_number=number,
            created_at=created_at,
            updated_at=updated_at,
            supersedes_revision_id=supersedes,
            **fields,
        )

    def _validate_revision_digest(self, revision: FirmRevision) -> None:
        expected = self._revision(
            self.to_draft(revision),
            revision.revision_number,
            revision.supersedes_revision_id,
            revision.created_at,
            revision.updated_at,
        ).revision_id
        if expected == revision.revision_id:
            return
        draft = self.to_draft(revision)
        material = {
            **asdict(draft),
            "status": draft.status.value,
            "revision_number": revision.revision_number,
            "created_at": revision.created_at,
            "updated_at": revision.updated_at,
            "supersedes_revision_id": revision.supersedes_revision_id,
        }
        material.pop("relevance")
        legacy = "firm-revision-" + hashlib.sha256(_canonical(material)).hexdigest()
        if revision.relevance != 0 or legacy != revision.revision_id:
            raise FirmError(f"firm revision digest mismatch: {revision.revision_id}")

    def _state(self) -> dict[str, Any]:
        try:
            with self._database.connect(read_only=True) as connection:
                current = connection.execute(
                    "SELECT firm_id,current_revision_id FROM firms ORDER BY firm_id"
                ).fetchall()
                revisions = connection.execute(
                    "SELECT firm_id,revision_id FROM firm_revisions "
                    "ORDER BY firm_id,revision_number"
                ).fetchall()
        except Exception as error:
            raise FirmError("cannot read firm catalog state") from error
        history: dict[str, list[str]] = {}
        for row in revisions:
            history.setdefault(str(row[0]), []).append(str(row[1]))
        return {
            "schema_version": _SCHEMA_VERSION,
            "current_revisions": {str(row[0]): str(row[1]) for row in current},
            "revision_history": history,
        }

    def _revision_path(self, revision_id: str) -> Path:
        if not revision_id.startswith("firm-revision-"):
            raise FirmError("unsafe firm revision path rejected")
        return self.revisions_root / f"{revision_id}.json"

    def _write_revision(self, revision: FirmRevision) -> None:
        self._publish(revision, create=revision.revision_number == 1)

    def _load_revision(self, revision_id: str) -> FirmRevision:
        with self._database.connect(read_only=True) as connection:
            row = connection.execute(
                "SELECT canonical_json FROM firm_revisions WHERE revision_id = ?",
                (revision_id,),
            ).fetchone()
        if row is None:
            raise FirmError(f"unknown firm revision: {revision_id}")
        try:
            value = json.loads(str(row[0]))
        except json.JSONDecodeError as error:
            raise FirmError("cannot read firm revision structured state") from error
        value.setdefault("relevance", 0.0)
        value["status"] = FirmStatus(value["status"])
        value["aliases"] = tuple(value["aliases"])
        value["domains"] = tuple(value["domains"])
        value["technology_focus"] = tuple(value["technology_focus"])
        value["identifiers"] = tuple(FirmIdentifier(**item) for item in value["identifiers"])
        value["source_hints"] = tuple(
            SourceDiscoveryHint(**item) for item in value["source_hints"]
        )
        return FirmRevision(**value)

    def _publish(self, revision: FirmRevision, *, create: bool) -> None:
        try:
            with self._database.transaction() as connection:
                self._insert_revision(connection, revision)
                if create:
                    connection.execute(
                        "INSERT INTO firms(firm_id,current_revision_id) VALUES (?,?)",
                        (revision.firm_id, revision.revision_id),
                    )
                else:
                    changed = connection.execute(
                        "UPDATE firms SET current_revision_id = ? WHERE firm_id = ? "
                        "AND current_revision_id = ?",
                        (
                            revision.revision_id,
                            revision.firm_id,
                            revision.supersedes_revision_id,
                        ),
                    ).rowcount
                    if changed != 1:
                        raise FirmError(
                            "invalid revision update: current firm revision has changed"
                        )
                self._database.advance_revision(connection)
        except StorageError as error:
            raise FirmError(str(error)) from error

    def _insert_revision(self, connection: Any, revision: FirmRevision) -> None:
        payload = canonical_json(asdict(revision))
        prior = connection.execute(
            "SELECT canonical_json FROM firm_revisions WHERE revision_id = ?",
            (revision.revision_id,),
        ).fetchone()
        if prior is not None:
            if str(prior[0]) != payload:
                raise FirmError(f"attempted firm historical mutation: {revision.revision_id}")
            return
        connection.execute(
            "INSERT INTO firm_revisions VALUES (?,?,?,?,?,?,?)",
            (
                revision.revision_id,
                revision.firm_id,
                revision.revision_number,
                revision.supersedes_revision_id,
                revision.status.value,
                revision.created_at,
                payload,
            ),
        )
        connection.executemany(
            "INSERT INTO firm_identifiers VALUES (?,?,?,?)",
            (
                (
                    revision.revision_id,
                    item.kind,
                    item.market or "",
                    item.value,
                )
                for item in revision.identifiers
            ),
        )
        connection.executemany(
            "INSERT INTO firm_domains VALUES (?,?)",
            ((revision.revision_id, item) for item in revision.domains),
        )
