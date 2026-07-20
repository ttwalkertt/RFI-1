"""Strict canonical YAML adapter for the authoritative artifact-stream contract."""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from typing import Any

import yaml

from rfi.storage.sqlite import canonical_json
from rfi.streams.contracts import StreamDraft, StreamError, StreamRevision

SCHEMA_VERSION = 1

_ROOT_FIELDS = {"schema_version", "stream", "revision"}
_STREAM_FIELDS = {
    "stream_id", "display_name", "description", "enabled", "input", "selection",
    "expansion", "bounds", "metadata",
}
_INPUT_FIELDS = {
    "external_source": {"kind", "source_profile_id", "artifact_schema"},
    "upstream_streams": {"kind", "stream_ids", "artifact_schema"},
}
_EXPANSION_FIELDS = {"strategy", "ancestor_closure", "descendant_depth"}
_BOUNDS_FIELDS = {"direct_matches", "total_artifacts"}
_METADATA_FIELDS = {"notes"}
_REVISION_FIELDS = {"revision_number", "created_at"}
_FORBIDDEN_KEYS = {
    "api_key", "archive_base_url", "archive_url", "backoff", "concurrency", "cookie",
    "credentials", "cursor", "endpoint", "password", "protocol", "provider", "pacing",
    "retry", "retry_after", "secret", "timeout", "token", "transport", "user_agent",
    "sql", "python", "javascript", "json_path", "jsonpath",
}


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> Any:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping", node.start_mark,
                f"duplicate field {key!r}", key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping
)


def parse_yaml(text: str) -> StreamDraft:
    """Parse and structurally decode one canonical stream YAML document without persistence."""
    if not text.strip():
        raise StreamError("empty_yaml", "$: stream YAML is empty", "$")
    try:
        value = yaml.load(text, Loader=_UniqueKeyLoader)
    except yaml.YAMLError as error:
        raise StreamError("malformed_yaml", f"$: malformed YAML: {error}", "$") from error
    root = _object(value, "$")
    _reject_forbidden(root, "$")
    _only(root, _ROOT_FIELDS, "$")
    if root.get("schema_version") != SCHEMA_VERSION:
        raise StreamError(
            "unsupported_schema_version",
            f"$.schema_version: expected {SCHEMA_VERSION}, got "
            f"{root.get('schema_version')!r}",
            "$.schema_version",
        )
    stream = _object(root.get("stream"), "$.stream")
    _only(stream, _STREAM_FIELDS, "$.stream")
    revision = root.get("revision")
    if revision is not None:
        revision_value = _object(revision, "$.revision")
        _only(revision_value, _REVISION_FIELDS, "$.revision")
        _positive_integer(revision_value.get("revision_number"), "$.revision.revision_number")
        _text(revision_value.get("created_at"), "$.revision.created_at")

    input_value = _object(stream.get("input"), "$.stream.input")
    kind = _text(input_value.get("kind"), "$.stream.input.kind")
    allowed_input = _INPUT_FIELDS.get(kind)
    if allowed_input is None:
        raise StreamError(
            "invalid_input_kind",
            "$.stream.input.kind: expected external_source or upstream_streams",
            "$.stream.input.kind",
        )
    _only(input_value, allowed_input, "$.stream.input")
    if kind == "external_source":
        input_ids = (_text(
            input_value.get("source_profile_id"),
            "$.stream.input.source_profile_id",
        ),)
        input_kind = "external"
    else:
        input_ids = _strings(input_value.get("stream_ids"), "$.stream.input.stream_ids")
        input_kind = "streams"

    expansion = _object(stream.get("expansion"), "$.stream.expansion")
    _only(expansion, _EXPANSION_FIELDS, "$.stream.expansion")
    strategy = _text(expansion.get("strategy"), "$.stream.expansion.strategy")
    decoded_expansion: dict[str, Any] = {"strategy": strategy}
    if "ancestor_closure" in expansion:
        ancestor = expansion["ancestor_closure"]
        decoded_expansion["ancestor_closure"] = (
            True if ancestor == "required" else _boolean(
                ancestor, "$.stream.expansion.ancestor_closure"
            )
        )
    if "descendant_depth" in expansion:
        decoded_expansion["descendant_depth"] = _integer(
            expansion["descendant_depth"], "$.stream.expansion.descendant_depth"
        )

    bounds = _object(stream.get("bounds"), "$.stream.bounds")
    _only(bounds, _BOUNDS_FIELDS, "$.stream.bounds")
    decoded_bounds = {
        "seed_limit": _positive_integer(
            bounds.get("direct_matches"), "$.stream.bounds.direct_matches"
        ),
        "expanded_limit": _positive_integer(
            bounds.get("total_artifacts"), "$.stream.bounds.total_artifacts"
        ),
    }
    metadata_value = stream.get("metadata", {})
    metadata = _object(metadata_value, "$.stream.metadata")
    _only(metadata, _METADATA_FIELDS, "$.stream.metadata")
    decoded_metadata = (
        {"notes": _text(metadata["notes"], "$.stream.metadata.notes")}
        if "notes" in metadata else {}
    )
    description = stream.get("description", "")
    if not isinstance(description, str):
        _fail("invalid_type", "$.stream.description", "must be a string")
    enabled = stream.get("enabled", True)
    return StreamDraft(
        stream_id=_text(stream.get("stream_id"), "$.stream.stream_id"),
        name=_text(stream.get("display_name"), "$.stream.display_name"),
        description=description.strip(),
        enabled=_boolean(enabled, "$.stream.enabled"),
        input_kind=input_kind,
        input_ids=input_ids,
        schema_id=_text(input_value.get("artifact_schema"), "$.stream.input.artifact_schema"),
        selection=_decode_policy(stream.get("selection"), "$.stream.selection"),
        expansion=decoded_expansion,
        bounds=decoded_bounds,
        metadata=decoded_metadata,
    )


