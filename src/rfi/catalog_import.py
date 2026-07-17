"""Canonical external-catalog model, validation, templates, and import orchestration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

import yaml

from rfi.firms import FirmDraft, FirmError, FirmRepository, FirmService


class CatalogImportError(RuntimeError):
    """An actionable external-catalog validation or import failure."""


@dataclass(frozen=True)
class Field:
    """One canonical input field used for decoding and template generation."""

    name: str
    kind: str = "string"
    required: bool = False
    default: Any = ""
    placeholder: Any = ""
    children: tuple[Field, ...] = ()


IDENTIFIER_FIELDS = (
    Field("kind", required=True, placeholder="ticker"),
    Field("value", required=True, placeholder="EXMP"),
    Field("market", placeholder="NASDAQ"),
)
SOURCE_HINT_FIELDS = (
    Field("kind", required=True, placeholder="investor-relations"),
    Field("value", required=True, placeholder="investor.example.com"),
    Field("notes", placeholder="Optional discovery guidance."),
)
FIRM_FIELDS = (
    Field("firm_id", required=True, placeholder="example-firm"),
    Field("canonical_name", required=True, placeholder="Example Firm, Inc."),
    Field("valid_from", "date", required=True, placeholder="YYYY-MM-DD"),
    Field("legal_name", placeholder="Example Firm, Inc."),
    Field("aliases", "strings", default=(), placeholder=("Example Firm",)),
    Field("identifiers", "objects", default=(), children=IDENTIFIER_FIELDS),
    Field("domains", "strings", default=(), placeholder=("example.com",)),
    Field("headquarters", placeholder="Example City, Country"),
    Field("jurisdiction", placeholder="Example jurisdiction"),
    Field("sector", placeholder="Information Technology"),
    Field("industry", placeholder="Example Industry"),
    Field("technology_focus", "strings", default=(), placeholder=("example technology",)),
    Field("source_hints", "objects", default=(), children=SOURCE_HINT_FIELDS),
    Field("notes", placeholder="Optional operator notes."),
    Field("relevance", "number", default=0.0, placeholder=50),
    Field("status", default="draft", placeholder="active"),
    Field("valid_through", "optional_date", default=None, placeholder=None),
)
CATALOG_FIELDS = (
    Field("title", required=True, placeholder="Example catalog"),
    Field("description", placeholder="Describe the purpose of this catalog."),
    Field("prepared_on", "date", required=True, placeholder="YYYY-MM-DD"),
)
SOURCE_FIELDS = (
    Field("title", required=True, placeholder="Example Source"),
    Field("url", required=True, placeholder="https://example.com/"),
    Field("accessed_on", "date", required=True, placeholder="YYYY-MM-DD"),
)
RESEARCH_FIELDS = (
    Field("prepared_by", required=True, placeholder="Your Name"),
    Field("methodology", required=True, placeholder="Describe selection methodology."),
    Field("reviewed_on", "date", required=True, placeholder="YYYY-MM-DD"),
    Field("sources", "objects", required=True, children=SOURCE_FIELDS),
)


@dataclass(frozen=True)
class ImportableType:
    """Registry entry separating a catalog section from its typed decoder."""

    section: str
    fields: tuple[Field, ...]
    decode: Callable[[dict[str, Any]], Any]


IMPORTABLE_TYPES = (
    ImportableType("firms", FIRM_FIELDS, FirmService.draft),
)


@dataclass(frozen=True)
class ImportCatalog:
    """A completely decoded external catalog independent of persistence."""

    source: Path
    firms: tuple[FirmDraft, ...]


@dataclass(frozen=True)
class ImportResult:
    """Deterministic import counts for one validated batch."""

    files: int
    created: tuple[str, ...]
    already_present: tuple[str, ...]


def canonical_template() -> str:
    """Render YAML from the exact field definitions accepted by the decoder."""
    value = {
        "schema_version": 1,
        "catalog": _template_object(CATALOG_FIELDS),
    }
    value.update(
        {
            definition.section: [_template_object(definition.fields)]
            for definition in IMPORTABLE_TYPES
        }
    )
    value["research"] = _template_object(RESEARCH_FIELDS)
    return yaml.safe_dump(value, sort_keys=False, allow_unicode=True)


def load_catalog(path: Path) -> ImportCatalog:
    """Read and fully validate one external catalog without touching application state."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as error:
        raise CatalogImportError(f"cannot read catalog file {path}: {error}") from error
    if not content.strip():
        raise CatalogImportError(f"catalog file is empty: {path}")
    try:
        value = yaml.safe_load(content)
    except yaml.YAMLError as error:
        raise CatalogImportError(f"malformed YAML in {path}: {error}") from error
    if not isinstance(value, dict):
        raise CatalogImportError(f"catalog root must be an object: {path}")
    root_fields = ("schema_version", "catalog", "research") + tuple(
        definition.section for definition in IMPORTABLE_TYPES
    )
    _only_fields(value, root_fields, "catalog root")
    if value.get("schema_version") != 1:
        raise CatalogImportError(
            f"unsupported schema_version in {path}: expected 1, got "
            f"{value.get('schema_version')!r}"
        )
    catalog = _decode_object(value.get("catalog"), CATALOG_FIELDS, "catalog")
    research = _decode_object(value.get("research"), RESEARCH_FIELDS, "research")
    drafts = _decode_section(value, IMPORTABLE_TYPES[0])
    _validate_dates(catalog, research, path)
    return ImportCatalog(path, tuple(drafts))


