"""Capability validation and bounded execution for repository artifact streams."""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, Callable

from rfi.artifacts import ArtifactContent
from rfi.storage.sqlite import canonical_json
from rfi.streams.contracts import (
    ArtifactProjection,
    SchemaCapability,
    StreamDraft,
    StreamDefinitionReview,
    StreamError,
    StreamImportResult,
    StreamPreview,
    StreamRevision,
    StreamRun,
    StreamSummary,
    ValidationResult,
)
from rfi.streams.definition import (
    canonical_yaml,
    normalize_draft,
    parse_yaml,
    semantic_diff,
    semantic_fingerprint,
    template_yaml,
)
from rfi.streams.registry import StreamSchemaRegistry, default_registry
from rfi.streams.repository import StreamRepository

_ID = re.compile(r"^[a-z][a-z0-9._-]{1,79}$")


def draft_from_dict(value: dict[str, Any]) -> StreamDraft:
    """Normalize one browser/CLI draft without accepting executable policy forms."""
    allowed = {
        "stream_id", "name", "description", "enabled", "input_kind", "input_ids",
        "schema_id", "selection", "expansion", "bounds", "metadata",
    }
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise StreamError(
            "unknown_field", f"$.{unknown[0]}: unknown stream draft field", f"$.{unknown[0]}"
        )
    try:
        input_ids = value.get("input_ids", [])
        bounds = value.get("bounds", {})
        enabled = value.get("enabled", True)
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be Boolean")
        metadata = value.get("metadata", {})
        if not isinstance(input_ids, (list, tuple)) or not isinstance(bounds, dict):
            raise TypeError("invalid input or bounds")
        if not isinstance(metadata, dict):
            raise TypeError("invalid metadata")
        return StreamDraft(
            stream_id=str(value["stream_id"]), name=str(value["name"]),
            description=str(value.get("description", "")),
            enabled=enabled, input_kind=str(value["input_kind"]),
            input_ids=tuple(str(item) for item in input_ids), schema_id=str(value["schema_id"]),
            selection=dict(value.get("selection", {})),
            expansion=dict(value.get("expansion", {"strategy": "none"})),
            bounds={str(key): int(item) for key, item in bounds.items()},
            metadata={str(key): str(item) for key, item in metadata.items()},
        )
    except (KeyError, TypeError, ValueError) as error:
        raise StreamError("invalid_draft", "stream draft is malformed") from error


