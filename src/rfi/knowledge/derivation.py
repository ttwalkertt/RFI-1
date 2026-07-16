"""Deterministic SEC meaning construction through source-object contracts only."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

from rfi.knowledge.contracts import (
    DerivationFailure,
    DerivedObject,
    KnowledgeStatus,
    ProvenanceReference,
)
from rfi.source_objects.contracts import SourceObject, SourceObjectReader

_DERIVER = "sec-header-deriver-v1"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _provenance(item: SourceObject) -> ProvenanceReference:
    return ProvenanceReference(
        source_object_id=item.source_object_id,
        document_id=item.document_id,
        artifact_id=item.artifact_id,
        byte_start=item.byte_start,
        byte_end=item.byte_end,
        content_sha256=item.content_sha256,
    )


def _object(
    object_type: str,
    semantic_key: str,
    payload: dict[str, Any],
    status: KnowledgeStatus,
    confidence: float,
    provenance: tuple[ProvenanceReference, ...],
) -> DerivedObject:
    identity = hashlib.sha256(
        f"knowledge-object-v1\0{object_type}\0{semantic_key}".encode()
    ).hexdigest()
    object_id = f"knowledge-{object_type}-{identity}"
    material = {
        "object_id": object_id,
        "payload": payload,
        "status": status.value,
        "confidence": confidence,
        "provenance": [asdict(item) for item in provenance],
        "derivation_id": _DERIVER,
    }
    version_id = f"knowledge-version-{hashlib.sha256(_canonical(material)).hexdigest()}"
    return DerivedObject(
        object_id=object_id,
        version_id=version_id,
        object_type=object_type,
        semantic_key=semantic_key,
        payload=payload,
        status=status,
        confidence=confidence,
        provenance=provenance,
        derivation_id=_DERIVER,
    )


class DeterministicSecDeriver:
    """Build bounded issuer, filing observation, and filed-by relationship knowledge."""

    def derive(
        self, source: SourceObjectReader
    ) -> tuple[list[DerivedObject], list[DerivationFailure]]:
        """Derive current knowledge without reading source persistence internals."""
        documents = sorted({item.document_id for item in source.inventory()})
        observations: list[DerivedObject] = []
        relationships: list[DerivedObject] = []
        failures: list[DerivationFailure] = []
        issuers: dict[str, dict[str, list[SourceObject]]] = {}
        document_ciks: dict[str, tuple[str, SourceObject]] = {}
        for document_id in documents:
            fields = self._fields(source.by_document(document_id))
            required = {
                "central-index-key",
                "company-conformed-name",
                "accession-number",
                "conformed-submission-type",
            }
            missing = sorted(required - fields.keys())
            if missing:
                failures.append(
                    self._failure(
                        document_id,
                        "incomplete-extraction",
                        f"missing fields: {', '.join(missing)}",
                    )
                )
                continue
            cik_item = fields["central-index-key"][0]
            name_item = fields["company-conformed-name"][0]
            cik = source.field_value(cik_item.source_object_id).lstrip("0") or "0"
            name = source.field_value(name_item.source_object_id)
            issuers.setdefault(cik, {}).setdefault(name, []).extend((cik_item, name_item))
            document_ciks[document_id] = (cik, cik_item)
            payload = {
                "document_id": document_id,
                "accession_number": self._value(source, fields, "accession-number"),
                "form_type": self._value(source, fields, "conformed-submission-type"),
                "period_of_report": self._value(source, fields, "conformed-period-of-report"),
                "filed_as_of_date": self._value(source, fields, "filed-as-of-date"),
            }
            proof_items = [
                fields[key][0]
                for key in (
                    "accession-number",
                    "conformed-submission-type",
                    "conformed-period-of-report",
                    "filed-as-of-date",
                )
                if key in fields
            ]
            status = KnowledgeStatus.CONFIRMED
            confidence = 1.0
            if payload["period_of_report"] is None or payload["filed_as_of_date"] is None:
                status = KnowledgeStatus.UNCERTAIN
                confidence = 0.8
            observations.append(
                _object(
                    "observation",
                    f"sec-filing:{document_id}",
                    payload,
                    status,
                    confidence,
                    tuple(_provenance(item) for item in proof_items),
                )
            )
        entities: list[DerivedObject] = []
        for cik, names in sorted(issuers.items()):
            status = KnowledgeStatus.CONFIRMED if len(names) == 1 else KnowledgeStatus.CONFLICTED
            confidence = 1.0 if len(names) == 1 else 0.5
            proof = sorted(
                {
                    item.source_object_id: item
                    for items in names.values()
                    for item in items
                }.values(),
                key=lambda item: item.source_object_id,
            )
            entities.append(
                _object(
                    "entity",
                    f"sec-issuer-cik:{cik}",
                    {"cik": cik, "names": sorted(names)},
                    status,
                    confidence,
                    tuple(_provenance(item) for item in proof),
                )
            )
            if status == KnowledgeStatus.CONFLICTED:
                failures.append(
                    self._failure(
                        proof[0].document_id,
                        "ambiguous-entity-resolution",
                        f"CIK {cik} has conflicting names: {', '.join(sorted(names))}",
                        tuple(item.source_object_id for item in proof),
                    )
                )
        entity_by_cik = {item.payload["cik"]: item for item in entities}
        observation_by_document = {
            item.payload["document_id"]: item for item in observations
        }
        for document_id, (cik, cik_item) in sorted(document_ciks.items()):
            if document_id not in observation_by_document:
                continue
            entity = entity_by_cik[cik]
            observation = observation_by_document[document_id]
            relationships.append(
                _object(
                    "relationship",
                    f"issuer-filed:{cik}:{document_id}",
                    {
                        "relationship": "issuer-filed",
                        "from_object_id": entity.object_id,
                        "to_object_id": observation.object_id,
                    },
                    KnowledgeStatus.CONFIRMED,
                    1.0,
                    (_provenance(cik_item), *observation.provenance),
                )
            )
        objects = sorted(
            entities + observations + relationships, key=lambda item: item.object_id
        )
        return objects, failures

    def _fields(self, items: list[SourceObject]) -> dict[str, list[SourceObject]]:
        fields: dict[str, list[SourceObject]] = {}
        for item in items:
            if item.kind == "field":
                fields.setdefault(item.role, []).append(item)
        return fields

    def _value(
        self, source: SourceObjectReader, fields: dict[str, list[SourceObject]], role: str
    ) -> str | None:
        return source.field_value(fields[role][0].source_object_id) if role in fields else None

    def _failure(
        self,
        document_id: str,
        category: str,
        message: str,
        source_object_ids: tuple[str, ...] = (),
    ) -> DerivationFailure:
        material = _canonical([document_id, category, message, source_object_ids])
        return DerivationFailure(
            failure_id=f"derivation-failure-{hashlib.sha256(material).hexdigest()}",
            document_id=document_id,
            category=category,
            message=message,
            source_object_ids=source_object_ids,
        )
