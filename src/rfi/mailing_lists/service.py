"""Bounded acquisition orchestration and repository-owned discussion queries."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, Callable
from urllib.parse import quote

from rfi.artifacts import ArtifactContent
from rfi.mailing_lists.contracts import (
    AcquisitionMessage,
    AcquisitionLimits,
    AcquisitionManifest,
    AcquisitionPreview,
    AcquisitionRunStatus,
    RelationshipAcquisitionStatus,
    ConnectivityState,
    DiscussionProjection,
    DiscussionSummary,
    InclusionReason,
    MailingListArchive,
    MailingListError,
    MailingListSource,
    LoreTransportPolicy,
    MessageDetail,
    MessageSummary,
    SelectionCriteria,
    normalize_lore_archive,
)
from rfi.mailing_lists.parser import normalize_message_id, parse_message, unavailable_ancestor
from rfi.mailing_lists.repository import MailingListRepository, message_key


class MailingListSourceService:
    """Shared validation and creation boundary for repository-global Lore sources."""

    _SOURCE_FIELDS = {
        "source_id", "display_name", "provider", "list_id", "archive_base_url", "transport"
    }
    _TRANSPORT_FIELDS = {
        "user_agent", "minimum_request_interval_seconds", "maximum_concurrency",
        "timeout_seconds", "maximum_response_bytes", "maximum_attempts_per_request",
        "backoff_initial_seconds", "backoff_maximum_seconds",
    }

    def __init__(self, repository: MailingListRepository) -> None:
        self.repository = repository

    def validate(self, value: Any) -> MailingListSource:
        if not isinstance(value, dict):
            raise MailingListError("invalid_source", "source profile must be an object")
        unknown = sorted(set(value) - self._SOURCE_FIELDS)
        if unknown:
            raise MailingListError(
                "invalid_source", f"unknown source-profile field: {unknown[0]}"
            )
        transport_value = value.get("transport", {})
        if not isinstance(transport_value, dict):
            raise MailingListError("invalid_source", "transport must be an object")
        unknown_transport = sorted(set(transport_value) - self._TRANSPORT_FIELDS)
        if unknown_transport:
            raise MailingListError(
                "invalid_source", f"unknown transport field: {unknown_transport[0]}"
            )
        defaults = asdict(LoreTransportPolicy())
        defaults.update(transport_value)
        provider = self._text(value, "provider")
        if provider != "lore-public-inbox":
            raise MailingListError(
                "invalid_source", "provider must be lore-public-inbox"
            )
        try:
            transport = LoreTransportPolicy(**defaults)
        except (TypeError, ValueError) as error:
            raise MailingListError(
                "invalid_source", "transport policy values have invalid types"
            ) from error
        archive_id, canonical_url = normalize_lore_archive(
            self._text(value, "archive_base_url")
        )
        list_id = self._text(value, "list_id")
        if list_id != archive_id:
            raise MailingListError(
                "invalid_source", "archive/list identity must match the canonical Lore URL"
            )
        source = MailingListSource(
            self._text(value, "source_id"),
            list_id,
            self._text(value, "display_name"),
            canonical_url,
            provider,
            transport,
        )
        # Exercise the authoritative governed-source contract without persisting it.
        from rfi.acquisition import SourceProfile

        try:
            SourceProfile(
                source.source_id,
                source.display_name,
                True,
                source.provider,
                {"archive_base_url": source.archive_base_url, "list_id": source.list_id},
                {
                    "repository_projection": "mailing-list",
                    "transport": asdict(source.transport),
                },
            )
        except ValueError as error:
            raise MailingListError("invalid_source", str(error)) from error
        if not source.list_id.strip():
            raise MailingListError("invalid_source", "archive/list identity must not be blank")
        if not source.archive_base_url.startswith("https://"):
            raise MailingListError("invalid_source", "archive URL must use HTTPS")
        return source

    def create(self, value: Any) -> tuple[MailingListSource, bool]:
        source = self.validate(value)
        return source, self.repository.configure_source(source)

    @staticmethod
    def _text(value: dict[str, Any], field: str) -> str:
        result = value.get(field)
        if not isinstance(result, str) or not result.strip():
            raise MailingListError("invalid_source", f"{field} must not be blank")
        return result.strip()


def derive_projection(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rebuild authoritative header-derived organization from retained evidence."""
    combined: dict[tuple[str, str], dict[str, Any]] = {}
    states: dict[tuple[str, str], set[str]] = {}
    policy_limits: dict[tuple[str, str], bool] = {}
    for record in records:
        key = (record["source_id"], record["external_message_id"])
        prior = combined.get(key)
        if prior is not None and prior["artifact_id"] != record["artifact_id"]:
            raise MailingListError(
                "message_id_conflict", "retained Message-ID has conflicting artifacts"
            )
        combined[key] = record
        states.setdefault(key, set()).add(record["connectivity_state"])
        policy_limits[key] = policy_limits.get(key, False) or bool(
            record.get("descendant_policy_limited", False)
        )
    by_external = {key: value for key, value in combined.items()}
    classifications: dict[tuple[str, str], tuple[str, tuple[str, str] | None, int | None]] = {}
    groups: dict[tuple[str, str], list[tuple[tuple[str, str], int]]] = {}
    for key, record in combined.items():
        parsed = record["parsed"]
        if parsed.external_message_id is None:
            classifications[key] = (ConnectivityState.QUARANTINED.value, None, None)
            continue
        path: list[tuple[str, str]] = []
        current = key
        seen: set[tuple[str, str]] = set()
        failure: str | None = None
        while True:
            if current in seen:
                failure = ConnectivityState.QUARANTINED.value
                break
            seen.add(current)
            path.append(current)
            current_record = by_external[current]
            parent = current_record["parsed"].immediate_parent_id
            if not parent:
                root = current
                break
            parent_key = (current[0], parent)
            if parent_key not in by_external:
                failure = ConnectivityState.INCOMPLETE.value
                break
            current = parent_key
        if failure:
            classifications[key] = (failure, None, None)
            continue
        depth = len(path) - 1
        requested_states = states[key]
        # A run-wide incomplete outcome is audit evidence about the acquisition, not
        # structural evidence about every component retained by that run. Once this
        # message's actual parent path closes at a retained root, only a connected
        # observation can clear a component-local truncation or quarantine marker;
        # inherited incomplete observations alone do not make the closed path incomplete.
        state = (
            ConnectivityState.CONNECTED.value
            if ConnectivityState.CONNECTED.value in requested_states
            else ConnectivityState.TRUNCATED.value
            if ConnectivityState.TRUNCATED.value in requested_states
            else ConnectivityState.QUARANTINED.value
            if ConnectivityState.QUARANTINED.value in requested_states
            else ConnectivityState.CONNECTED.value
        )
        classifications[key] = (state, root, depth)
        if state != ConnectivityState.QUARANTINED.value:
            groups.setdefault(root, []).append((key, depth))

    messages: list[dict[str, Any]] = []
    for key, record in sorted(combined.items()):
        parsed = record["parsed"]
        state, _root, _depth = classifications[key]
        parent_key = (key[0], parsed.immediate_parent_id) if parsed.immediate_parent_id else None
        parent_message_key = (
            message_key(*parent_key) if parent_key and parent_key in combined else None
        )
        messages.append({
            "message_key": message_key(*key), "source_id": key[0],
            "external_message_id": key[1], "artifact_id": record["artifact_id"],
            "document_id": record["document_id"], "subject": parsed.subject,
            "normalized_subject": parsed.normalized_subject, "sender": parsed.sender,
            "message_date": parsed.message_date, "text_content": parsed.text_content,
            "connectivity_state": state,
            "is_tombstone": bool(record.get("is_tombstone", False)),
            "parent_external_message_id": parsed.immediate_parent_id,
            "parent_message_key": parent_message_key,
            "canonical": {
                "external_message_id": parsed.external_message_id,
                "references": list(parsed.references),
                "parse_warnings": list(parsed.parse_warnings),
                "relationship_basis": "header",
                "normalized_subject_is_identity": False,
                "is_tombstone": bool(record.get("is_tombstone", False)),
                "unavailable_details": record.get("unavailable_details"),
            },
        })
    discussions: list[dict[str, Any]] = []
    for root, members in sorted(groups.items()):
        component_states = [classifications[key][0] for key, _depth in members]
        component_state = (
            ConnectivityState.INCOMPLETE.value
            if ConnectivityState.INCOMPLETE.value in component_states
            else ConnectivityState.TRUNCATED.value
            if ConnectivityState.TRUNCATED.value in component_states
            else ConnectivityState.CONNECTED.value
        )
        if (
            component_state == ConnectivityState.INCOMPLETE.value
            and not any(depth > 0 for _key, depth in members)
        ):
            continue
        dates = sorted(
            value
            for key, _depth in members
            if (value := combined[key]["parsed"].message_date) is not None
        )
        digest = hashlib.sha256(f"{root[0]}\0{root[1]}".encode()).hexdigest()
        discussions.append({
            "discussion_id": f"discussion-{digest[:32]}", "source_id": root[0],
            "root_message_key": message_key(*root), "connectivity_state": component_state,
            "descendant_truncated": component_state == ConnectivityState.TRUNCATED.value,
            "descendant_policy_limited": any(policy_limits[key] for key, _depth in members),
            "first_message_at": dates[0] if dates else None,
            "last_message_at": dates[-1] if dates else None,
            "members": [(message_key(*key), depth) for key, depth in members],
            "canonical": {
                "root_external_message_id": root[1],
                "connectivity_validated": True,
                "relationship_authority": "header",
                "descendant_policy_limited": any(
                    policy_limits[key] for key, _depth in members
                ),
                "tombstone_count": sum(
                    bool(combined[key].get("is_tombstone", False))
                    for key, _depth in members
                ),
            },
        })
    return messages, discussions