def canonical_yaml(draft: StreamDraft, revision: StreamRevision | None = None) -> str:
    """Serialize one normalized definition with stable key and collection ordering."""
    normalized = normalize_draft(draft)
    input_value: dict[str, Any]
    if normalized.input_kind == "external":
        input_value = {
            "kind": "external_source",
            "source_profile_id": normalized.input_ids[0] if normalized.input_ids else "",
            "artifact_schema": normalized.schema_id,
        }
    else:
        input_value = {
            "kind": "upstream_streams",
            "stream_ids": list(normalized.input_ids),
            "artifact_schema": normalized.schema_id,
        }
    stream: dict[str, Any] = {
        "stream_id": normalized.stream_id,
        "display_name": normalized.name,
        "description": normalized.description,
        "enabled": normalized.enabled,
        "input": input_value,
        "selection": _encode_policy(normalized.selection),
        "expansion": _canonical_expansion(normalized.expansion),
        "bounds": {
            "direct_matches": normalized.bounds.get("seed_limit", 0),
            "total_artifacts": normalized.bounds.get("expanded_limit", 0),
        },
    }
    if normalized.metadata:
        stream["metadata"] = dict(normalized.metadata)
    value: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "stream": stream}
    if revision is not None:
        value["revision"] = {
            "revision_number": revision.revision_number,
            "created_at": revision.created_at,
        }
    return yaml.safe_dump(value, sort_keys=False, allow_unicode=True, width=100)


def normalize_draft(draft: StreamDraft) -> StreamDraft:
    """Canonicalize collection order, scalar whitespace, defaults, and policy structure."""
    inputs = tuple(item.strip() for item in draft.input_ids)
    if draft.input_kind == "streams":
        inputs = tuple(sorted(inputs))
    strategy = str(draft.expansion.get("strategy", "none")).strip()
    expansion: dict[str, Any] = {"strategy": strategy}
    if strategy == "connected_discussion":
        expansion.update({
            "ancestor_closure": draft.expansion.get("ancestor_closure", True),
            "descendant_depth": draft.expansion.get("descendant_depth", 0),
        })
    return StreamDraft(
        stream_id=draft.stream_id.strip(),
        name=draft.name.strip(),
        description=draft.description.strip(),
        enabled=draft.enabled,
        input_kind=draft.input_kind.strip(),
        input_ids=inputs,
        schema_id=draft.schema_id.strip(),
        selection=_normalize_policy(draft.selection),
        expansion=expansion,
        bounds={
            "seed_limit": draft.bounds.get("seed_limit", 0),
            "expanded_limit": draft.bounds.get("expanded_limit", 0),
        },
        metadata={key: value.strip() for key, value in sorted(draft.metadata.items())},
    )


