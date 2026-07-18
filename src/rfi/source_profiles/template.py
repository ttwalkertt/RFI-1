"""Runtime loader and fail-closed validator for canonical acquisition application data."""

from __future__ import annotations

import re
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from rfi.source_profiles.contracts import (
    AcquisitionTemplate,
    AddressabilityClass,
    CanonicalArtifact,
    CanonicalCategory,
    RetrievalFieldDefinition,
    RetrievalModeDefinition,
    SourceProfileError,
)

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_FIELD_TYPES = {"integer", "string", "url"}


def canonical_template_path() -> Path:
    """Return the shipped template path in normal filesystem installations."""
    return Path(str(resources.files("rfi").joinpath("resources/source-profile-template.yaml")))


def load_canonical_template(path: Path | None = None) -> AcquisitionTemplate:
    """Load and validate the one shipped acquisition template, or a test fixture path."""
    target = path or canonical_template_path()
    try:
        value = yaml.safe_load(target.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise SourceProfileError(f"cannot load canonical acquisition template: {error}") from error
    return validate_canonical_template(value)


def validate_canonical_template(value: Any) -> AcquisitionTemplate:
    """Decode a template object and reject ambiguity, drift, or noncanonical ordering."""
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise SourceProfileError("unsupported or malformed canonical acquisition template")
    fields_raw = _objects(value, "retrieval_fields")
    modes_raw = _objects(value, "retrieval_modes")
    categories_raw = _objects(value, "categories")
    fields = tuple(_field(item) for item in fields_raw)
    _unique((item.name for item in fields), "retrieval field names")
    field_names = {item.name for item in fields}
    modes = tuple(_mode(item, field_names) for item in modes_raw)
    _unique((item.mode for item in modes), "retrieval mode identifiers")
    mode_names = {item.mode for item in modes}
    categories = tuple(_category(item, mode_names) for item in categories_raw)
    _unique((item.category_id for item in categories), "category identifiers")
    _ascending((item.order for item in categories), "category")
    artifacts = tuple(item for category in categories for item in category.items)
    if not artifacts:
        raise SourceProfileError("canonical acquisition template must define artifacts")
    _unique((item.artifact_id for item in artifacts), "canonical artifact identifiers")
    _unique((item.short_name.casefold() for item in artifacts), "canonical short names")
    return AcquisitionTemplate(1, fields, modes, categories)


def _objects(parent: dict[str, Any], name: str) -> list[dict[str, Any]]:
    value = parent.get(name)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise SourceProfileError(f"canonical template {name} must be an array of objects")
    return value


def _text(value: Any, label: str, identifier: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SourceProfileError(f"canonical template {label} is required")
    result = value.strip()
    if identifier and not _IDENTIFIER.fullmatch(result):
        raise SourceProfileError(f"invalid canonical template {label}: {result}")
    return result


def _strings(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise SourceProfileError(f"canonical template {label} must be a string array")
    result = tuple(item.strip() for item in value)
    if any(not item for item in result) or len(set(result)) != len(result):
        raise SourceProfileError(f"canonical template {label} contains empty or duplicate values")
    return result


def _order(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise SourceProfileError(f"canonical template {label} must be a positive integer")
    return value


def _field(value: dict[str, Any]) -> RetrievalFieldDefinition:
    value_type = _text(value.get("type"), "retrieval field type", identifier=True)
    if value_type not in _FIELD_TYPES:
        raise SourceProfileError(f"unsupported canonical retrieval field type: {value_type}")
    multiple = value.get("multiple", False)
    if not isinstance(multiple, bool):
        raise SourceProfileError("canonical retrieval field multiple must be boolean")
    return RetrievalFieldDefinition(
        _text(value.get("name"), "retrieval field name", identifier=True),
        _text(value.get("label"), "retrieval field label"),
        _text(value.get("description"), "retrieval field description"),
        value_type,
        multiple,
    )


def _mode(value: dict[str, Any], fields: set[str]) -> RetrievalModeDefinition:
    supported = _strings(value.get("supported_fields"), "mode supported_fields")
    required = _strings(value.get("required_fields", []), "mode required_fields")
    required_any = _strings(value.get("required_any", []), "mode required_any")
    if not set((*supported, *required, *required_any)).issubset(fields):
        raise SourceProfileError("retrieval mode references an unknown canonical field")
    if not set((*required, *required_any)).issubset(supported):
        raise SourceProfileError("retrieval mode requirements must be supported fields")
    return RetrievalModeDefinition(
        _text(value.get("mode"), "retrieval mode", identifier=True),
        _text(value.get("label"), "retrieval mode label"),
        _text(value.get("description"), "retrieval mode description"),
        supported,
        required,
        required_any,
    )


def _category(value: dict[str, Any], modes: set[str]) -> CanonicalCategory:
    category_id = _text(value.get("id"), "category identifier", identifier=True)
    items = tuple(_artifact(item, category_id, modes) for item in _objects(value, "items"))
    if not items:
        raise SourceProfileError(f"canonical category {category_id} must define artifacts")
    _ascending((item.order for item in items), f"items in {category_id}")
    return CanonicalCategory(
        category_id,
        _text(value.get("label"), "category label"),
        _text(value.get("description"), "category description"),
        _order(value.get("order"), "category order"),
        items,
    )


def _artifact(
    value: dict[str, Any], category_id: str, modes: set[str]
) -> CanonicalArtifact:
    short_name = _text(value.get("short_name"), "artifact short_name")
    if len(short_name) > 32:
        raise SourceProfileError(f"canonical short_name is not concise: {short_name}")
    enabled = value.get("default_enabled")
    if not isinstance(enabled, bool):
        raise SourceProfileError("canonical artifact default_enabled must be boolean")
    supported = _strings(value.get("supported_retrieval_modes"), "artifact modes")
    if not supported or not set(supported).issubset(modes):
        raise SourceProfileError("canonical artifact references an unsupported retrieval mode")
    try:
        addressability = AddressabilityClass(value.get("addressability"))
    except ValueError as error:
        raise SourceProfileError("unsupported canonical addressability class") from error
    return CanonicalArtifact(
        _text(value.get("id"), "artifact identifier", identifier=True),
        short_name,
        _text(value.get("label"), "artifact label"),
        _text(value.get("description"), "artifact description"),
        category_id,
        enabled,
        addressability,
        supported,
        _order(value.get("order"), "artifact order"),
    )


def _unique(values: Any, label: str) -> None:
    items = tuple(values)
    if len(set(items)) != len(items):
        raise SourceProfileError(f"canonical template has duplicate {label}")


def _ascending(values: Any, label: str) -> None:
    items = tuple(values)
    if items != tuple(sorted(items)) or len(set(items)) != len(items):
        raise SourceProfileError(f"canonical template {label} ordering is not deterministic")