class StreamService:
    """Shared admin/CLI stream contract with deterministic bounded publication."""

    def __init__(
        self,
        repository: StreamRepository,
        *,
        clock: Callable[[], str] | None = None,
        identifiers: Callable[[], str] | None = None,
        registry: StreamSchemaRegistry | None = None,
    ) -> None:
        self.repository = repository
        self.clock = clock or (lambda: datetime.now(UTC).isoformat())
        self.identifiers = identifiers or (lambda: f"streamrun-{uuid.uuid4().hex}")
        self.registry = registry or default_registry()
        self._capability_map = {
            item.capability.schema_id: item.capability
            for item in self.registry.registrations()
        }

    def capabilities(self) -> tuple[SchemaCapability, ...]:
        return tuple(self._capability_map.values())

    def external_sources(self) -> tuple[dict[str, Any], ...]:
        return self.repository.external_sources()

    def list_streams(self) -> tuple[StreamSummary, ...]:
        result = []
        for revision in self.repository.list_revisions():
            latest = self.repository.runs(revision.stream_id)
            current = latest[0] if latest else None
            memberships = self.repository.memberships(revision.stream_id, limit=500)
            result.append(
                StreamSummary(
                    revision.stream_id, revision.draft.name, revision.draft.enabled,
                    revision.draft.input_kind, revision.draft.schema_id,
                    revision.revision_id, revision.revision_number,
                    self.repository.dependencies(revision.revision_id),
                    self.repository.consumers(revision.stream_id),
                    current.run_id if current else None, current.status if current else None,
                    len(memberships),
                )
            )
        return tuple(result)

    def detail(self, stream_id: str, revision_id: str | None = None) -> StreamRevision:
        return self.repository.revision(stream_id, revision_id)

    def history(self, stream_id: str) -> tuple[StreamRevision, ...]:
        return self.repository.history(stream_id)

    def schema_template(self) -> str:
        """Return the documented YAML template generated from the canonical adapter."""
        return template_yaml()

    def review_yaml(self, text: str) -> StreamDefinitionReview:
        """Parse, resolve, normalize, validate, and compare YAML without persistence."""
        try:
            draft = normalize_draft(parse_yaml(text))
        except StreamError as error:
            return StreamDefinitionReview(
                False, (self._error_value(error),), (), None, None, None, (), None, "invalid"
            )
        validation = self.validate(draft)
        if not validation.valid:
            return StreamDefinitionReview(
                False, validation.errors, (), draft, None, semantic_fingerprint(draft),
                (), None, "invalid",
            )
        try:
            current = self.detail(draft.stream_id)
        except StreamError as error:
            if error.code != "unknown_stream":
                raise
            current = None
        differences = semantic_diff(current.draft, draft) if current else ()
        mode = "new" if current is None else "revision" if differences else "already_current"
        warnings = () if current is None or differences else ({
            "code": "already_current",
            "path": "$.stream",
            "message": "the normalized definition is already the current saved revision",
        },)
        return StreamDefinitionReview(
            True, (), warnings, draft, canonical_yaml(draft), semantic_fingerprint(draft),
            differences, current.revision_id if current else None, mode,
        )

    def import_yaml(
        self, text: str, mode: str, expected_revision_id: str | None = None
    ) -> StreamImportResult:
        """Explicitly import a new identity or revision; identical input is a no-op."""
        review = self.review_yaml(text)
        if not review.valid or review.draft is None or review.semantic_fingerprint is None:
            first = review.errors[0]
            raise StreamError(first["code"], first["message"], first.get("path"))
        if review.import_mode == "already_current":
            revision = self.detail(review.draft.stream_id)
            return StreamImportResult("already_current", revision, review.semantic_fingerprint)
        if review.import_mode == "new":
            if mode != "new":
                raise StreamError(
                    "import_mode_required",
                    "$.stream.stream_id: this identity is new; import requires new mode",
                    "$.stream.stream_id",
                )
            revision = self.save(review.draft)
            return StreamImportResult("created", revision, review.semantic_fingerprint)
        if mode != "revision":
            raise StreamError(
                "import_mode_required",
                "$.stream.stream_id: this identity exists; import requires revision mode",
                "$.stream.stream_id",
            )
        expected = expected_revision_id or review.existing_revision_id
        revision = self.save(review.draft, expected)
        return StreamImportResult("revised", revision, review.semantic_fingerprint)

    def export_yaml(self, stream_id: str, revision_id: str | None = None) -> str:
        """Export a selected saved revision as deterministic canonical YAML."""
        revision = self.detail(stream_id, revision_id)
        return canonical_yaml(revision.draft, revision)

    def draft_yaml(self, draft: StreamDraft) -> str:
        """Validate and serialize an unsaved draft through the authoritative contract."""
        normalized = normalize_draft(draft)
        validation = self.validate(normalized)
        if not validation.valid:
            first = validation.errors[0]
            raise StreamError(first["code"], first["message"], first.get("path"))
        return canonical_yaml(normalized)

    def compare(self, before: StreamDraft, after: StreamDraft) -> tuple[dict[str, Any], ...]:
        """Expose the normalized semantic comparison used by YAML review."""
        return semantic_diff(before, after)

    @staticmethod
    def _error_value(error: StreamError) -> dict[str, str]:
        return {
            "code": error.code,
            "path": error.path or "$",
            "message": str(error),
        }

    def _validate_contract_shape(
        self, draft: StreamDraft, add: Callable[[str, str, str], None]
    ) -> None:
        """Reject hidden, ill-typed, or non-contract values before normalization."""
        if not isinstance(draft.enabled, bool):
            add("invalid_type", "must be a Boolean", "$.stream.enabled")
        if not isinstance(draft.selection, dict):
            add("invalid_type", "must be an object", "$.stream.selection")
        else:
            self._validate_policy_shape(draft.selection, add, "$.stream.selection")
        if not isinstance(draft.expansion, dict):
            add("invalid_type", "must be an object", "$.stream.expansion")
        else:
            unknown = sorted(
                set(draft.expansion)
                - {"strategy", "ancestor_closure", "descendant_depth"}
            )
            if unknown:
                add(
                    "unknown_field", "unknown expansion field",
                    f"$.stream.expansion.{unknown[0]}",
                )
        if not isinstance(draft.bounds, dict):
            add("invalid_type", "must be an object", "$.stream.bounds")
        else:
            unknown_bounds = sorted(set(draft.bounds) - {"seed_limit", "expanded_limit"})
            if unknown_bounds:
                add(
                    "unknown_field", "unknown bounds field",
                    f"$.stream.bounds.{unknown_bounds[0]}",
                )
            for key, value in draft.bounds.items():
                if isinstance(value, bool) or not isinstance(value, int):
                    add("invalid_type", "must be an integer", f"$.stream.bounds.{key}")
        unknown_metadata = sorted(set(draft.metadata) - {"notes"})
        if unknown_metadata:
            add(
                "unknown_field", "unknown metadata field",
                f"$.stream.metadata.{unknown_metadata[0]}",
            )

    def _validate_policy_shape(
        self, node: dict[str, Any], add: Callable[[str, str, str], None], path: str
    ) -> None:
        operation = node.get("op")
        allowed = (
            {"op", "items"} if operation in {"all", "any"}
            else {"op", "item"} if operation == "not"
            else {"op", "field", "operator", "value"}
        )
        unknown = sorted(set(node) - allowed)
        if unknown:
            add("unknown_field", "unknown policy field", f"{path}.{unknown[0]}")
        if operation in {"all", "any"}:
            items = node.get("items")
            if isinstance(items, (list, tuple)):
                for index, item in enumerate(items):
                    if isinstance(item, dict):
                        self._validate_policy_shape(item, add, f"{path}.{operation}[{index}]")
        elif operation == "not" and isinstance(node.get("item"), dict):
            self._validate_policy_shape(node["item"], add, f"{path}.not")

    def validate(
        self, draft: StreamDraft, provisional_external_sources: tuple[str, ...] = ()
    ) -> ValidationResult:
        errors: list[dict[str, str]] = []

        def add(code: str, message: str, path: str = "$.stream") -> None:
            errors.append({"code": code, "path": path, "message": f"{path}: {message}"})

        self._validate_contract_shape(draft, add)
        draft = normalize_draft(draft)

        if not _ID.fullmatch(draft.stream_id):
            add(
                "invalid_identity", "must be a stable lowercase repository identity",
                "$.stream.stream_id",
            )
        if not draft.name.strip():
            add("invalid_name", "display name is required", "$.stream.display_name")
        capability = self._capability_map.get(draft.schema_id)
        if capability is None:
            add(
                "unsupported_schema", f"unsupported artifact schema: {draft.schema_id}",
                "$.stream.input.artifact_schema",
            )
        if draft.input_kind not in {"external", "streams"}:
            add(
                "invalid_input_kind", "must be external or streams", "$.stream.input.kind"
            )
        if not draft.input_ids:
            add("missing_input", "at least one input is required", "$.stream.input")
        if len(set(draft.input_ids)) != len(draft.input_ids):
            add("duplicate_input", "stable identities must be unique", "$.stream.input")
        if draft.input_kind == "external":
            self._validate_external(draft, add, provisional_external_sources)
        elif draft.input_kind == "streams":
            self._validate_upstreams(draft, add)
        seed_limit = draft.bounds.get("seed_limit", 0)
        expanded_limit = draft.bounds.get("expanded_limit", 0)
        if not 1 <= seed_limit <= 500:
            add(
                "invalid_limit", "must be between 1 and 500",
                "$.stream.bounds.direct_matches",
            )
        if not 1 <= expanded_limit <= 2000:
            add(
                "invalid_limit", "must be between 1 and 2000",
                "$.stream.bounds.total_artifacts",
            )
        if capability is not None:
            self._validate_policy(draft.selection, capability, errors)
            strategy = str(draft.expansion.get("strategy", "none"))
            registration = self.registry.registration(draft.schema_id)
            handlers = {
                item.strategy: item for item in registration.expansion_handlers
            } if registration else {}
            if strategy not in handlers:
                add(
                    "unsupported_expansion",
                    f"schema {draft.schema_id} does not support expansion {strategy}",
                    "$.stream.expansion.strategy",
                )
            else:
                for item in handlers[strategy].validate(draft.expansion):
                    path = (
                        "$.stream.expansion.descendant_depth"
                        if "depth" in item["message"] else "$.stream.expansion"
                    )
                    add(item["code"], item["message"], path)
        try:
            order = self._topological_order(draft)
        except StreamError as error:
            add(error.code, str(error), error.path or "$.stream.input")
            order = ()
        return ValidationResult(not errors, tuple(errors), tuple(order))

    def save(
        self, draft: StreamDraft, expected_revision_id: str | None = None
    ) -> StreamRevision:
        draft = normalize_draft(draft)
        validation = self.validate(draft)
        if not validation.valid:
            first = validation.errors[0]
            raise StreamError(first["code"], first["message"])
        return self.repository.save(draft, expected_revision_id)

    def preview(self, draft: StreamDraft, limit: int = 25) -> StreamPreview:
        draft = normalize_draft(draft)
        validation = self.validate(draft)
        if not validation.valid:
            first = validation.errors[0]
            raise StreamError(first["code"], first["message"])
        if not 1 <= limit <= 100:
            raise StreamError("invalid_limit", "preview limit must be between 1 and 100")
        self._refresh(draft.schema_id)
        candidates, upstream = self._candidates(draft)
        publications, candidate_count, direct_count, context_count, truncated = self._plan(
            draft, "preview", candidates, upstream
        )
        items = tuple(
            {
                "artifact_id": item["artifact_id"], "document_id": item["document_id"],
                "title": item["projection"]["title"],
                "inclusion_kind": item["inclusion_kind"],
                "inclusion_reason": item["inclusion_reason"],
            }
            for item in publications[:limit]
        )
        return StreamPreview(
            draft.stream_id, candidate_count, direct_count, context_count,
            truncated or len(publications) > limit, items,
        )

    def run(self, stream_id: str) -> StreamRun:
        revision = self.repository.revision(stream_id)
        if not revision.draft.enabled:
            raise StreamError("stream_disabled", "disabled streams cannot execute")
        self._refresh(revision.draft.schema_id)
        candidates, upstream = self._candidates(revision.draft)
        fingerprint = self._fingerprint(revision, candidates, upstream)
        existing = self.repository.successful_run(revision.revision_id, fingerprint)
        if existing is not None:
            return existing
        run_id = self.identifiers()
        self.repository.begin_run(run_id, revision, fingerprint, self.clock())
        try:
            publications, _candidate_count, _direct, _context, _truncated = self._plan(
                revision.draft, run_id, candidates, upstream
            )
            return self.repository.publish_run(run_id, self.clock(), publications)
        except Exception as error:
            code = error.code if isinstance(error, StreamError) else "execution_failed"
            self.repository.fail_run(run_id, self.clock(), code, str(error))
            if isinstance(error, StreamError):
                raise
            raise StreamError("execution_failed", "stream execution failed") from error

    def run_chain(self, stream_id: str) -> tuple[StreamRun, ...]:
        draft = self.repository.revision(stream_id).draft
        order = self._topological_order(draft)
        if len(order) > 50:
            raise StreamError("chain_limit", "dependency chain exceeds the 50-stream limit")
        return tuple(self.run(item) for item in order)

    def rebuild(self) -> dict[str, int | str]:
        return self.repository.rebuild()

    def content(self, membership_id: str) -> ArtifactContent:
        membership = self.repository.membership(membership_id)
        content = self.repository.artifacts.read_artifact(membership.artifact_id)
        return ArtifactContent(
            membership.document_id, membership.artifact_id, content,
            self._media_type(membership.artifact_id), hashlib.sha256(content).hexdigest(),
        )

    def _media_type(self, artifact_id: str) -> str:
        for item in self.repository.artifacts.artifact_metadata():
            if item.get("artifact_id") == artifact_id:
                return str(item.get("media_type", "application/octet-stream"))
        return "application/octet-stream"

    def _validate_external(
        self,
        draft: StreamDraft,
        add: Callable[[str, str, str], None],
        provisional_external_sources: tuple[str, ...] = (),
    ) -> None:
        if len(draft.input_ids) != 1:
            add(
                "invalid_external_input", "external input requires exactly one governed source",
                "$.stream.input.source_profile_id",
            )
            return
        known = {
            item["source_id"] for item in self.repository.external_sources()
        } | set(provisional_external_sources)
        if draft.input_ids[0] not in known:
            add(
                "unknown_source", f"unknown governed source: {draft.input_ids[0]}",
                "$.stream.input.source_profile_id",
            )

    def _refresh(self, schema_id: str) -> int:
        registration = self.registry.registration(schema_id)
        if registration is None:
            raise StreamError("unsupported_schema", f"unsupported artifact schema: {schema_id}")
        return registration.projection_provider.refresh(self.repository)

    def _validate_upstreams(
        self, draft: StreamDraft, add: Callable[[str, str, str], None]
    ) -> None:
        for upstream_id in draft.input_ids:
            if upstream_id == draft.stream_id:
                add("self_reference", "a stream cannot consume itself", "$.stream.input.stream_ids")
                continue
            try:
                upstream = self.repository.revision(upstream_id)
            except StreamError:
                add(
                    "unknown_upstream", f"unknown upstream stream: {upstream_id}",
                    "$.stream.input.stream_ids",
                )
                continue
            if upstream.draft.schema_id != draft.schema_id:
                add(
                    "incompatible_schema",
                    f"upstream {upstream_id} provides {upstream.draft.schema_id}, "
                    f"not {draft.schema_id}",
                    "$.stream.input.artifact_schema",
                )

    def _validate_policy(
        self, node: dict[str, Any], capability: SchemaCapability,
        errors: list[dict[str, str]], depth: int = 0, count: list[int] | None = None,
        path: str = "$.stream.selection",
    ) -> None:
        count = count if count is not None else [0]
        count[0] += 1
        if count[0] > 50 or depth > 5:
            errors.append({
                "code": "policy_limit", "path": path,
                "message": f"{path}: policy exceeds bounded complexity",
            })
            return
        op = node.get("op") if isinstance(node, dict) else None
        if op in {"all", "any"}:
            items = node.get("items")
            if not isinstance(items, (list, tuple)) or not items:
                errors.append({
                    "code": "invalid_policy", "path": path,
                    "message": f"{path}: {op} requires policy items",
                })
                return
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    errors.append({
                        "code": "invalid_policy", "path": f"{path}.{op}[{index}]",
                        "message": f"{path}.{op}[{index}]: policy item must be an object",
                    })
                else:
                    self._validate_policy(
                        item, capability, errors, depth + 1, count,
                        f"{path}.{op}[{index}]",
                    )
            return
        if op == "not":
            item = node.get("item")
            if not isinstance(item, dict):
                errors.append({
                    "code": "invalid_policy", "path": f"{path}.not",
                    "message": f"{path}.not: not requires one policy item",
                })
            else:
                self._validate_policy(
                    item, capability, errors, depth + 1, count, f"{path}.not"
                )
            return
        if op != "predicate":
            errors.append({
                "code": "invalid_policy",
                "path": f"{path}.op",
                "message": f"{path}.op: policy uses an unsupported operation",
            })
            return
        field = str(node.get("field", ""))
        operator = str(node.get("operator", ""))
        supported = capability.fields.get(field)
        if field.startswith("attribute:"):
            attribute_id = field.partition(":")[2]
            attribute = next(
                (item for item in capability.attributes if item.attribute_id == attribute_id), None
            )
            supported = attribute.operators if attribute else None
        if supported is None:
            errors.append({
                "code": "unsupported_predicate",
                "path": f"{path}.field",
                "message": f"{path}.field: schema {capability.schema_id} does not register "
                f"field {field}",
            })
        elif operator not in supported:
            errors.append({
                "code": "unsupported_operator",
                "path": f"{path}.operator",
                "message": f"{path}.operator: field {field} does not support operator {operator}",
            })
        value = node.get("value")
        if operator == "in":
            if not isinstance(value, list) or not value or len(value) > 50:
                errors.append({
                    "code": "invalid_value", "path": f"{path}.values",
                    "message": f"{path}.values: in requires 1-50 values",
                })
        elif not isinstance(value, str) or not value.strip():
            errors.append({
                "code": "invalid_value", "path": f"{path}.value",
                "message": f"{path}.value: predicate value is required",
            })

    def _topological_order(self, draft: StreamDraft) -> tuple[str, ...]:
        graph: dict[str, tuple[str, ...]] = {
            item.stream_id: self.repository.dependencies(item.revision_id)
            for item in self.repository.list_revisions()
        }
        graph[draft.stream_id] = draft.input_ids if draft.input_kind == "streams" else ()
        visiting: set[str] = set()
        visited: set[str] = set()
        order: list[str] = []

        def visit(node: str) -> None:
            if node in visiting:
                raise StreamError(
                    "dependency_cycle", f"stream dependency cycle includes {node}",
                    "$.stream.input.stream_ids",
                )
            if node in visited:
                return
            visiting.add(node)
            for dependency in graph.get(node, ()):
                visit(dependency)
            visiting.remove(node)
            visited.add(node)
            order.append(node)

        visit(draft.stream_id)
        return tuple(order)

    def _candidates(
        self, draft: StreamDraft
    ) -> tuple[tuple[ArtifactProjection, ...], dict[str, list[dict[str, Any]]]]:
        upstream: dict[str, list[dict[str, Any]]] = {}
        if draft.input_kind == "external":
            return self.repository.projections(draft.schema_id, draft.input_ids), upstream
        projections: dict[str, ArtifactProjection] = {}
        for upstream_id in draft.input_ids:
            current_revision = self.repository.revision(upstream_id)
            latest = self.repository.latest_success(upstream_id)
            if latest is None or latest.revision_id != current_revision.revision_id:
                raise StreamError(
                    "upstream_not_current",
                    f"upstream {upstream_id} must run at its current revision first",
                )
            for membership in self.repository.memberships(upstream_id, latest.run_id, 500):
                projections[membership.artifact_id] = membership.projection
                upstream.setdefault(membership.artifact_id, []).append({
                    "upstream_stream_id": upstream_id,
                    "upstream_membership_id": membership.membership_id,
                    "inclusion_reason": "inherited_upstream_candidate",
                })
        return tuple(sorted(projections.values(), key=self._projection_key)), upstream

    def _fingerprint(
        self, revision: StreamRevision, candidates: tuple[ArtifactProjection, ...],
        upstream: dict[str, list[dict[str, Any]]],
    ) -> str:
        value = {
            "revision_id": revision.revision_id,
            "candidates": [asdict(item) for item in candidates],
            "upstream": upstream,
        }
        return hashlib.sha256(canonical_json(value).encode()).hexdigest()

    def _plan(
        self, draft: StreamDraft, run_key: str, candidates: tuple[ArtifactProjection, ...],
        upstream: dict[str, list[dict[str, Any]]],
    ) -> tuple[list[dict[str, Any]], int, int, int, bool]:
        matches = [item for item in candidates if self._matches(draft.selection, item)]
        seed_limit = draft.bounds["seed_limit"]
        truncated = len(matches) > seed_limit
        direct = matches[:seed_limit]
        selected: dict[str, dict[str, Any]] = {}
        strategy = str(draft.expansion.get("strategy", "none"))
        for item in direct:
            selected[item.artifact_id] = {
                "projection": item, "inclusion_kind": "direct",
                "inclusion_reason": "direct_match",
                "lineage": list(upstream.get(item.artifact_id, [])),
            }
        registration = self.registry.registration(draft.schema_id)
        if registration is None:
            raise StreamError(
                "unsupported_schema", f"unsupported artifact schema: {draft.schema_id}"
            )
        handler = next(
            (item for item in registration.expansion_handlers if item.strategy == strategy), None
        )
        if handler is None:
            raise StreamError("unsupported_expansion", f"unsupported expansion: {strategy}")
        for expanded in handler.expand(self.repository, draft, tuple(direct), upstream):
            selected[expanded.projection.artifact_id] = {
                "projection": expanded.projection,
                "inclusion_kind": "context",
                "inclusion_reason": expanded.inclusion_reason,
                "lineage": list(expanded.lineage),
            }
        publications = []
        for item in sorted(
            selected.values(), key=lambda value: self._projection_key(value["projection"])
        ):
            projection = item["projection"]
            digest = hashlib.sha256(
                f"{run_key}\0{projection.artifact_id}".encode()
            ).hexdigest()
            publications.append({
                "membership_id": f"membership-{digest[:32]}",
                "artifact_id": projection.artifact_id,
                "document_id": projection.document_id,
                "inclusion_kind": item["inclusion_kind"],
                "inclusion_reason": item["inclusion_reason"],
                "expansion_strategy": strategy,
                "completeness": projection.completeness,
                "projection": asdict(projection),
                "lineage": item["lineage"] or [{
                    "seed_artifact_id": projection.artifact_id,
                    "inclusion_reason": "direct_match",
                }],
            })
        direct_count = sum(item["inclusion_kind"] == "direct" for item in publications)
        return (
            publications, len(candidates), direct_count,
            len(publications) - direct_count, truncated,
        )

    def _matches(self, node: dict[str, Any], item: ArtifactProjection) -> bool:
        op = str(node["op"])
        if op == "all":
            return all(self._matches(child, item) for child in node["items"])
        if op == "any":
            return any(self._matches(child, item) for child in node["items"])
        if op == "not":
            return not self._matches(node["item"], item)
        field = str(node["field"])
        operator = str(node["operator"])
        expected = node["value"]
        if field == "schema":
            actual: Any = item.schema_id
        elif field == "source":
            actual = item.source_id
        elif field == "title":
            actual = item.title
        elif field == "text":
            actual = item.searchable_text
        elif field == "authors":
            actual = item.authors
        elif field == "effective_at":
            actual = item.effective_at or ""
        elif field == "completeness":
            actual = item.completeness or ""
        else:
            actual = item.attributes.get(field.partition(":")[2], "")
        values = (
            tuple(str(value).casefold() for value in actual)
            if isinstance(actual, tuple) else ()
        )
        scalar = str(actual).casefold() if not isinstance(actual, tuple) else ""
        if operator == "contains":
            needle = str(expected).casefold()
            return any(needle in value for value in values) if values else needle in scalar
        if operator == "equals":
            needle = str(expected).casefold()
            return needle in values if values else scalar == needle
        if operator == "in":
            accepted = {str(value).casefold() for value in expected}
            return bool(set(values).intersection(accepted)) if values else scalar in accepted
        if operator == "after_or_on":
            target = str(expected).casefold()
            comparable = scalar[:10] if field == "effective_at" and len(target) == 10 else scalar
            return comparable >= target
        if operator == "before_or_on":
            target = str(expected).casefold()
            comparable = scalar[:10] if field == "effective_at" and len(target) == 10 else scalar
            return comparable <= target
        return False

    @staticmethod
    def _projection_key(item: ArtifactProjection) -> tuple[str, str]:
        return item.effective_at or "", item.artifact_id