def semantic_fingerprint(draft: StreamDraft) -> str:
    """Return the stable identity of one normalized semantic definition."""
    return hashlib.sha256(canonical_json(asdict(normalize_draft(draft))).encode()).hexdigest()


def semantic_diff(before: StreamDraft, after: StreamDraft) -> tuple[dict[str, Any], ...]:
    """Compare normalized definitions by operator-facing semantic category."""
    left = normalize_draft(before)
    right = normalize_draft(after)
    categories = (
        ("identity", {
            "stream_id": left.stream_id, "display_name": left.name,
            "description": left.description, "metadata": left.metadata,
        }, {
            "stream_id": right.stream_id, "display_name": right.name,
            "description": right.description, "metadata": right.metadata,
        }),
        ("enabled_state", left.enabled, right.enabled),
        ("input", {"kind": left.input_kind, "identities": left.input_ids},
         {"kind": right.input_kind, "identities": right.input_ids}),
        ("artifact_schema", left.schema_id, right.schema_id),
        ("selection", left.selection, right.selection),
        ("context_expansion", left.expansion, right.expansion),
        ("bounds", left.bounds, right.bounds),
    )
    return tuple(
        {"category": category, "before": old, "after": new}
        for category, old, new in categories if old != new
    )


def template_yaml() -> str:
    """Render a valid, documented template from the canonical serializer contract."""
    sample = StreamDraft(
        "linux-block-storage", "Linux Block Storage",
        "Linux block-layer discussions relevant to storage architecture", True,
        "external", ("linux-block-lore",), "mail.message",
        {"op": "any", "items": (
            {"op": "predicate", "field": "text", "operator": "contains", "value": "zoned"},
            {"op": "predicate", "field": "authors", "operator": "contains",
             "value": "Jens Axboe"},
        )},
        {"strategy": "connected_discussion", "ancestor_closure": True,
         "descendant_depth": 3},
        {"seed_limit": 25, "expanded_limit": 200},
        {"notes": "Optional operator notes; this field does not configure transport."},
    )
    comments = (
        "# Canonical artifact-stream definition schema/template.\n"
        "# Required: schema_version, stream identity, input, selection, expansion, and bounds.\n"
        "# Optional: description, enabled (defaults true), and metadata.notes.\n"
        "# For a derived stream, use kind: upstream_streams and stream_ids: [stable-stream-id].\n"
        "# Policy nodes are exactly all, any, not, or field/operator/value(s) predicates.\n"
        "# Operators and fields must be declared by the selected artifact schema.\n"
        "# Transport settings, endpoints, credentials, and secrets are forbidden.\n"
        "# Executable policy content is also forbidden.\n"
    )
    return comments + canonical_yaml(sample)


def _decode_policy(value: Any, path: str) -> dict[str, Any]:
    node = _object(value, path)
    keys = set(node)
    groups = keys.intersection({"all", "any", "not"})
    if groups:
        if len(groups) != 1 or len(keys) != 1:
            _fail("invalid_policy", path, "must contain exactly one Boolean operation")
        operation = next(iter(groups))
        if operation == "not":
            return {"op": "not", "item": _decode_policy(node[operation], f"{path}.not")}
        items = node[operation]
        if not isinstance(items, list) or not items:
            _fail("invalid_policy", f"{path}.{operation}", "must be a non-empty list")
        return {
            "op": operation,
            "items": [_decode_policy(item, f"{path}.{operation}[{index}]")
                      for index, item in enumerate(items)],
        }
    allowed = {"field", "operator", "value", "values"}
    _only(node, allowed, path)
    if "value" in node and "values" in node:
        _fail("invalid_policy", path, "cannot contain both value and values")
    field = _text(node.get("field"), f"{path}.field")
    field = {"searchable_text": "text", "effective_timestamp": "effective_at"}.get(
        field, field
    )
    operator = _text(node.get("operator"), f"{path}.operator")
    if "values" in node:
        predicate_value: Any = list(_strings(node["values"], f"{path}.values"))
    else:
        predicate_value = _text(node.get("value"), f"{path}.value")
    operator = {
        "on_or_after": "after_or_on",
        "on_or_before": "before_or_on",
    }.get(operator, operator)
    if operator == "contains_any":
        if not isinstance(predicate_value, list):
            _fail("invalid_policy", path, "contains_any requires values")
        return {
            "op": "any",
            "items": [
                {"op": "predicate", "field": field, "operator": "contains", "value": item}
                for item in predicate_value
            ],
        }
    return {
        "op": "predicate", "field": field, "operator": operator, "value": predicate_value
    }


