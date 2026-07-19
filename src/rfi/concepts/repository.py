"""Immutable-revision JSON persistence for the independent concept catalog."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from rfi.concepts.contracts import (
    ConceptDraft,
    ConceptError,
    ConceptRevision,
    ConceptStatus,
    MethodKind,
    ObservationMethod,
)
from rfi.storage import RepositoryDatabase, StorageError
from rfi.storage.sqlite import canonical_json

_SCHEMA_VERSION = 1
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_METHOD_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._:/-][a-z0-9]+)*$")
_RESULT_SHAPES = {
    "boolean",
    "category",
    "event",
    "integer",
    "narrative",
    "quantity",
    "range",
    "ratio",
    "relationship",
    "state",
    "structured",
}
_OPERATIONS = {
    "add",
    "divide",
    "margin-from-cost",
    "multiply",
    "percentage",
    "subtract",
}


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_date(value: str | None, label: str, required: bool = False) -> date | None:
    if value is None:
        if required:
            raise ConceptError(f"{label} is required")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ConceptError(f"{label} must be an ISO date") from error


def _unique(values: tuple[str, ...], label: str) -> tuple[str, ...]:
    cleaned = tuple(item.strip() for item in values if item.strip())
    if len(set(item.casefold() for item in cleaned)) != len(cleaned):
        raise ConceptError(f"{label} must not contain duplicates")
    return cleaned


class MethodRegistry:
    """Validation boundary for built-in and explicitly registered extension method kinds."""

    def __init__(self, extension_kinds: tuple[str, ...] = ()) -> None:
        self.kinds = {item.value for item in MethodKind} | set(extension_kinds)

    def validate(self, method: ObservationMethod) -> ObservationMethod:
        """Validate common fields and bounded built-in configuration."""
        if not _METHOD_IDENTIFIER.fullmatch(method.method_id):
            raise ConceptError(f"invalid method identifier: {method.method_id}")
        if method.kind not in self.kinds:
            raise ConceptError(f"unknown method kind: {method.kind}")
        if not method.name.strip():
            raise ConceptError(f"method name is required: {method.method_id}")
        if method.result_shape not in _RESULT_SHAPES and not method.result_shape.startswith(
            "extension:"
        ):
            raise ConceptError(f"unknown result shape: {method.result_shape}")
        self._valid_interval(method.valid_from, method.valid_through, method.method_id)
        if not isinstance(method.configuration, dict):
            raise ConceptError(f"method configuration must be an object: {method.method_id}")
        if method.kind == MethodKind.DETERMINISTIC:
            self._validate_deterministic(method)
        return method

    def _valid_interval(
        self,
        valid_from: str | None,
        valid_through: str | None,
        label: str,
    ) -> None:
        start = _parse_date(valid_from, f"{label} valid_from")
        end = _parse_date(valid_through, f"{label} valid_through")
        if start and end and end < start:
            raise ConceptError(f"invalid method validity interval: {label}")

    def _validate_deterministic(self, method: ObservationMethod) -> None:
        operation = method.configuration.get("operation")
        if operation not in _OPERATIONS:
            raise ConceptError(
                f"invalid deterministic operation for {method.method_id}: {operation}"
            )
        inputs = method.configuration.get("inputs")
        if not isinstance(inputs, list) or len(inputs) < 1:
            raise ConceptError(f"deterministic inputs are required: {method.method_id}")
        roles: list[str] = []
        for item in inputs:
            if not isinstance(item, dict):
                raise ConceptError(f"deterministic input must be an object: {method.method_id}")
            role = item.get("role")
            concept_id = item.get("concept_id")
            if not isinstance(role, str) or not role.strip():
                raise ConceptError(f"deterministic input role is required: {method.method_id}")
            if not isinstance(concept_id, str) or not _IDENTIFIER.fullmatch(concept_id):
                raise ConceptError(f"deterministic input concept is invalid: {method.method_id}")
            roles.append(role)
        if len(roles) != len(set(roles)):
            raise ConceptError(f"deterministic input roles must be unique: {method.method_id}")
        if set(method.required_inputs) != set(roles):
            raise ConceptError(
                f"required_inputs must match deterministic roles: {method.method_id}"
            )
        if operation in {"divide", "percentage", "subtract"} and len(roles) != 2:
            raise ConceptError(f"deterministic operation requires two inputs: {method.method_id}")
        if operation == "margin-from-cost" and set(roles) != {
            "revenue",
            "cost_of_revenue",
        }:
            raise ConceptError(
                f"margin-from-cost requires revenue and cost_of_revenue: {method.method_id}"
            )


class ConceptRepository:
    """Concept authority with immutable revisions in shared SQLite state."""

    def __init__(self, root: Path, extension_method_kinds: tuple[str, ...] = ()) -> None:
        self.root = root
        self.revisions_root = root / "revisions"
        self.pointer = root / "catalog.json"
        self.registry = MethodRegistry(extension_method_kinds)
        self._database = RepositoryDatabase(root)

    @classmethod
    def initialize(
        cls,
        root: Path,
        extension_method_kinds: tuple[str, ...] = (),
    ) -> ConceptRepository:
        """Initialize an empty catalog without overwriting existing state."""
        try:
            RepositoryDatabase.initialize(root)
        except StorageError as error:
            raise ConceptError(str(error)) from error
        repository = cls(root, extension_method_kinds)
        repository.verify()
        return repository

    @classmethod
    def open(
        cls,
        root: Path,
        extension_method_kinds: tuple[str, ...] = (),
    ) -> ConceptRepository:
        """Open only state that passes complete integrity validation."""
        try:
            RepositoryDatabase.open(root)
        except StorageError as error:
            raise ConceptError(str(error)) from error
        repository = cls(root, extension_method_kinds)
        repository.verify()
        return repository

    def create(
        self,
        draft: ConceptDraft,
        fail_before_publish: bool = False,
    ) -> ConceptRevision:
        """Create a stable concept identity and its first immutable revision."""
        self._validate_draft(draft)
        if draft.concept_id in self._state()["current_revisions"]:
            raise ConceptError(f"duplicate concept identifier: {draft.concept_id}")
        revision = self._revision(draft, 1, None, _now(), _now())
        if fail_before_publish:
            raise ConceptError("injected interrupted write before catalog publication")
        self._publish(revision, create=True)
        return revision

    def validate(self, draft: ConceptDraft) -> None:
        """Validate a definition through the public catalog contract without mutation."""
        self._validate_draft(draft)

    def revise(
        self,
        concept_id: str,
        draft: ConceptDraft,
        expected_revision_id: str,
        fail_before_publish: bool = False,
    ) -> ConceptRevision:
        """Append a revision using optimistic current-revision validation."""
        if concept_id != draft.concept_id:
            raise ConceptError("a revision cannot change the stable concept identifier")
        current = self.get(concept_id)
        if current.revision_id != expected_revision_id:
            raise ConceptError("invalid revision update: current revision has changed")
        self._validate_draft(draft)
        revision = self._revision(
            draft,
            current.revision_number + 1,
            current.revision_id,
            current.created_at,
            _now(),
        )
        if fail_before_publish:
            raise ConceptError("injected interrupted write before catalog publication")
        self._publish(revision, create=False)
        return revision

    def retire(self, concept_id: str, expected_revision_id: str) -> ConceptRevision:
        """Retire through a new revision without deleting historical meaning."""
        current = self.get(concept_id)
        draft = self.to_draft(current, status=ConceptStatus.RETIRED)
        return self.revise(concept_id, draft, expected_revision_id)

    def get(self, concept_id: str, revision_id: str | None = None) -> ConceptRevision:
        """Return the current or named immutable revision."""
        state = self._state()
        history = state["revision_history"].get(concept_id)
        if not history:
            raise ConceptError(f"unknown concept: {concept_id}")
        target = revision_id or state["current_revisions"][concept_id]
        if target not in history:
            raise ConceptError(f"unknown concept revision: {target}")
        return self._load_revision(target)

    def history(self, concept_id: str) -> tuple[ConceptRevision, ...]:
        """Return revision history without allowing historical mutation."""
        state = self._state()
        identifiers = state["revision_history"].get(concept_id)
        if not identifiers:
            raise ConceptError(f"unknown concept: {concept_id}")
        return tuple(self._load_revision(item) for item in identifiers)

    def lookup(
        self,
        query: str = "",
        tag: str | None = None,
        status: ConceptStatus | None = None,
        valid_on: str | None = None,
    ) -> tuple[ConceptRevision, ...]:
        """Search current definitions by operator-facing metadata."""
        target_date = _parse_date(valid_on, "valid_on")
        needle = query.strip().casefold()
        items: list[ConceptRevision] = []
        state = self._state()
        for concept_id in sorted(state["current_revisions"]):
            item = self.get(concept_id)
            searchable = " ".join(
                (
                    item.concept_id,
                    item.display_name,
                    item.definition,
                    item.comments,
                    *item.aliases,
                    *item.hints,
                    *item.tags,
                    *item.classifications.values(),
                )
            ).casefold()
            if needle and needle not in searchable:
                continue
            if tag and tag.casefold() not in {value.casefold() for value in item.tags}:
                continue
            if status and item.status != status:
                continue
            if target_date and not self._valid_on(item, target_date):
                continue
            items.append(item)
        return tuple(items)

    def verify(self) -> dict[str, int | str]:
        """Fail closed on pointer, schema, chain, digest, or orphan inconsistencies."""
        state = self._state()
        referenced: set[str] = set()
        revisions = 0
        for concept_id, history in state["revision_history"].items():
            if not _IDENTIFIER.fullmatch(concept_id) or not history:
                raise ConceptError(f"invalid catalog history identity: {concept_id}")
            previous: str | None = None
            for number, revision_id in enumerate(history, start=1):
                revision = self._load_revision(revision_id)
                if revision.concept_id != concept_id:
                    raise ConceptError(f"revision concept mismatch: {revision_id}")
                if revision.revision_number != number:
                    raise ConceptError(f"revision sequence mismatch: {revision_id}")
                if revision.supersedes_revision_id != previous:
                    raise ConceptError(f"revision chain mismatch: {revision_id}")
                self._validate_revision_digest(revision)
                self._validate_draft(self.to_draft(revision))
                previous = revision_id
                referenced.add(revision_id)
                revisions += 1
            if state["current_revisions"].get(concept_id) != history[-1]:
                raise ConceptError(f"current revision mismatch: {concept_id}")
        return {
            "concepts": len(state["current_revisions"]),
            "revisions": revisions,
            "result": "PASS",
        }

    @staticmethod
    def to_draft(
        revision: ConceptRevision,
        status: ConceptStatus | None = None,
    ) -> ConceptDraft:
        """Project a current revision into editable intent."""
        return ConceptDraft(
            concept_id=revision.concept_id,
            display_name=revision.display_name,
            definition=revision.definition,
            comments=revision.comments,
            aliases=revision.aliases,
            hints=revision.hints,
            status=status or revision.status,
            tags=revision.tags,
            classifications=revision.classifications,
            valid_from=revision.valid_from,
            valid_through=revision.valid_through,
            sample_date=revision.sample_date,
            methods=revision.methods,
            related_concept_ids=revision.related_concept_ids,
            samples=revision.samples,
            warnings=revision.warnings,
        )

    def _validate_draft(self, draft: ConceptDraft) -> None:
        if not _IDENTIFIER.fullmatch(draft.concept_id):
            raise ConceptError(f"invalid concept identifier: {draft.concept_id}")
        if not draft.display_name.strip() or not draft.definition.strip():
            raise ConceptError("display name and definition are required")
        start = _parse_date(draft.valid_from, "valid_from", required=True)
        end = _parse_date(draft.valid_through, "valid_through")
        _parse_date(draft.sample_date, "sample_date")
        if start and end and end < start:
            raise ConceptError("invalid concept validity interval")
        _unique(draft.aliases, "aliases")
        _unique(draft.hints, "hints")
        _unique(draft.tags, "tags")
        method_ids = [self.registry.validate(item).method_id for item in draft.methods]
        if len(method_ids) != len(set(method_ids)):
            raise ConceptError("method identifiers must be unique within a revision")
        for related in draft.related_concept_ids:
            if not _IDENTIFIER.fullmatch(related):
                raise ConceptError(f"invalid related concept identifier: {related}")

    def _revision(
        self,
        draft: ConceptDraft,
        number: int,
        supersedes: str | None,
        created_at: str,
        updated_at: str,
    ) -> ConceptRevision:
        material = {
            **asdict(draft),
            "status": draft.status.value,
            "revision_number": number,
            "created_at": created_at,
            "updated_at": updated_at,
            "supersedes_revision_id": supersedes,
        }
        revision_id = "concept-revision-" + hashlib.sha256(_canonical(material)).hexdigest()
        draft_fields = asdict(draft)
        draft_fields["status"] = draft.status
        draft_fields["methods"] = draft.methods
        return ConceptRevision(
            revision_id=revision_id,
            revision_number=number,
            created_at=created_at,
            updated_at=updated_at,
            supersedes_revision_id=supersedes,
            **draft_fields,
        )

    def _validate_revision_digest(self, revision: ConceptRevision) -> None:
        draft = self.to_draft(revision)
        expected = self._revision(
            draft,
            revision.revision_number,
            revision.supersedes_revision_id,
            revision.created_at,
            revision.updated_at,
        ).revision_id
        if expected != revision.revision_id:
            raise ConceptError(f"revision digest mismatch: {revision.revision_id}")

    def _valid_on(self, revision: ConceptRevision, target: date) -> bool:
        start = date.fromisoformat(revision.valid_from)
        end = date.fromisoformat(revision.valid_through) if revision.valid_through else None
        return start <= target and (end is None or target <= end)

    def _state(self) -> dict[str, Any]:
        with self._database.connect(read_only=True) as connection:
            current = connection.execute(
                "SELECT concept_id,current_revision_id FROM concepts ORDER BY concept_id"
            ).fetchall()
            revisions = connection.execute(
                "SELECT concept_id,revision_id FROM concept_revisions "
                "ORDER BY concept_id,revision_number"
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
        if not revision_id.startswith("concept-revision-"):
            raise ConceptError("unsafe revision path rejected")
        return self.revisions_root / f"{revision_id}.json"

    def _write_revision(self, revision: ConceptRevision) -> None:
        with self._database.connect(read_only=True) as connection:
            prior = connection.execute(
                "SELECT canonical_json FROM concept_revisions WHERE revision_id = ?",
                (revision.revision_id,),
            ).fetchone()
        if prior is not None:
            if str(prior[0]) != canonical_json(asdict(revision)):
                raise ConceptError(f"attempted historical mutation: {revision.revision_id}")
            return
        self._publish(revision, create=revision.revision_number == 1)

    def _load_revision(self, revision_id: str) -> ConceptRevision:
        with self._database.connect(read_only=True) as connection:
            row = connection.execute(
                "SELECT canonical_json FROM concept_revisions WHERE revision_id = ?",
                (revision_id,),
            ).fetchone()
        if row is None:
            raise ConceptError(f"unknown concept revision: {revision_id}")
        try:
            value = json.loads(str(row[0]))
        except json.JSONDecodeError as error:
            raise ConceptError("cannot read concept structured state") from error
        value["status"] = ConceptStatus(value["status"])
        value["methods"] = tuple(ObservationMethod(**item) for item in value["methods"])
        for field_name in (
            "aliases",
            "hints",
            "tags",
            "related_concept_ids",
            "samples",
            "warnings",
        ):
            value[field_name] = tuple(value[field_name])
        return ConceptRevision(**value)

    def _publish(self, revision: ConceptRevision, *, create: bool) -> None:
        payload = canonical_json(asdict(revision))
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    "INSERT INTO concept_revisions VALUES (?,?,?,?,?,?)",
                    (
                        revision.revision_id,
                        revision.concept_id,
                        revision.revision_number,
                        revision.supersedes_revision_id,
                        revision.created_at,
                        payload,
                    ),
                )
                if create:
                    connection.execute(
                        "INSERT INTO concepts(concept_id,current_revision_id) VALUES (?,?)",
                        (revision.concept_id, revision.revision_id),
                    )
                else:
                    changed = connection.execute(
                        "UPDATE concepts SET current_revision_id = ? WHERE concept_id = ? "
                        "AND current_revision_id = ?",
                        (
                            revision.revision_id,
                            revision.concept_id,
                            revision.supersedes_revision_id,
                        ),
                    ).rowcount
                    if changed != 1:
                        raise ConceptError("invalid revision update: current revision has changed")
                self._database.advance_revision(connection)
        except StorageError as error:
            raise ConceptError(str(error)) from error