def import_catalogs(
    paths: tuple[Path, ...],
    repository: FirmRepository,
    prospective: tuple[FirmDraft, ...] = (),
    fail_after_revision_count: int | None = None,
) -> ImportResult:
    """Validate a complete batch, then create only new, non-conflicting firms."""
    catalogs = tuple(load_catalog(path) for path in paths)
    drafts = tuple(draft for catalog in catalogs for draft in catalog.firms)
    existing = {firm.firm_id: firm for firm in repository.lookup()}
    future = {draft.firm_id: draft for draft in prospective}
    planned: dict[str, FirmDraft] = {}
    already: list[str] = []
    for draft in drafts:
        current = existing.get(draft.firm_id)
        expected = future.get(draft.firm_id)
        prior = planned.get(draft.firm_id)
        if current is not None:
            if _draft_value(draft) != _draft_value(repository.to_draft(current)):
                raise CatalogImportError(
                    f"conflicting canonical identifier {draft.firm_id}: existing record differs"
                )
            already.append(draft.firm_id)
            continue
        if expected is not None:
            if _draft_value(draft) != _draft_value(expected):
                raise CatalogImportError(
                    f"conflicting canonical identifier {draft.firm_id}: starter record differs"
                )
            already.append(draft.firm_id)
            continue
        if prior is not None:
            if _draft_value(draft) != _draft_value(prior):
                raise CatalogImportError(
                    f"conflicting canonical identifier {draft.firm_id}: batch records differ"
                )
            raise CatalogImportError(f"duplicate canonical identifier in batch: {draft.firm_id}")
        repository.validate(draft)
        planned[draft.firm_id] = draft
    _validate_planned_together(repository, prospective + tuple(planned.values()))
    created = []
    ordered = tuple(planned[firm_id] for firm_id in sorted(planned))
    if ordered:
        repository.create_batch(ordered, fail_after_revision_count)
    created.extend(draft.firm_id for draft in ordered)
    return ImportResult(len(catalogs), tuple(created), tuple(sorted(set(already))))


def _validate_planned_together(
    repository: FirmRepository, drafts: tuple[FirmDraft, ...]
) -> None:
    """Apply repository conflict semantics across new records before persistence."""
    validator = _ValidationOverlay(repository, drafts)
    for draft in drafts:
        validator.validate(draft, draft.firm_id)


@dataclass(frozen=True)
class _SyntheticFirm:
    """Minimum repository validation projection for a planned firm."""

    firm_id: str
    identifiers: tuple[Any, ...]
    domains: tuple[str, ...]

    def __init__(self, draft: FirmDraft) -> None:
        object.__setattr__(self, "firm_id", draft.firm_id)
        object.__setattr__(self, "identifiers", draft.identifiers)
        object.__setattr__(self, "domains", draft.domains)


