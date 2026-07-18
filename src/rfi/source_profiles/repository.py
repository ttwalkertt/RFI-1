"""Immutable revision persistence for firm-owned source-profile configuration."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
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

_SCHEMA_VERSION = 1
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_DOMAIN = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SourceProfileRepository:
    """Independent profile authority with immutable revisions and atomic current pointers."""

    def __init__(self, root: Path, template: AcquisitionTemplate) -> None:
        self.root = root
        self.revisions_root = root / "revisions"
        self.pointer = root / "catalog.json"
        self.template = template
        self._artifacts = {item.artifact_id: item for item in template.artifacts}
        self._modes = {item.mode: item for item in template.retrieval_modes}

    @classmethod
    def initialize(
        cls, root: Path, template: AcquisitionTemplate
    ) -> SourceProfileRepository:
        """Initialize empty profile state without overwriting existing history."""
        repository = cls(root, template)
        if repository.pointer.exists():
            repository.verify()
            return repository
        root.mkdir(parents=True, exist_ok=True)
        repository.revisions_root.mkdir(exist_ok=True)
        repository._atomic_json(
            repository.pointer,
            {"schema_version": _SCHEMA_VERSION, "current_revisions": {}, "revision_history": {}},
        )
        return repository

    @classmethod
    def open(cls, root: Path, template: AcquisitionTemplate) -> SourceProfileRepository:
        """Open only state that passes complete chain and template validation."""
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
        path = self._revision_path(revision.source_profile_revision_id)
        existed = path.exists()
        self._write_revision(revision)
        try:
            if fail_before_publish:
                raise SourceProfileError(
                    "injected interrupted write before source-profile publication"
                )
            state["current_revisions"][draft.firm_id] = revision.source_profile_revision_id
            state["revision_history"].setdefault(draft.firm_id, []).append(
                revision.source_profile_revision_id
            )
            self._atomic_json(self.pointer, state)
        except Exception:
            if not existed:
                path.unlink(missing_ok=True)
            raise
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
        files = {path.stem for path in self.revisions_root.glob("*.json")}
        if files != referenced:
            raise SourceProfileError(
                "source-profile catalog contains missing or unreferenced revision files"
            )
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
    ) -> SourceProfileRevision:
        material = {
            **asdict(draft),
            "revision_number": number,
            "created_at": created_at,
            "updated_at": updated_at,
            "supersedes_revision_id": supersedes,
        }
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
        )

    def _validate_digest(self, revision: SourceProfileRevision) -> None:
        expected = self._revision(
            self.to_draft(revision),
            revision.revision_number,
            revision.supersedes_revision_id,
            revision.created_at,
            revision.updated_at,
        ).source_profile_revision_id
        if expected != revision.source_profile_revision_id:
            raise SourceProfileError(
                f"source-profile revision digest mismatch: "
                f"{revision.source_profile_revision_id}"
            )

    def _state(self) -> dict[str, Any]:
        value = self._load_json(self.pointer)
        if value.get("schema_version") != _SCHEMA_VERSION:
            raise SourceProfileError("unsupported or corrupt source-profile catalog schema")
        if not isinstance(value.get("current_revisions"), dict) or not isinstance(
            value.get("revision_history"), dict
        ):
            raise SourceProfileError("source-profile catalog pointer is malformed")
        return value

    def _revision_path(self, revision_id: str) -> Path:
        if not revision_id.startswith("source-profile-revision-"):
            raise SourceProfileError("unsafe source-profile revision path rejected")
        return self.revisions_root / f"{revision_id}.json"

    def _write_revision(self, revision: SourceProfileRevision) -> None:
        path = self._revision_path(revision.source_profile_revision_id)
        content = _canonical(asdict(revision))
        if path.exists() and path.read_bytes() != content:
            raise SourceProfileError(
                f"attempted source-profile historical mutation: "
                f"{revision.source_profile_revision_id}"
            )
        if not path.exists():
            self._atomic_json(path, asdict(revision))

    def _load_revision(self, revision_id: str) -> SourceProfileRevision:
        value = self._load_json(self._revision_path(revision_id))

        def candidate(value: dict[str, Any]) -> RetrievalCandidate:
            fields = dict(value)
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
        return SourceProfileRevision(**value)

    def _load_json(self, path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SourceProfileError(
                f"cannot read source-profile state {path.name}: {error}"
            ) from error
        if not isinstance(value, dict):
            raise SourceProfileError(f"source-profile state is not an object: {path.name}")
        return value

    def _atomic_json(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(_canonical(value))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