class MailingListAcquisitionService:
    """Two-stage bounded acquisition with fail-closed connected admission."""

    def __init__(
        self,
        repository: MailingListRepository,
        archive: MailingListArchive,
        *,
        clock: Callable[[], str] | None = None,
        identifiers: Callable[[], str] | None = None,
    ) -> None:
        self.repository = repository
        self.archive = archive
        self.clock = clock or (lambda: datetime.now(UTC).isoformat())
        self.identifiers = identifiers or (lambda: f"mailrun-{uuid.uuid4().hex}")

    def preview(
        self, source_id: str, criteria: SelectionCriteria, limits: AcquisitionLimits,
        *, cancelled: Callable[[], bool] | None = None,
    ) -> AcquisitionPreview:
        plan = self._plan(source_id, criteria, limits, cancelled=cancelled)
        return AcquisitionPreview(
            source_id, criteria, limits, plan["seeds"], len(plan["items"]),
            dict(Counter(item["inclusion_reason"] for item in plan["items"].values())),
            plan["state"], plan["truncated"], tuple(plan["warnings"]),
            plan["discovery_complete"], plan["required_ancestry_complete"],
            plan["descendant_policy_complete"], plan["descendant_policy_limited"],
            plan["unexpected_truncation"],
        )

    def acquire(
        self, source_id: str, criteria: SelectionCriteria, limits: AcquisitionLimits,
        *, cancelled: Callable[[], bool] | None = None, discovery_offset: int = 0,
        coverage_batch_id: str | None = None, prior_batches_complete: bool = True,
    ) -> AcquisitionManifest:
        # Configuration errors are not acquisition attempts and cannot satisfy the
        # run table's governed-source foreign key.
        source = self.repository.source(source_id)
        run_id = self.identifiers()
        requested_at = self.clock()
        effective_batch_id = coverage_batch_id or hashlib.sha256(
            json.dumps(
                {
                    "source_id": source_id,
                    "criteria": asdict(criteria),
                    "limits": asdict(limits),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()[:32]
        continuation = (
            self.repository.relationship_resume_state(
                source_id, effective_batch_id, discovery_offset
            )
            if coverage_batch_id is not None else None
        )
        try:
            plan = self._plan(
                source_id, criteria, limits, cancelled=cancelled,
                discovery_offset=discovery_offset, continuation=continuation,
            )
        except MailingListError as error:
            if error.code == "acquisition_cancelled":
                raise
            self.repository.record_failure(
                run_id, source_id, requested_at, criteria, limits, error
            )
            raise
        retained: list[dict[str, Any]] = []
        created = 0
        idempotent = 0
        for external_id, item in sorted(plan["items"].items()):
            if item.get("reuse", False):
                key = message_key(source_id, external_id)
                doc_id = str(item["document_id"])
                artifact_id = str(item["artifact_id"])
                artifact_created = False
            elif item.get("is_tombstone", False):
                key, doc_id, artifact_id, artifact_created = (
                    self.repository.retain_unavailable_ancestor(
                        source, run_id, external_id, requested_at,
                        item["unavailable_details"]["attempts"],
                    )
                )
            else:
                key, doc_id, artifact_id, artifact_created = self.repository.retain_message(
                    source, run_id, external_id, item["parsed"], item["raw"],
                    item["location"], item["inclusion_reason"], requested_at,
                    item["fallback_archive_url"],
                )
            del key
            created += int(artifact_created)
            idempotent += int(not artifact_created)
            retained.append({
                "source_id": source_id, "external_message_id": external_id,
                "artifact_id": artifact_id, "document_id": doc_id,
                "connectivity_state": plan["item_states"].get(external_id, plan["state"].value),
                "inclusion_reason": item["inclusion_reason"], "is_seed": item["is_seed"],
                "parsed": item["parsed"],
                "fallback_archive_url": item["fallback_archive_url"],
                "descendant_policy_limited": plan["descendant_policy_limited"],
                "is_tombstone": bool(item.get("is_tombstone", False)),
                "unavailable_details": item.get("unavailable_details"),
            })
        existing = self.repository.parsed_retained_records()
        messages, discussions = derive_projection(existing + retained)
        retained_keys = {
            message_key(item["source_id"], item["external_message_id"])
            for item in retained
        }
        relationships = sum(
            item["message_key"] in retained_keys
            and bool(item["parent_external_message_id"])
            for item in messages
        )
        run_discussions = sum(
            any(key in retained_keys for key, _depth in item["members"])
            for item in discussions
            if item["source_id"] == source_id
        )
        coverage_complete = (
            prior_batches_complete
            and plan["discovery_complete"]
            and plan["required_ancestry_complete"]
            and plan["relationship_status"] in {
                RelationshipAcquisitionStatus.COMPLETE,
                RelationshipAcquisitionStatus.POLICY_TRUNCATED,
            }
            and not plan["unexpected_truncation"]
            and not plan["failures"]
            and plan["state"] == ConnectivityState.CONNECTED
        )
        manifest = AcquisitionManifest(
            run_id, source_id, requested_at, criteria, limits, plan["seeds"], len(retained),
            relationships,
            run_discussions,
            dict(Counter(item["inclusion_reason"] for item in retained)),
            plan["state"], plan["truncated"], tuple(plan["warnings"]), created, idempotent,
            AcquisitionRunStatus.PARTIAL if plan["failures"] else AcquisitionRunStatus.SUCCEEDED,
            plan["failures"][0].code if plan["failures"] else None,
            any(error.retryable for error in plan["failures"]),
            discovery_offset, plan["discovery_has_more"],
            plan["relationship_truncated"], effective_batch_id, coverage_complete,
            tuple(sorted(
                external_id for external_id, item in plan["items"].items()
                if item["fallback_archive_url"] is not None
            )),
            plan["discovery_complete"], plan["required_ancestry_complete"],
            plan["descendant_policy_complete"], plan["descendant_policy_limited"],
            plan["unexpected_truncation"],
            tuple(sorted(
                external_id for external_id, item in plan["items"].items()
                if item.get("is_tombstone", False)
            )),
            plan["relationship_status"], plan["continuation"],
            plan["relationship_records_processed"],
        )
        self.repository.publish(manifest, retained, messages, discussions)
        return manifest

    def rebuild(self) -> dict[str, int | str]:
        records = self.repository.parsed_retained_records()
        messages, discussions = derive_projection(records)
        self.repository.replace_derived(messages, discussions)
        return {
            "messages": len(messages), "discussions": len(discussions),
            "relationships": sum(bool(item["parent_external_message_id"]) for item in messages),
            "result": "PASS",
        }

    def _plan(self, source_id: str, criteria: SelectionCriteria,
              limits: AcquisitionLimits, *,
              cancelled: Callable[[], bool] | None = None,
              discovery_offset: int = 0,
              continuation: dict[str, Any] | None = None) -> dict[str, Any]:
        self.repository.source(source_id)
        self._check_cancelled(cancelled)
        if continuation is None:
            if discovery_offset == 0:
                seeds, seed_truncated = self.archive.discover(criteria, limits.seed_limit)
            else:
                discover_page = getattr(self.archive, "discover_page", None)
                if discover_page is None:
                    raise MailingListError(
                        "pagination_unsupported", "mailing-list archive cannot continue discovery"
                    )
                seeds, seed_truncated = discover_page(
                    criteria, limits.seed_limit, discovery_offset
                )
        else:
            seeds = tuple(str(item) for item in continuation.get("seeds", ()))
            seed_truncated = bool(continuation.get("discovery_has_more", False))
        self._check_cancelled(cancelled)
        if not seeds:
            raise MailingListError("no_seed_matches", "bounded selection found no messages")
        items: dict[str, dict[str, Any]] = {}
        warnings: list[str] = []
        failures: list[MailingListError] = []
        quarantined = False
        context_fetches = 0
        retained = {
            item["external_message_id"]: item
            for item in self.repository.parsed_retained_records()
            if item["source_id"] == source_id
        }
        acquired_ids = set(
            str(item) for item in (continuation or {}).get("acquired_ids", ())
        )
        resuming = continuation is not None

        def known(external_id: str) -> dict[str, Any] | None:
            return items.get(external_id) or retained.get(external_id)

        def fetch(external_id: str, reason: InclusionReason, is_seed: bool = False) -> str | None:
            nonlocal context_fetches, quarantined
            self._check_cancelled(cancelled)
            expected = normalize_message_id(external_id) or external_id
            existing = known(expected)
            if existing is not None and not is_seed:
                if is_seed:
                    acquired_ids.add(expected)
                if not resuming and expected in retained and expected not in items:
                    prior = retained[expected]
                    items[expected] = {
                        "raw": None, "location": "", "parsed": prior["parsed"],
                        "inclusion_reason": reason.value, "is_seed": False,
                        "forced_state": None, "fallback_archive_url": None,
                        "is_tombstone": bool(prior.get("is_tombstone", False)),
                        "unavailable_details": prior.get("unavailable_details"),
                        "reuse": True, "artifact_id": prior["artifact_id"],
                        "document_id": prior["document_id"],
                    }
                    acquired_ids.add(expected)
                return expected
            archive_message = self.archive.fetch(expected)
            parsed = parse_message(archive_message.raw)
            storage_id = parsed.external_message_id or (
                "malformed-" + hashlib.sha256(archive_message.raw).hexdigest()[:32]
            )
            if parsed.external_message_id != expected:
                quarantined = True
                warnings.append(f"archive response Message-ID mismatch for {expected}")
            if not is_seed:
                context_fetches += 1
            items[storage_id] = {
                "raw": archive_message.raw, "location": archive_message.location,
                "parsed": parsed, "inclusion_reason": reason.value, "is_seed": is_seed,
                "forced_state": (
                    ConnectivityState.QUARANTINED.value
                    if parsed.external_message_id != expected else None
                ),
                "fallback_archive_url": archive_message.fallback_archive_url,
                "is_tombstone": False,
                "unavailable_details": None,
            }
            acquired_ids.add(storage_id)
            return storage_id

        seed_reason = (
            InclusionReason.EXPLICIT_REQUEST if criteria.message_ids else InclusionReason.SEED_MATCH
        )
        state = dict(continuation or {})
        if continuation is None:
            normalized_seeds = []
            for seed in seeds:
                try:
                    stored = fetch(seed, seed_reason, True)
                    if stored:
                        normalized_seeds.append(stored)
                except MailingListError as error:
                    if error.code == "acquisition_cancelled":
                        raise
                    failures.append(error)
                    warnings.append(f"seed rejected: {error.code}")
            seeds = tuple(normalized_seeds)
            state = {
                "version": 1,
                "phase": "ancestry",
                "seeds": list(seeds),
                "discovery_has_more": seed_truncated,
                "acquired_ids": sorted(acquired_ids),
                "ancestry_stack": [
                    {"current": seed, "seen": []} for seed in reversed(seeds)
                ],
                "reply_stack": [],
                "completed_reply_ids": [],
                "policy_truncated": False,
            }

        ancestry_stack = list(state.get("ancestry_stack", []))
        reply_stack = list(state.get("reply_stack", []))
        completed_reply_ids = set(
            str(item) for item in state.get("completed_reply_ids", ())
        )
        phase = str(state.get("phase", "ancestry"))
        policy_truncated = bool(state.get("policy_truncated", False))
        retry_ancestry: list[dict[str, Any]] = []

        while phase == "ancestry" and ancestry_stack:
            frame = dict(ancestry_stack[-1])
            current = str(frame["current"])
            seen = set(str(item) for item in frame.get("seen", ()))
            if current in seen:
                quarantined = True
                failures.append(MailingListError("relationship_cycle", "cycle in ancestry"))
                warnings.append("cycle detected in immediate-reply ancestry")
                break
            next_seen = {*seen, current}
            current_item = known(current)
            if current_item is None:
                failures.append(MailingListError("continuation_corrupt", "ancestor is missing"))
                break
            parent = current_item["parsed"].immediate_parent_id
            if not parent:
                ancestry_stack.pop()
                continue
            if known(parent) is not None:
                if not resuming:
                    fetch(parent, InclusionReason.ANCESTOR)
                acquired_ids.add(parent)
                ancestry_stack[-1] = {
                    "current": parent, "seen": sorted(next_seen)
                }
                continue
            if context_fetches >= limits.context_limit:
                break
            try:
                fetch(parent, InclusionReason.ANCESTOR)
            except MailingListError as error:
                if error.code == "acquisition_cancelled":
                    raise
                if error.code == "archive_message_not_found":
                    attempts = error.details.get("attempts")
                    if not isinstance(attempts, list) or len(attempts) != 2 or any(
                        not isinstance(item, dict)
                        or item.get("http_status") != 404
                        or not isinstance(item.get("location"), str)
                        for item in attempts
                    ):
                        raise MailingListError(
                            "invalid_unavailability_evidence",
                            "confirmed Lore absence lacks valid two-path evidence",
                        ) from error
                    context_fetches += 1
                    items[parent] = {
                        "raw": None, "location": str(attempts[-1]["location"]),
                        "parsed": unavailable_ancestor(parent),
                        "inclusion_reason": InclusionReason.ANCESTOR.value,
                        "is_seed": False, "forced_state": None,
                        "fallback_archive_url": None, "is_tombstone": True,
                        "unavailable_details": {"attempts": attempts},
                    }
                    acquired_ids.add(parent)
                    warnings.append(f"confirmed unavailable ancestor tombstoned: {parent}")
                    ancestry_stack[-1] = {
                        "current": parent, "seen": sorted(next_seen)
                    }
                else:
                    failures.append(error)
                    warnings.append(f"required ancestor unavailable: {parent}")
                    retry_ancestry.append(dict(ancestry_stack.pop()))
            else:
                ancestry_stack[-1] = {
                    "current": parent, "seen": sorted(next_seen)
                }

        if phase == "ancestry" and not ancestry_stack:
            phase = "replies"
            scoped = {
                key: known(key) for key in acquired_ids if known(key) is not None
            }
            roots = sorted(
                key for key, item in scoped.items()
                if item is not None and not item["parsed"].immediate_parent_id
            )
            if not reply_stack:
                reply_stack = [
                    {"message_id": root, "depth": 0, "offset": 0, "pending": [],
                     "has_more": True, "enumerated": False}
                    for root in reversed(roots)
                ]

        while phase == "replies" and reply_stack:
            frame = reply_stack[-1]
            parent = str(frame["message_id"])
            depth = int(frame["depth"])
            if parent in completed_reply_ids:
                reply_stack.pop()
                continue
            if depth >= limits.descendant_depth:
                policy_truncated = True
                completed_reply_ids.add(parent)
                reply_stack.pop()
                continue
            parent_item = known(parent)
            if parent_item is None:
                failures.append(MailingListError("continuation_corrupt", "reply parent is missing"))
                break
            if parent_item.get("is_tombstone", False):
                completed_reply_ids.add(parent)
                reply_stack.pop()
                continue
            pending = list(frame.get("pending", []))
            if pending:
                child = str(pending.pop(0))
                frame["pending"] = pending
                if child in {str(item["message_id"]) for item in reply_stack}:
                    failures.append(MailingListError("relationship_cycle", "cycle in replies"))
                    warnings.append("cycle detected in reply traversal")
                    break
                if known(child) is None:
                    if context_fetches >= limits.context_limit:
                        frame["pending"] = [child, *pending]
                        break
                    try:
                        fetch(child, InclusionReason.DESCENDANT)
                    except MailingListError as error:
                        if error.code == "acquisition_cancelled":
                            raise
                        frame["pending"] = [child, *pending]
                        failures.append(error)
                        warnings.append(f"descendant unavailable: {error.code}")
                        break
                elif not resuming:
                    fetch(child, InclusionReason.DESCENDANT)
                    acquired_ids.add(child)
                reply_stack.append({
                    "message_id": child, "depth": depth + 1, "offset": 0,
                    "pending": [], "has_more": True, "enumerated": False,
                })
                continue
            if bool(frame.get("has_more", True)) or not bool(frame.get("enumerated", False)):
                remaining = limits.context_limit - context_fetches
                if remaining <= 0:
                    break
                page_size = min(50, remaining)
                page = getattr(self.archive, "direct_children_page", None)
                if page is None:
                    if int(frame.get("offset", 0)):
                        failures.append(MailingListError(
                            "pagination_unsupported",
                            "mailing-list archive cannot resume relationship pagination",
                        ))
                        break
                    page = lambda message_id, limit, _offset: self.archive.direct_children(
                        message_id, limit
                    )
                try:
                    page_offset = int(frame.get("offset", 0))
                    if page_offset == 0:
                        children, has_more = self.archive.direct_children(parent, page_size)
                    else:
                        children, has_more = page(parent, page_size, page_offset)
                except MailingListError as error:
                    failures.append(error)
                    warnings.append(f"descendant enumeration failed: {error.code}")
                    break
                ordered = list(dict.fromkeys(sorted(children)))
                if has_more and not ordered:
                    failures.append(MailingListError(
                        "pagination_no_progress", "relationship page made no progress"
                    ))
                    break
                frame["offset"] = int(frame.get("offset", 0)) + len(ordered)
                frame["pending"] = ordered
                frame["has_more"] = bool(has_more)
                frame["enumerated"] = True
                continue
            completed_reply_ids.add(parent)
            reply_stack.pop()

        if not items and failures and not acquired_ids:
            retryable = any(error.retryable for error in failures)
            first = next((error for error in failures if error.retryable), failures[0])
            raise MailingListError(
                first.code,
                "bounded mailing-list acquisition obtained no usable messages",
                retryable=retryable,
            ) from first

        if (
            phase == "replies" and not reply_stack and not failures
            and not self.archive.descendant_enumeration_complete
        ):
            failures.append(MailingListError(
                "provider_relationship_incomplete",
                "provider could not prove relationship enumeration complete",
                retryable=True,
            ))
            warnings.append("provider relationship enumeration remained incomplete")
        required_ancestry_complete = (
            not ancestry_stack and not retry_ancestry and phase == "replies"
        )
        pending = bool(ancestry_stack or reply_stack) and not failures
        relationship_status = (
            RelationshipAcquisitionStatus.FAILED if failures else
            RelationshipAcquisitionStatus.CONTINUATION_PENDING if pending else
            RelationshipAcquisitionStatus.POLICY_TRUNCATED if policy_truncated else
            RelationshipAcquisitionStatus.COMPLETE
        )
        descendant_policy_complete = relationship_status in {
            RelationshipAcquisitionStatus.COMPLETE,
            RelationshipAcquisitionStatus.POLICY_TRUNCATED,
        }
        continuation_value = None
        if relationship_status in {
            RelationshipAcquisitionStatus.CONTINUATION_PENDING,
            RelationshipAcquisitionStatus.FAILED,
        }:
            continuation_value = {
                "version": 1, "phase": "ancestry" if retry_ancestry else phase,
                "seeds": list(seeds),
                "discovery_has_more": seed_truncated,
                "acquired_ids": sorted(acquired_ids),
                "ancestry_stack": retry_ancestry or ancestry_stack,
                "reply_stack": reply_stack,
                "completed_reply_ids": sorted(completed_reply_ids),
                "policy_truncated": policy_truncated,
            }
        provisional = []
        for external_id, item in items.items():
            provisional.append({
                "source_id": source_id, "external_message_id": external_id,
                "artifact_id": (
                    retained[external_id]["artifact_id"]
                    if external_id in retained else "preview"
                ),
                "document_id": (
                    retained[external_id]["document_id"]
                    if external_id in retained else "preview"
                ),
                "connectivity_state": item["forced_state"] or ConnectivityState.CONNECTED.value,
                "parsed": item["parsed"],
                "is_tombstone": bool(item.get("is_tombstone", False)),
                "unavailable_details": item.get("unavailable_details"),
            })
        projected, _ = derive_projection(
            self.repository.parsed_retained_records() + provisional
        )
        item_states = {
            item["external_message_id"]: item["connectivity_state"] for item in projected
        }
        if quarantined or any(
            value == ConnectivityState.QUARANTINED.value for value in item_states.values()
        ):
            state = ConnectivityState.QUARANTINED
        elif failures or not required_ancestry_complete or any(
            value == ConnectivityState.INCOMPLETE.value for value in item_states.values()
        ):
            state = ConnectivityState.INCOMPLETE
        elif relationship_status == RelationshipAcquisitionStatus.CONTINUATION_PENDING:
            state = ConnectivityState.TRUNCATED
        else:
            state = ConnectivityState.CONNECTED
        unexpected_truncation = bool(failures) or (
            relationship_status == RelationshipAcquisitionStatus.CONTINUATION_PENDING
        )
        return {
            "seeds": tuple(seeds), "items": items, "warnings": sorted(set(warnings)),
            "state": state, "truncated": unexpected_truncation,
            "discovery_has_more": seed_truncated,
            "discovery_complete": not seed_truncated,
            "required_ancestry_complete": required_ancestry_complete,
            "descendant_policy_complete": descendant_policy_complete,
            "descendant_policy_limited": policy_truncated,
            "unexpected_truncation": unexpected_truncation,
            "relationship_truncated": (
                relationship_status == RelationshipAcquisitionStatus.CONTINUATION_PENDING
            ),
            "item_states": item_states, "failures": tuple(failures),
            "relationship_status": relationship_status,
            "continuation": continuation_value,
            "relationship_records_processed": context_fetches,
        }

    @staticmethod
    def _check_cancelled(cancelled: Callable[[], bool] | None) -> None:
        if cancelled is not None and cancelled():
            raise MailingListError(
                "acquisition_cancelled", "mailing-list acquisition was cancelled"
            )


class MailingListQueryService:
    """Bounded read projection for CLI, browser, and future model-facing consumers."""

    def __init__(self, repository: MailingListRepository) -> None:
        self.repository = repository

    def sources(self) -> tuple[dict[str, Any], ...]:
        counts = {
            row["source_id"]: row["count"]
            for row in self.repository.rows(
                "SELECT source_id,count(*) AS count FROM mailing_list_discussions "
                "GROUP BY source_id"
            )
        }
        return tuple({**asdict(source), "discussion_count": int(counts.get(source.source_id, 0))}
                     for source in self.repository.sources())

    def acquisition_run(self, run_id: str) -> dict[str, Any]:
        rows = self.repository.rows(
            "SELECT run_id,source_id,requested_at,lifecycle_status,status AS connectivity_state,"
            "seed_limit,context_limit,seed_count,message_count,error_code,retryable,canonical_json "
            "FROM mailing_list_runs WHERE run_id=?", (run_id,),
        )
        if not rows:
            raise MailingListError("unknown_run", "unknown mailing-list acquisition run")
        row = dict(rows[0])
        row["retryable"] = bool(row["retryable"])
        row["manifest"] = json.loads(str(row.pop("canonical_json")))
        return row

    def acquisition_messages(
        self, run_id: str, limit: int = 100
    ) -> tuple[AcquisitionMessage, ...]:
        self._limit(limit)
        run = self.acquisition_run(run_id)
        fallback_ids = set(run["manifest"].get("fallback_message_ids", ()))
        rows = self.repository.rows(
            self._message_select(
                prefix="mailing_list_run_items i JOIN mailing_list_messages m "
                "ON m.source_id=i.source_id AND m.external_message_id=i.external_message_id",
                extra_select=",i.inclusion_reason,i.is_seed,dm.discussion_id",
            )
            + " WHERE i.run_id=? ORDER BY i.is_seed DESC,m.message_date,m.message_key LIMIT ?",
            (run_id, limit),
        )
        result = []
        for row in rows:
            summary = self._message(row)
            source = self.repository.source(str(row["source_id"]))
            token = (summary.external_message_id or "").strip("<>")
            reason = str(row["inclusion_reason"])
            direct = reason in {
                InclusionReason.SEED_MATCH.value, InclusionReason.EXPLICIT_REQUEST.value
            }
            fallback = summary.external_message_id in fallback_ids
            archive_url = (
                "https://lore.kernel.org/all/" if fallback
                else source.archive_base_url
            )
            result.append(AcquisitionMessage(
                summary, reason, direct, not direct,
                "" if summary.is_tombstone else
                f"{archive_url}{quote(token, safe='@')}/" if token else "",
                str(row["discussion_id"]) if row.get("discussion_id") else None,
                fallback,
            ))
        return tuple(result)

    def discussions(self, source_id: str, limit: int = 25, offset: int = 0
                    ) -> tuple[DiscussionSummary, ...]:
        self._limit(limit)
        self.repository.require_derived()
        rows = self.repository.rows(
            "SELECT d.*,s.list_id,m.subject AS root_subject FROM mailing_list_discussions d "
            "JOIN mailing_list_sources s ON s.source_id=d.source_id "
            "JOIN mailing_list_messages m ON m.message_key=d.root_message_key "
            "WHERE d.source_id=? ORDER BY d.last_message_at DESC,d.discussion_id LIMIT ? OFFSET ?",
            (source_id, limit, offset),
        )
        return tuple(self._discussion(row) for row in rows)

    def discussion(self, discussion_id: str) -> DiscussionSummary:
        rows = self.repository.rows(
            "SELECT d.*,s.list_id,m.subject AS root_subject FROM mailing_list_discussions d "
            "JOIN mailing_list_sources s ON s.source_id=d.source_id "
            "JOIN mailing_list_messages m ON m.message_key=d.root_message_key "
            "WHERE d.discussion_id=?", (discussion_id,),
        )
        if not rows:
            raise MailingListError("unknown_discussion", "unknown mailing-list discussion")
        return self._discussion(rows[0])

    def children(self, message_key_value: str, limit: int = 50, offset: int = 0
                 ) -> tuple[MessageSummary, ...]:
        self._limit(limit)
        return tuple(self._message(row) for row in self.repository.rows(
            self._message_select() +
            " WHERE r.parent_message_key=? ORDER BY m.message_date,m.message_key LIMIT ? OFFSET ?",
            (message_key_value, limit, offset),
        ))

    def ancestors(self, message_key_value: str, limit: int = 100) -> tuple[MessageSummary, ...]:
        self._limit(limit)
        rows = self.repository.rows(
            "WITH RECURSIVE path(message_key,n) AS (SELECT ?,0 UNION ALL "
            "SELECT r.parent_message_key,path.n+1 FROM path JOIN mailing_list_relationships r "
            "ON r.child_message_key=path.message_key "
            "WHERE r.parent_message_key IS NOT NULL AND path.n<?) "
            + self._message_select(
                prefix="path JOIN mailing_list_messages m ON m.message_key=path.message_key"
            )
            + " ORDER BY path.n DESC", (message_key_value, limit),
        )
        return tuple(self._message(row) for row in rows)

    def projection(self, discussion_id: str, limit: int = 100) -> DiscussionProjection:
        self._limit(limit)
        summary = self.discussion(discussion_id)
        rows = self.repository.rows(
            self._message_select() + " WHERE dm.discussion_id=? "
            "ORDER BY dm.depth,m.message_date,m.message_key LIMIT ?",
            (discussion_id, limit + 1),
        )
        return DiscussionProjection(summary, tuple(self._message(row) for row in rows[:limit]),
                                    len(rows) > limit)

    def search(self, text: str, source_id: str | None = None, limit: int = 50
               ) -> tuple[MessageSummary, ...]:
        self._limit(limit)
        if not text.strip():
            raise MailingListError("invalid_query", "search text must not be blank")
        where = "(m.subject LIKE ? OR m.sender LIKE ? OR m.text_content LIKE ?)"
        values: list[Any] = [f"%{text}%"] * 3
        if source_id:
            where += " AND m.source_id=?"
            values.append(source_id)
        values.append(limit)
        return tuple(self._message(row) for row in self.repository.rows(
            self._message_select() + f" WHERE {where} ORDER BY m.message_date DESC LIMIT ?",
            tuple(values),
        ))

    def incomplete(self, source_id: str | None = None, limit: int = 50
                   ) -> tuple[MessageSummary, ...]:
        self._limit(limit)
        where = "m.connectivity_state IN ('incomplete','quarantined')"
        params: tuple[Any, ...] = (limit,)
        if source_id:
            where += " AND m.source_id=?"
            params = (source_id, limit)
        return tuple(self._message(row) for row in self.repository.rows(
            self._message_select() + f" WHERE {where} ORDER BY m.message_date DESC LIMIT ?", params
        ))

    def message(self, key: str) -> MessageDetail:
        rows = self.repository.rows(self._message_select() + " WHERE m.message_key=?", (key,))
        if not rows:
            raise MailingListError("unknown_message", "unknown mailing-list message")
        row = rows[0]
        summary = self._message(row)
        source = self.repository.source(str(row["source_id"]))
        membership = self.repository.rows(
            "SELECT dm.discussion_id,d.root_message_key FROM mailing_list_discussion_members dm "
            "JOIN mailing_list_discussions d ON d.discussion_id=dm.discussion_id "
            "WHERE dm.message_key=?", (key,),
        )
        reasons = self.repository.rows(
            "SELECT DISTINCT inclusion_reason,run_id FROM mailing_list_run_items "
            "WHERE source_id=? AND external_message_id=? ORDER BY run_id",
            (source.source_id, summary.external_message_id),
        )
        relation = self.repository.rows(
            "SELECT authority,certainty,parent_external_message_id,parent_message_key "
            "FROM mailing_list_relationships WHERE child_message_key=?", (key,),
        )
        artifact = next(
            item for item in self.repository.artifacts.artifact_metadata()
            if item["artifact_id"] == summary.artifact_id
        )
        observations = [
            item for item in self.repository.artifacts.observations()
            if item["artifact_id"] == summary.artifact_id
        ]
        locations = tuple(dict.fromkeys(
            location for item in observations
            for location in item.get("candidate", {}).get("provenance", {}).get("locations", [])
        ))
        rel = relation[0] if relation else {}
        return MessageDetail(
            summary, source, str(membership[0]["discussion_id"]) if membership else None,
            str(membership[0]["root_message_key"]) if membership else None,
            tuple(sorted({str(item["inclusion_reason"]) for item in reasons})),
            tuple(str(item["run_id"]) for item in reasons),
            str(rel["authority"]) if rel else None, str(rel["certainty"]) if rel else None,
            str(rel["parent_external_message_id"])
            if rel and not rel["parent_message_key"] else None,
            str(artifact["sha256"]), str(artifact["media_type"]), int(artifact["size"]),
            "verified", locations,
        )

    def content(self, key: str) -> ArtifactContent:
        detail = self.message(key)
        raw = self.repository.raw_for_artifact(detail.summary.artifact_id)
        return ArtifactContent(detail.summary.document_id, detail.summary.artifact_id, raw,
                               detail.media_type, detail.checksum_sha256)

    @staticmethod
    def _limit(limit: int) -> None:
        if not 1 <= limit <= 100:
            raise MailingListError("invalid_limit", "query limit must be between 1 and 100")

    @staticmethod
    def _discussion(row: dict[str, Any]) -> DiscussionSummary:
        canonical = json.loads(str(row["canonical_json"]))
        return DiscussionSummary(
            str(row["discussion_id"]), str(row["source_id"]), str(row["list_id"]),
            str(row["root_message_key"]), str(row["root_subject"]), int(row["message_count"]),
            row["first_message_at"], row["last_message_at"],
            ConnectivityState(str(row["connectivity_state"])), bool(row["descendant_truncated"]),
            bool(canonical.get("descendant_policy_limited", False)),
            int(canonical.get("tombstone_count", 0)),
        )

    @staticmethod
    def _message_select(
        prefix: str = "mailing_list_messages m", extra_select: str = ""
    ) -> str:
        return (
            "SELECT m.*,r.parent_external_message_id,dm.depth,"
            "(SELECT count(*) FROM mailing_list_relationships c "
            f"WHERE c.parent_message_key=m.message_key) AS child_count{extra_select} "
            f"FROM {prefix} LEFT JOIN mailing_list_relationships r "
            "ON r.child_message_key=m.message_key "
            "LEFT JOIN mailing_list_discussion_members dm ON dm.message_key=m.message_key"
        )

    @staticmethod
    def _message(row: dict[str, Any]) -> MessageSummary:
        canonical = json.loads(str(row["canonical_json"]))
        return MessageSummary(
            str(row["message_key"]), canonical.get("external_message_id"),
            str(row["document_id"]), str(row["artifact_id"]), str(row["subject"]),
            str(row["sender"]), row["message_date"], row.get("parent_external_message_id"),
            ConnectivityState(str(row["connectivity_state"])), int(row["child_count"]),
            int(row["depth"]) if row.get("depth") is not None else None,
            bool(canonical.get("is_tombstone", False)),
        )
