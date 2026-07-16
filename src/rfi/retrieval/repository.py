"""Rebuildable governed index and retrieval over public source and knowledge contracts."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from rfi.knowledge.contracts import KnowledgeReader
from rfi.retrieval.contracts import (
    CandidateDecision,
    DerivedKnowledgeResult,
    MetadataConstraints,
    ResultClass,
    RetrievalError,
    RetrievalHealth,
    RetrievalQuery,
    RetrievalResponse,
    RetrievalState,
    RetrievalTrace,
    Score,
    SourceEvidenceResult,
    Vectorizer,
)
from rfi.retrieval.vector import HashingVectorizer, cosine, tokens
from rfi.source_objects.contracts import SourceObject, SourceObjectReader

_SCHEMA = 1


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _enum_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _enum_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_enum_safe(item) for item in value]
    return value


class RetrievalRepository:
    """Own disposable search generations while authoritative data stays elsewhere."""

    def __init__(
        self,
        root: Path,
        source: SourceObjectReader,
        knowledge: KnowledgeReader,
        vectorizer: Vectorizer | None = None,
    ) -> None:
        self.root = root
        self.generations = root / "generations"
        self.pointer = root / "current-generation.json"
        self.source = source
        self.knowledge = knowledge
        self.vectorizer = vectorizer or HashingVectorizer()

    def rebuild(self, fail_before_publish: bool = False) -> dict[str, int | str]:
        """Reproduce an entire index and atomically select it only after verification."""
        try:
            self.knowledge.verify(self.source)
        except Exception as error:
            raise RetrievalError(
                f"knowledge provenance validation failed before indexing: {error}"
            ) from error
        fingerprint = self.authority_fingerprint()
        entries = self._entries()
        payload = {
            "schema_version": _SCHEMA,
            "authority_fingerprint": fingerprint,
            "vectorizer": self.vectorizer.name,
            "entries": entries,
            "knowledge_failures": len(self.knowledge.failures()),
        }
        generation_id = f"retrieval-generation-{_digest(payload)}"
        destination = self.generations / generation_id
        destination.mkdir(parents=True, exist_ok=True)
        content = _canonical(payload)
        path = destination / "index.json"
        if path.exists() and path.read_bytes() != content:
            raise RetrievalError("retrieval generation identity conflicts with existing content")
        path.write_bytes(content)
        manifest = {
            "schema_version": _SCHEMA,
            "generation_id": generation_id,
            "index_sha256": hashlib.sha256(content).hexdigest(),
            "indexed_items": len(entries),
        }
        (destination / "manifest.json").write_bytes(_canonical(manifest))
        self._load_generation(generation_id)
        if fail_before_publish:
            raise RetrievalError("injected retrieval rebuild failure before publication")
        self._atomic_write(
            self.pointer,
            _canonical({"schema_version": _SCHEMA, "generation_id": generation_id}),
        )
        return {
            "generation_id": generation_id,
            "authority_fingerprint": fingerprint,
            "indexed_items": len(entries),
            "source_items": sum(
                entry["result_class"] == ResultClass.SOURCE_EVIDENCE.value
                for entry in entries
            ),
            "knowledge_items": sum(
                entry["result_class"] == ResultClass.DERIVED_KNOWLEDGE.value
                for entry in entries
            ),
            "vectorizer": self.vectorizer.name,
            "result": "PASS",
        }

    def health(self) -> RetrievalHealth:
        """Compare the selected index with both current authorities and its own digest."""
        if not self.pointer.is_file():
            return RetrievalHealth(RetrievalState.MISSING, "retrieval index pointer is absent")
        try:
            pointer = self._read_json(self.pointer)
            generation_id = pointer["generation_id"]
            payload, manifest = self._load_generation(generation_id)
        except (KeyError, RetrievalError) as error:
            return RetrievalHealth(RetrievalState.CORRUPT, str(error))
        try:
            current = self.authority_fingerprint()
        except Exception as error:
            return RetrievalHealth(
                RetrievalState.CORRUPT,
                f"cannot inspect authoritative contracts: {error}",
                generation_id,
                int(manifest["indexed_items"]),
            )
        if payload["authority_fingerprint"] != current:
            return RetrievalHealth(
                RetrievalState.STALE,
                "retrieval index does not represent current source and knowledge state",
                generation_id,
                int(manifest["indexed_items"]),
            )
        if payload["vectorizer"] != self.vectorizer.name:
            return RetrievalHealth(
                RetrievalState.STALE,
                "retrieval index uses a different vector implementation",
                generation_id,
                int(manifest["indexed_items"]),
            )
        return RetrievalHealth(
            RetrievalState.READY,
            "retrieval index is reproducible from current authoritative contracts",
            generation_id,
            int(manifest["indexed_items"]),
        )

    def search(self, query: RetrievalQuery) -> RetrievalResponse:
        """Apply vector candidate generation, deterministic filters, and bounded ranking."""
        self._validate_query(query)
        health = self.health()
        if health.state != RetrievalState.READY or health.generation_id is None:
            raise RetrievalError(f"retrieval state is {health.state.value}: {health.message}")
        try:
            query_vector = self.vectorizer.vector(query.text)
        except Exception as error:
            raise RetrievalError(f"query vector generation failed: {error}") from error
        payload, _ = self._load_generation(health.generation_id)
        query_tokens = set(tokens(query.text))
        ranked: list[tuple[float, dict[str, Any], Score]] = []
        decisions: list[CandidateDecision] = []
        for entry in payload["entries"]:
            result_class = ResultClass(entry["result_class"])
            reason = self._filter_reason(entry, query.constraints, query.result_classes)
            if reason is not None:
                decisions.append(
                    CandidateDecision(entry["identity"], result_class, False, reason)
                )
                continue
            vector_score = max(0.0, cosine(query_vector, tuple(entry["vector"])))
            entry_tokens = set(tokens(entry["text"]))
            lexical = len(query_tokens & entry_tokens) / max(1, len(query_tokens))
            final = round((0.72 * vector_score) + (0.28 * lexical), 12)
            score = Score(round(vector_score, 12), round(lexical, 12), final)
            if final < query.minimum_score:
                decisions.append(
                    CandidateDecision(
                        entry["identity"], result_class, False, "below-minimum-score", score
                    )
                )
                continue
            ranked.append((final, entry, score))
        ranked.sort(key=lambda item: (-item[0], item[1]["result_class"], item[1]["identity"]))
        if len(ranked) > query.candidate_limit:
            for _, entry, score in ranked[query.candidate_limit:]:
                decisions.append(
                    CandidateDecision(
                        entry["identity"],
                        ResultClass(entry["result_class"]),
                        False,
                        "candidate-limit",
                        score,
                    )
                )
            ranked = ranked[:query.candidate_limit]
        selected = ranked[:query.max_results]
        for _, entry, score in selected:
            decisions.append(
                CandidateDecision(
                    entry["identity"],
                    ResultClass(entry["result_class"]),
                    True,
                    "vector-plus-metadata-match",
                    score,
                )
            )
        for _, entry, score in ranked[query.max_results:]:
            decisions.append(
                CandidateDecision(
                    entry["identity"],
                    ResultClass(entry["result_class"]),
                    False,
                    "result-limit",
                    score,
                )
            )
        source_results: list[SourceEvidenceResult] = []
        knowledge_results: list[DerivedKnowledgeResult] = []
        for _, entry, score in selected:
            metadata = {
                key: tuple(value) for key, value in sorted(entry["metadata"].items())
            }
            rationale = self._rationale(entry, score, query.constraints)
            if entry["result_class"] == ResultClass.SOURCE_EVIDENCE.value:
                source_results.append(
                    SourceEvidenceResult(
                        ResultClass.SOURCE_EVIDENCE,
                        self.source.get(entry["identity"]),
                        score,
                        rationale,
                        metadata,
                    )
                )
            else:
                knowledge_results.append(
                    DerivedKnowledgeResult(
                        ResultClass.DERIVED_KNOWLEDGE,
                        self.knowledge.get(entry["identity"]),
                        score,
                        rationale,
                        metadata,
                    )
                )
        notes: list[str] = []
        if not selected:
            notes.append("no candidate satisfied score and metadata constraints")
        requested = set(query.result_classes)
        returned = {
            *(ResultClass.SOURCE_EVIDENCE for _ in source_results),
            *(ResultClass.DERIVED_KNOWLEDGE for _ in knowledge_results),
        }
        for missing in sorted(requested - returned, key=lambda item: item.value):
            notes.append(f"no {missing.value} result was selected")
        if payload.get("knowledge_failures"):
            notes.append(
                f"current knowledge generation reports {payload['knowledge_failures']} "
                "derivation failure(s)"
            )
        trace_material = {
            "generation": health.generation_id,
            "fingerprint": payload["authority_fingerprint"],
            "query": _enum_safe(asdict(query)),
            "decisions": [_enum_safe(asdict(item)) for item in decisions],
        }
        trace = RetrievalTrace(
            f"retrieval-trace-{_digest(trace_material)}",
            health.generation_id,
            payload["authority_fingerprint"],
            query,
            tuple(decisions),
            (),
            tuple(notes),
            len(ranked) > query.max_results,
        )
        return RetrievalResponse(tuple(source_results), tuple(knowledge_results), trace)

    def authority_fingerprint(self) -> str:
        """Fingerprint only stable public representations from both authorities."""
        source = [_enum_safe(asdict(item)) for item in self.source.inventory()]
        knowledge = [_enum_safe(asdict(item)) for item in self.knowledge.inventory()]
        failures = [_enum_safe(asdict(item)) for item in self.knowledge.failures()]
        material = {"source": source, "knowledge": knowledge, "failures": failures}
        return f"authority-{_digest(material)}"

    def _entries(self) -> list[dict[str, Any]]:
        source_items = self.source.inventory()
        document_metadata = self._document_metadata(source_items)
        entries: list[dict[str, Any]] = []
        for item in source_items:
            metadata = dict(document_metadata.get(item.document_id, {}))
            metadata.update(
                {
                    "document_id": [item.document_id],
                    "artifact_id": [item.artifact_id],
                    "source_kind": [item.kind],
                    "source_role": [item.role],
                }
            )
            values = " ".join(f"{key} {value}" for key, value in item.attributes.items())
            text = " ".join(
                ["source evidence", item.kind, item.role, values]
                + [value for group in metadata.values() for value in group]
            )
            entries.append(
                self._entry(
                    item.source_object_id, ResultClass.SOURCE_EVIDENCE, text, metadata
                )
            )
        for item in self.knowledge.inventory():
            payload = json.dumps(item.payload, sort_keys=True, separators=(",", ":"))
            entity_ids = self._entity_ids(item.object_id, item.object_type, item.payload)
            if item.semantic_key.startswith("issuer-filed:"):
                cik = item.semantic_key.split(":", maxsplit=2)[1]
                entity_ids.extend((cik, cik.zfill(10)))
                entity_ids = sorted(set(entity_ids))
            metadata: dict[str, list[str]] = {
                "knowledge_type": [item.object_type],
                "knowledge_status": [item.status.value],
                "entity_id": entity_ids,
                "document_id": sorted({ref.document_id for ref in item.provenance}),
                "artifact_id": sorted({ref.artifact_id for ref in item.provenance}),
            }
            for document_id in metadata["document_id"]:
                for key, values in document_metadata.get(document_id, {}).items():
                    metadata.setdefault(key, []).extend(values)
            document_types = self._payload_values(item.payload, "form_type", "document_type")
            periods = self._payload_values(
                item.payload,
                "report_period",
                "period_of_report",
                "filing_date",
                "filed_as_of_date",
                "period",
            )
            if document_types:
                metadata["document_type"] = document_types
            if periods:
                metadata["period"] = periods
            text = " ".join(
                [
                    "derived knowledge interpretation",
                    item.object_type,
                    item.semantic_key,
                    item.status.value,
                    payload,
                ]
                + [value for group in metadata.values() for value in group]
            )
            entries.append(
                self._entry(item.object_id, ResultClass.DERIVED_KNOWLEDGE, text, metadata)
            )
        return sorted(entries, key=lambda item: (item["result_class"], item["identity"]))

    def _entry(
        self,
        identity: str,
        result_class: ResultClass,
        text: str,
        metadata: dict[str, list[str]],
    ) -> dict[str, Any]:
        try:
            vector = self.vectorizer.vector(text)
        except Exception as error:
            raise RetrievalError(f"vector generation failed for {identity}: {error}") from error
        return {
            "identity": identity,
            "result_class": result_class.value,
            "text": text,
            "metadata": {key: sorted(set(value)) for key, value in sorted(metadata.items())},
            "vector": list(vector),
        }

    def _document_metadata(self, items: list[SourceObject]) -> dict[str, dict[str, list[str]]]:
        roles = {
            "conformed-submission-type": "document_type",
            "conformed-period-of-report": "period",
            "central-index-key": "entity_id",
        }
        result: dict[str, dict[str, list[str]]] = {}
        for item in items:
            key = roles.get(item.role)
            value = item.attributes.get("value")
            if key and value:
                values = [value]
                if key == "entity_id" and value.isdigit():
                    values.append(value.lstrip("0") or "0")
                result.setdefault(item.document_id, {}).setdefault(key, []).extend(values)
        return result

    def _entity_ids(self, object_id: str, object_type: str, payload: dict[str, Any]) -> list[str]:
        values = self._payload_values(
            payload, "entity_id", "issuer_id", "cik", "from_object_id"
        )
        values.extend(value.zfill(10) for value in tuple(values) if value.isdigit())
        if object_type == "entity":
            values.append(object_id)
        return sorted(set(values))

    def _payload_values(self, payload: dict[str, Any], *keys: str) -> list[str]:
        values: list[str] = []
        for key in keys:
            value = payload.get(key)
            if isinstance(value, (str, int, float)):
                values.append(str(value))
        return values

    def _filter_reason(
        self,
        entry: dict[str, Any],
        filters: MetadataConstraints,
        result_classes: tuple[ResultClass, ...],
    ) -> str | None:
        if ResultClass(entry["result_class"]) not in result_classes:
            return "result-class"
        checks = (
            ("document_id", filters.document_ids),
            ("artifact_id", filters.artifact_ids),
            ("entity_id", filters.entity_ids),
            ("document_type", filters.document_types),
            ("source_kind", filters.source_kinds),
            ("source_role", filters.source_roles),
            ("knowledge_type", filters.knowledge_types),
            ("knowledge_status", tuple(item.value for item in filters.knowledge_statuses)),
        )
        for key, expected in checks:
            if expected and not set(expected) & set(entry["metadata"].get(key, [])):
                return f"metadata:{key}"
        periods = entry["metadata"].get("period", [])
        if filters.period_from and not any(value >= filters.period_from for value in periods):
            return "metadata:period-from"
        if filters.period_to and not any(value <= filters.period_to for value in periods):
            return "metadata:period-to"
        return None

    def _rationale(
        self, entry: dict[str, Any], score: Score, filters: MetadataConstraints
    ) -> tuple[str, ...]:
        reasons = [
            f"vector candidate score {score.vector:.6f}",
            f"lexical overlap score {score.lexical:.6f}",
        ]
        if filters != MetadataConstraints():
            reasons.append("all requested metadata constraints satisfied")
        return tuple(reasons)

    def _validate_query(self, query: RetrievalQuery) -> None:
        if not query.text.strip():
            raise RetrievalError("query text must not be blank")
        if not query.result_classes:
            raise RetrievalError("at least one result class is required")
        if query.constraints.unsupported:
            names = ", ".join(query.constraints.unsupported)
            raise RetrievalError(f"unsupported metadata constraints: {names}")
        if not 1 <= query.max_results <= 100:
            raise RetrievalError("max_results must be between 1 and 100")
        if not query.max_results <= query.candidate_limit <= 1000:
            raise RetrievalError("candidate_limit must be between max_results and 1000")
        if not 0 <= query.context_radius <= 4096:
            raise RetrievalError("context_radius must be between 0 and 4096")
        if not 1 <= query.evidence_budget_bytes <= 10_000_000:
            raise RetrievalError("evidence budget is outside supported bounds")
        if not 0.0 <= query.minimum_score <= 1.0:
            raise RetrievalError("minimum_score must be between 0 and 1")
        filters = query.constraints
        if filters.period_from and filters.period_to and filters.period_from > filters.period_to:
            raise RetrievalError("period_from must not follow period_to")

    def _load_generation(self, generation_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        directory = self.generations / generation_id
        try:
            manifest = self._read_json(directory / "manifest.json")
            content = (directory / "index.json").read_bytes()
        except OSError as error:
            raise RetrievalError(f"retrieval generation is incomplete: {error}") from error
        if manifest.get("schema_version") != _SCHEMA:
            raise RetrievalError("unsupported retrieval manifest schema")
        if manifest.get("generation_id") != generation_id:
            raise RetrievalError("retrieval generation identity mismatch")
        if hashlib.sha256(content).hexdigest() != manifest.get("index_sha256"):
            raise RetrievalError("retrieval index digest mismatch")
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as error:
            raise RetrievalError(f"retrieval index is not valid JSON: {error}") from error
        if payload.get("schema_version") != _SCHEMA or not isinstance(payload.get("entries"), list):
            raise RetrievalError("retrieval index contract is invalid")
        if len(payload["entries"]) != manifest.get("indexed_items"):
            raise RetrievalError("retrieval manifest inventory mismatch")
        return payload, manifest

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RetrievalError(f"cannot read retrieval state {path}: {error}") from error
        if not isinstance(value, dict):
            raise RetrievalError(f"retrieval record is not an object: {path}")
        return value

    def _atomic_write(self, path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