def _encode_policy(node: dict[str, Any]) -> dict[str, Any]:
    operation = node.get("op")
    if operation in {"all", "any"}:
        return {str(operation): [_encode_policy(item) for item in node.get("items", ())]}
    if operation == "not":
        return {"not": _encode_policy(node.get("item", {}))}
    value = node.get("value")
    result = {"field": node.get("field", ""), "operator": node.get("operator", "")}
    result["values" if isinstance(value, (list, tuple)) else "value"] = (
        list(value) if isinstance(value, (list, tuple)) else value
    )
    return result


def _normalize_policy(node: dict[str, Any]) -> dict[str, Any]:
    operation = node.get("op") if isinstance(node, dict) else None
    if operation in {"all", "any"}:
        normalized = [_normalize_policy(item) for item in node.get("items", [])]
        normalized.sort(key=canonical_json)
        return {"op": operation, "items": normalized}
    if operation == "not":
        return {"op": "not", "item": _normalize_policy(node.get("item", {}))}
    value = node.get("value") if isinstance(node, dict) else None
    if isinstance(value, (list, tuple)):
        value = sorted(set(str(item).strip() for item in value))
    elif isinstance(value, str):
        value = value.strip()
    return {
        "op": "predicate",
        "field": str(node.get("field", "")).strip() if isinstance(node, dict) else "",
        "operator": str(node.get("operator", "")).strip() if isinstance(node, dict) else "",
        "value": value,
    }


def _canonical_expansion(expansion: dict[str, Any]) -> dict[str, Any]:
    result = {"strategy": expansion.get("strategy", "none")}
    if result["strategy"] == "connected_discussion":
        result["ancestor_closure"] = "required"
        result["descendant_depth"] = expansion.get("descendant_depth", 0)
    return result


def _reject_forbidden(value: Any, path: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key).casefold().replace("-", "_")
            child = f"{path}.{key}"
            if key_text in _FORBIDDEN_KEYS or any(
                term in key_text for term in ("credential", "password", "secret", "token")
            ):
                _fail(
                    "forbidden_configuration", child,
                    "transport, secret, cursor, or executable configuration is not allowed",
                )
            _reject_forbidden(item, child)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_forbidden(item, f"{path}[{index}]")


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        _fail("invalid_type", path, "must be an object with string fields")
    return value


def _only(value: dict[str, Any], allowed: set[str], path: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        _fail("unknown_field", f"{path}.{unknown[0]}", "unknown field")


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("invalid_type", path, "must be a non-empty string")
    return value.strip()


def _strings(value: Any, path: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        _fail("invalid_type", path, "must be a non-empty string list")
    result = tuple(_text(item, f"{path}[{index}]") for index, item in enumerate(value))
    if len(set(result)) != len(result):
        _fail("duplicate_identity", path, "must not contain duplicate stable identities")
    return result


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        _fail("invalid_type", path, "must be a Boolean")
    return value


def _integer(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail("invalid_type", path, "must be an integer")
    return value


def _positive_integer(value: Any, path: str) -> int:
    result = _integer(value, path)
    if result < 1:
        _fail("invalid_bounds", path, "must be a positive integer")
    return result


def _fail(code: str, path: str, message: str) -> None:
    raise StreamError(code, f"{path}: {message}", path)