class _ValidationOverlay(FirmRepository):
    """Read-only view combining persisted and planned firms for batch validation."""

    def __init__(self, repository: FirmRepository, drafts: tuple[FirmDraft, ...]) -> None:
        super().__init__(repository.root)
        self.repository = repository
        self.drafts = drafts

    def lookup(self, *args: Any, **kwargs: Any) -> tuple[Any, ...]:
        return self.repository.lookup(*args, **kwargs) + tuple(
            _SyntheticFirm(draft) for draft in self.drafts
        )


def _template_object(fields: tuple[Field, ...]) -> dict[str, Any]:
    result = {}
    for field in fields:
        if field.kind == "objects":
            result[field.name] = [_template_object(field.children)]
        else:
            result[field.name] = field.placeholder
    return result


def _decode_section(value: dict[str, Any], definition: ImportableType) -> tuple[Any, ...]:
    raw_records = value.get(definition.section)
    if not isinstance(raw_records, list) or not raw_records:
        raise CatalogImportError(f"{definition.section} must be a non-empty array")
    records = []
    for index, raw in enumerate(raw_records):
        label = f"{definition.section}[{index}]"
        payload = _decode_object(raw, definition.fields, label)
        try:
            records.append(definition.decode(payload))
        except (FirmError, TypeError, ValueError) as error:
            raise CatalogImportError(f"{label}: {error}") from error
    return tuple(records)


def _decode_object(value: Any, fields: tuple[Field, ...], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CatalogImportError(f"{label} must be an object")
    definitions = {field.name: field for field in fields}
    _only_fields(value, tuple(definitions), label)
    result = {}
    for name, field in definitions.items():
        if name not in value:
            if field.required:
                raise CatalogImportError(f"{label}.{name} is required")
            result[name] = field.default
            continue
        result[name] = _decode_field(value[name], field, f"{label}.{name}")
    return result


def _decode_field(value: Any, field: Field, label: str) -> Any:
    if field.kind == "string":
        if not isinstance(value, str) or (field.required and not value.strip()):
            raise CatalogImportError(f"{label} must be a non-empty string")
        return value
    if field.kind == "optional_string":
        if value is not None and not isinstance(value, str):
            raise CatalogImportError(f"{label} must be a string or null")
        return value
    if field.kind in {"date", "optional_date"}:
        if value is None and field.kind == "optional_date":
            return None
        if isinstance(value, date):
            return value.isoformat()
        if not isinstance(value, str) or (field.required and not value.strip()):
            raise CatalogImportError(f"{label} must be an ISO date")
        return value
    if field.kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CatalogImportError(f"{label} must be a number")
        return value
    if field.kind == "strings":
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise CatalogImportError(f"{label} must be an array of strings")
        return tuple(value)
    if not isinstance(value, list) or (field.required and not value):
        raise CatalogImportError(f"{label} must be a non-empty array")
    return [_decode_object(item, field.children, f"{label}[{index}]")
            for index, item in enumerate(value)]


def _only_fields(value: dict[str, Any], allowed: tuple[str, ...], label: str) -> None:
    unknown = sorted(set(value).difference(allowed))
    if unknown:
        raise CatalogImportError(f"{label} contains unsupported field: {unknown[0]}")


def _validate_dates(
    catalog: dict[str, Any], research: dict[str, Any], path: Path
) -> None:
    checks = [
        (catalog["prepared_on"], "catalog.prepared_on"),
        (research["reviewed_on"], "research.reviewed_on"),
    ]
    checks.extend(
        (source["accessed_on"], f"research.sources[{index}].accessed_on")
        for index, source in enumerate(research["sources"])
    )
    for raw, label in checks:
        try:
            date.fromisoformat(raw)
        except (TypeError, ValueError) as error:
            raise CatalogImportError(f"{path}: {label} must be an ISO date") from error


def _draft_value(draft: FirmDraft) -> dict[str, Any]:
    value = asdict(draft)
    value["status"] = draft.status.value
    return value
