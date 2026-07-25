# Global Canonical Mailing-List Message Store — Schema Design

> **Status:** Design proposal (review-only)  
> **Task context:** This design is a follow-on to TASK-023 (bounded mailing-list evidence), TASK-028 (operator workflow), TASK-030 (tombstone evidence), TASK-031 (resumable relationship acquisition), and TASK-032 (fetch queue history). It proposes the next architectural step: a global canonical message store that decouples immutable source evidence from acquisition-specific observation evidence and versioned derived projections.  
> **Scope:** Design only. No migrations, production code, or persistence changes are implemented.

---

## 1. Current-State Summary

### 1.1 Authority model

RFI-1 uses a **hybrid authority model** (TASK-020/TASK-021):

- **SQLite** (`repository.sqlite3`) owns authoritative structured records.
- **Content-addressed filesystem** (`<state>/content/sha256/<prefix>/<sha256>`) owns exact immutable artifact bytes.
- **Version-controlled documents** own governance and configuration.
- **Rebuildable projections** (document index, checkpoints, discussion indexes) are non-authoritative.

Schema version is currently **6** (see `SCHEMA_VERSION` in `src/rfi/storage/sqlite.py`).

### 1.2 Current acquisition identity model

The acquisition substrate (`src/rfi/acquisition/contracts.py`, `src/rfi/acquisition/repository.py`) establishes these identity domains:

| Identity | Owner | Meaning |
|---|---|---|
| `source_id` | repository governance | configured acquisition source |
| `document_id` | repository domain | stable logical source document |
| `artifact_id` | repository evidence | one exact byte sequence (`artifact-<sha256>`) |
| `observation_id` | repository evidence | one successful acquisition observation |
| `attempt_id` | repository history | one materially distinct activity |
| provider identifiers | external provider | provenance attributes only |

Key tables in the acquisition substrate:

- `governed_sources` — immutable source profiles
- `artifacts` — `artifact_id`, `sha256`, `byte_count`, `media_type`, `content_reference`, `created_at`
- `documents` — `document_id`, `current_artifact_id`, `durable_status`
- `acquisition_attempts` — immutable attempt records with `outcome`, `occurred_at`, `mechanism`, `artifact_id`
- `artifact_observations` — one observation per successful attempt, linking attempt→artifact→document→source
- `checkpoint_events` / `current_checkpoints` — source-scoped progress cursors

### 1.3 Current mailing-list models

The mailing-list vertical (`src/rfi/mailing_lists/`) adds these tables:

- `mailing_list_sources` — Lore source metadata (`source_id`, `list_id`, `display_name`, `archive_base_url`)
- `mailing_list_runs` — immutable acquisition manifests (`run_id`, `source_id`, `requested_at`, `status`, `seed_limit`, `context_limit`, `seed_count`, `message_count`, `canonical_json`, `lifecycle_status`, `error_code`, `retryable`)
- `mailing_list_run_items` — per-run per-message observations (`run_id`, `source_id`, `external_message_id`, `artifact_id`, `document_id`, `inclusion_reason`, `is_seed`, `connectivity_state`)
- `mailing_list_messages` — **rebuildable derived projection** of parsed message metadata (`message_key`, `source_id`, `external_message_id`, `artifact_id`, `document_id`, `subject`, `normalized_subject`, `sender`, `message_date`, `text_content`, `connectivity_state`, `canonical_json`)
- `mailing_list_relationships` — header-derived reply edges (`child_message_key`, `parent_external_message_id`, `parent_message_key`, `authority`, `certainty`)
- `mailing_list_discussions` — connected discussion roots (`discussion_id`, `source_id`, `root_message_key`, `connectivity_state`, `descendant_truncated`, `message_count`, `first_message_at`, `last_message_at`, `canonical_json`)
- `mailing_list_discussion_members` — discussion membership with depth (`discussion_id`, `message_key`, `depth`)

### 1.4 Current Message-ID handling

- `normalize_message_id()` in `src/rfi/mailing_lists/parser.py` normalizes Message-IDs to `<local@domain.casefold()>`.
- `message_key(source_id, external_message_id)` = `message-{sha256(source_id\0external_message_id)[:32]}` — **source-scoped**, not global.
- `document_id(source_id, external_message_id)` = `mail.{sha256(source_id\0external_message_id)[:32]}` — **source-scoped**.
- `external_message_id` is the normalized Message-ID, stored per-message in `mailing_list_messages`.

### 1.5 Current acquisition-run records

`AcquisitionManifest` (frozen dataclass in `contracts.py`) is serialized as `canonical_json` in `mailing_list_runs`. It carries:

- `run_id`, `source_id`, `requested_at`, `criteria`, `limits`, `seed_ids`
- `message_count`, `relationship_count`, `discussion_count`, `inclusion_reasons`
- `state` (ConnectivityState), `truncated`, `warnings`
- `artifact_count_created`, `idempotent_messages`, `run_status`, `error_code`, `retryable`
- `discovery_offset`, `discovery_has_more`, `relationship_truncated`, `coverage_batch_id`, `coverage_complete`
- `fallback_message_ids`, `discovery_complete`, `required_ancestry_complete`, `descendant_policy_complete`, `descendant_policy_limited`, `unexpected_truncation`
- `tombstone_message_ids`, `relationship_status`, `relationship_continuation`, `relationship_records_processed`

### 1.6 Current coverage logic

Coverage is computed in `MailingListAcquisitionService.acquire()` (`src/rfi/mailing_lists/service.py`). The `coverage_complete` flag is set when:

- `prior_batches_complete` is true
- `discovery_complete` is true
- `required_ancestry_complete` is true
- `relationship_status` is `complete` or `policy_truncated`
- No `unexpected_truncation`
- No failures
- `state` is `connected`

Coverage is **run-level**, not per-message. The `coverage_batch_id` and `discovery_offset` fields support resumable relationship acquisition (TASK-031).

### 1.7 Current discussion projection

`derive_projection()` in `service.py` rebuilds `mailing_list_messages`, `mailing_list_relationships`, `mailing_list_discussions`, and `mailing_list_discussion_members` from `retained_records()`. It:

- Walks `In-Reply-To` chains to find roots and detect cycles
- Assigns `connectivity_state` (connected/truncated/incomplete/quarantined) per message
- Groups messages into discussions by root
- Validates that every connected/truncated member has one acyclic path to root

### 1.8 Current fetch history

`mailing_list_fetch_history` and `mailing_list_fetch_events` (added by TASK-032) provide bounded operator scrollback (50 history entries, 200 events). These are **fetch-job-level**, not acquisition-run-level.

### 1.9 Current patch-series / revision semantics

From `docs/revisioned-artifact-streams.md`: Mail streams register `mail.list_id` and `mail.patch_version` attributes. The `connected_discussion` expansion strategy consumes TASK-023's discussion membership. No dedicated patch-series table exists; patch detection is a future schema attribute.

### 1.10 Current integrity verification

- `RepositoryDatabase.validate()` runs SQLite integrity check + foreign key check
- `AcquisitionRepository.verify_integrity()` checks every artifact reference against filesystem content
- `MailingListRepository.validate_connectivity()` walks every connected/truncated message path to root

---

## 2. Proposed Entity-Relationship Model

### 2.1 Layering

```
┌─────────────────────────────────────────────────────────────────┐
│  ACQUISITION OBSERVATIONS (per-run, per-window evidence)        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ acquisition_runs │ acquisition_windows │ run_observations │ │
│  │ run_unavailable_observations                           │   │
│  └─────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│  CANONICAL MESSAGES (global, immutable source facts)            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ canonical_messages │ message_raw_artifacts               │ │
│  │ message_headers (normalized) │ message_metadata (parsed) │ │
│  └─────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│  DERIVED PROJECTIONS (versioned, regenerable)                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ message_relationships │ message_references              │ │
│  │ message_discussions │ discussion_members                │ │
│  │ patch_series │ patch_series_revisions                  │ │
│  │ projection_versions                                   │ │
│  └─────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│  INTEGRITY & CORRUPTION                                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ message_integrity                                       │ │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Key architectural decisions

1. **Global canonical messages keyed by normalized Message-ID** — `canonical_messages` uses `normalized_message_id` as the primary key, not a source-scoped hash. This enables reuse across sources and acquisitions.

2. **Separation of immutable source facts from acquisition observations** — `message_raw_artifacts` stores exact bytes (immutable). `run_observations` records what each acquisition run discovered, fetched, reused, or found unavailable.

3. **Deterministic extracted metadata is versioned** — `message_metadata` is derived from raw artifacts via a named parser version. `projection_versions` tracks which parser/schema version produced each derived table.

4. **Acquisition coverage is independent from canonical message existence** — `acquisition_windows` records coverage scope per window; `run_observations` records per-message observation state per run.

5. **Unavailability markers are first-class** — `run_unavailable_observations` records confirmed-absence evidence (404 from both archives) without creating a canonical message.

---

## 3. Table-by-Table Schema

### 3.1 `canonical_messages`

**Purpose:** Global canonical message identity keyed by normalized Message-ID. One row per unique normalized Message-ID. Immutable after creation.

| Column | Type | Notes |
|---|---|---|
| `normalized_message_id` | TEXT PK | `<local@domain.casefold()>` — global canonical key |
| `source_id` | TEXT FK→`governed_sources` | Source that first retained this message |
| `document_id` | TEXT UNIQUE | Stable logical document ID (`mail.<hash>`) |
| `artifact_id` | TEXT FK→`artifacts` | Current canonical artifact (SHA-256 of exact bytes) |
| `media_type` | TEXT | `message/rfc822` or `application/vnd.rfi.mailing-list-tombstone+json` |
| `created_at` | TEXT | ISO 8601 UTC, when first retained |
| `first_observed_at` | TEXT | ISO 8601 UTC, earliest observation |
| `is_tombstone` | INTEGER 0/1 | Whether this is a confirmed-unavailable ancestor |
| `sha256` | TEXT | SHA-256 of exact bytes (denormalized from artifact for fast lookup) |

**PK:** `normalized_message_id`  
**FK:** `artifact_id` → `artifacts(artifact_id)`, `source_id` → `governed_sources(source_id)`  
**Unique:** `document_id`, `sha256`  
**Check:** `is_tombstone IN (0,1)`  
**Indexes:** `canonical_messages(source_id)`, `canonical_messages(is_tombstone)`  
**Mutability:** Immutable after insert. `artifact_id` may be updated only if the existing artifact is superseded by a different byte sequence under the same Message-ID (conflict — see invariants).  
**Lifecycle:** Created once per unique normalized Message-ID. Never deleted.

### 3.2 `message_raw_artifacts`

**Purpose:** Immutable raw-message provenance. One row per canonical message, linking to the content-addressed filesystem bytes. This is the immutable source evidence layer.

| Column | Type | Notes |
|---|---|---|
| `canonical_message_id` | TEXT PK, FK→`canonical_messages` | |
| `artifact_id` | TEXT FK→`artifacts` | Exact byte sequence identity |
| `sha256` | TEXT | SHA-256 of exact bytes |
| `byte_count` | INTEGER | Byte count |
| `media_type` | TEXT | `message/rfc822` or tombstone type |
| `content_reference` | TEXT | `sha256/<prefix>/<sha256>` filesystem path |
| `retained_at` | TEXT | ISO 8601 UTC |
| `retained_by_run_id` | TEXT FK→`acquisition_runs` | Run that first retained this artifact |

**PK:** `canonical_message_id`  
**FK:** `canonical_message_id` → `canonical_messages(normalized_message_id)`, `artifact_id` → `artifacts(artifact_id)`, `retained_by_run_id` → `acquisition_runs(run_id)`  
**Unique:** `artifact_id` (one artifact = one canonical message)  
**Indexes:** `message_raw_artifacts(sha256)`  
**Mutability:** Immutable after insert.  
**Lifecycle:** Created once per canonical message. Never deleted.

### 3.3 `message_headers`

**Purpose:** Normalized source headers extracted from the raw RFC 5322 message. Deterministic, parser-version-independent facts about the message envelope.

| Column | Type | Notes |
|---|---|---|
| `canonical_message_id` | TEXT PK, FK→`canonical_messages` | |
| `message_id_raw` | TEXT | Raw `Message-ID` header value |
| `subject` | TEXT | Raw `Subject` header |
| `normalized_subject` | TEXT | Subject with Re:/Fwd: and [PATCH] prefixes stripped, casefolded |
| `sender` | TEXT | Raw `From` header |
| `sender_name` | TEXT | Extracted display name (may be NULL) |
| `sender_email` | TEXT | Extracted email address (may be NULL) |
| `message_date` | TEXT | ISO 8601 UTC, parsed from `Date` header (may be NULL) |
| `in_reply_to` | TEXT | Normalized `In-Reply-To` Message-ID (may be NULL) |
| `references_raw` | TEXT | Raw `References` header value |
| `date_raw` | TEXT | Raw `Date` header value |

**PK:** `canonical_message_id`  
**FK:** `canonical_message_id` → `canonical_messages(normalized_message_id)`  
**Indexes:** `message_headers(message_date)`, `message_headers(in_reply_to)`, `message_headers(sender_email)`  
**Mutability:** Immutable after insert.  
**Lifecycle:** Created once per canonical message. Regenerated only if the parser version changes (see `projection_versions`).

### 3.4 `message_metadata`

**Purpose:** Deterministic extracted metadata suitable for LLM graph traversal. Parsed from raw bytes via a named parser version. Regenerable from `message_raw_artifacts`.

| Column | Type | Notes |
|---|---|---|
| `canonical_message_id` | TEXT PK, FK→`canonical_messages` | |
| `parser_version` | TEXT | Parser/schema version that produced this row |
| `text_content` | TEXT | Extracted plain-text body (may be empty for tombstones) |
| `has_attachments` | INTEGER 0/1 | |
| `attachment_count` | INTEGER | |
| `content_language` | TEXT | Parsed `Content-Language` (may be NULL) |
| `normalized_subject_is_identity` | INTEGER 0/1 | Whether subject normalization preserves identity |
| `parse_warnings` | TEXT | JSON array of parse warnings |
| `extracted_at` | TEXT | ISO 8601 UTC |

**PK:** `canonical_message_id`  
**FK:** `canonical_message_id` → `canonical_messages(normalized_message_id)`  
**Unique:** `parser_version` (one row per message per parser version)  
**Check:** `has_attachments IN (0,1)`, `normalized_subject_is_identity IN (0,1)`  
**Indexes:** `message_metadata(parser_version)`  
**Mutability:** Immutable per `(canonical_message_id, parser_version)`. A new parser version creates a new row; old rows are retained.  
**Lifecycle:** Regenerated from raw artifacts. Can be rebuilt offline.

### 3.5 `acquisition_runs`

**Purpose:** Immutable acquisition run records. One row per bounded acquisition run. Replaces the `canonical_json` blob in `mailing_list_runs` with structured columns while preserving the manifest for backward compatibility.

| Column | Type | Notes |
|---|---|---|
| `run_id` | TEXT PK | `mailrun-<uuid>` |
| `source_id` | TEXT FK→`governed_sources` | |
| `window_id` | TEXT FK→`acquisition_windows` | Window this run belongs to |
| `requested_at` | TEXT | ISO 8601 UTC |
| `completed_at` | TEXT | ISO 8601 UTC (may be NULL if failed before completion) |
| `status` | TEXT | `connected`, `truncated`, `incomplete`, `quarantined` |
| `lifecycle_status` | TEXT | `succeeded`, `partial`, `retryable_failure`, `terminal_failure` |
| `error_code` | TEXT | NULL if no error |
| `retryable` | INTEGER 0/1 | |
| `seed_limit` | INTEGER | |
| `context_limit` | INTEGER | |
| `seed_count` | INTEGER | |
| `message_count` | INTEGER | Total messages observed in this run |
| `artifact_count_created` | INTEGER | New artifacts created |
| `idempotent_messages` | INTEGER | Messages reused without new artifacts |
| `tombstone_count` | INTEGER | Tombstones created |
| `relationship_count` | INTEGER | Relationship edges observed |
| `discussion_count` | INTEGER | Discussions observed |
| `discovery_offset` | INTEGER | Discovery pagination offset |
| `discovery_has_more` | INTEGER 0/1 | |
| `coverage_batch_id` | TEXT | Coverage batch identity for resumption |
| `coverage_complete` | INTEGER 0/1 | |
| `relationship_status` | TEXT | `complete`, `continuation_pending`, `policy_truncated`, `failed` |
| `relationship_continuation` | TEXT | JSON continuation frontier (may be NULL) |
| `relationship_records_processed` | INTEGER | |
| `truncated` | INTEGER 0/1 | |
| `unexpected_truncation` | INTEGER 0/1 | |
| `discovery_complete` | INTEGER 0/1 | |
| `required_ancestry_complete` | INTEGER 0/1 | |
| `descendant_policy_complete` | INTEGER 0/1 | |
| `descendant_policy_limited` | INTEGER 0/1 | |
| `manifest_json` | TEXT | Full canonical JSON manifest for backward compatibility |

**PK:** `run_id`  
**FK:** `source_id` → `governed_sources(source_id)`, `window_id` → `acquisition_windows(window_id)`  
**Check:** `status IN ('connected','truncated','incomplete','quarantined')`, `lifecycle_status IN ('succeeded','partial','retryable_failure','terminal_failure')`, `relationship_status IN ('complete','continuation_pending','policy_truncated','failed')`  
**Indexes:** `acquisition_runs(source_id, requested_at DESC)`, `acquisition_runs(window_id)`  
**Mutability:** Immutable after insert.  
**Lifecycle:** Created once per acquisition run. Never deleted.

### 3.6 `acquisition_windows`

**Purpose:** Acquisition windows or scopes. One row per bounded date window or explicit scope within a source. Windows are the unit of coverage tracking.

| Column | Type | Notes |
|---|---|---|
| `window_id` | TEXT PK | `window-<source_id>-<date>` |
| `source_id` | TEXT FK→`governed_sources` | |
| `window_start` | TEXT | ISO 8601 date |
| `window_end` | TEXT | ISO 8601 date |
| `criteria_json` | TEXT | Selection criteria (JSON) |
| `coverage_complete` | INTEGER 0/1 | Whether all runs in this window achieved coverage |
| `created_at` | TEXT | ISO 8601 UTC |

**PK:** `window_id`  
**FK:** `source_id` → `governed_sources(source_id)`  
**Unique:** `(source_id, window_start, window_end)`  
**Check:** `coverage_complete IN (0,1)`  
**Indexes:** `acquisition_windows(source_id, window_start)`  
**Mutability:** `coverage_complete` is updated when all runs in the window complete. All other fields immutable.  
**Lifecycle:** Created per bounded window. Updated only for coverage status.

### 3.7 `run_observations`

**Purpose:** Per-run/per-window message observations. Records what each acquisition run discovered, fetched, reused, or found unavailable for each Message-ID. This is the acquisition-specific evidence layer.

| Column | Type | Notes |
|---|---|---|
| `run_id` | TEXT PK, FK→`acquisition_runs` | |
| `canonical_message_id` | TEXT FK→`canonical_messages` | NULL for unavailable observations |
| `external_message_id` | TEXT | Normalized Message-ID as observed |
| `observation_type` | TEXT | `discovered`, `fetched`, `reused`, `unavailable` |
| `inclusion_reason` | TEXT | `seed_match`, `explicit_request`, `ancestor_context`, `descendant_context`, `relationship_context` |
| `is_seed` | INTEGER 0/1 | |
| `connectivity_state` | TEXT | `connected`, `truncated`, `incomplete`, `quarantined` |
| `artifact_id` | TEXT FK→`artifacts` | NULL if not fetched/reused |
| `document_id` | TEXT | NULL if not fetched/reused |
| `fallback_archive_url` | TEXT | Cross-list fallback URL (may be NULL) |
| `observed_at` | TEXT | ISO 8601 UTC |

**PK:** `(run_id, external_message_id)`  
**FK:** `run_id` → `acquisition_runs(run_id)`, `canonical_message_id` → `canonical_messages(normalized_message_id)`, `artifact_id` → `artifacts(artifact_id)`  
**Check:** `observation_type IN ('discovered','fetched','reused','unavailable')`, `inclusion_reason IN ('seed_match','explicit_request','ancestor_context','descendant_context','relationship_context')`, `connectivity_state IN ('connected','truncated','incomplete','quarantined')`, `is_seed IN (0,1)`  
**Indexes:** `run_observations(external_message_id)`, `run_observations(observation_type)`, `run_observations(canonical_message_id)`  
**Mutability:** Immutable after insert.  
**Lifecycle:** Created per run per observed Message-ID. Never deleted.

### 3.8 `run_unavailable_observations`

**Purpose:** Unavailable-message observations. Records confirmed-absence evidence (HTTP 404 from both archives) without creating a canonical message. These do not permanently suppress later successful fetches.

| Column | Type | Notes |
|---|---|---|
| `observation_id` | TEXT PK | `unavail-<run_id>-<message_id_hash>` |
| `run_id` | TEXT FK→`acquisition_runs` | |
| `external_message_id` | TEXT | Normalized Message-ID |
| `observed_at` | TEXT | ISO 8601 UTC |
| `locations` | TEXT | JSON array of attempted URLs |
| `http_statuses` | TEXT | JSON array of HTTP status codes |
| `availability` | TEXT | `confirmed_not_found` |
| `content_synthesized` | INTEGER 0/1 | Always 0 |

**PK:** `observation_id`  
**FK:** `run_id` → `acquisition_runs(run_id)`  
**Unique:** `(run_id, external_message_id)`  
**Check:** `availability = 'confirmed_not_found'`, `content_synthesized = 0`  
**Indexes:** `run_unavailable_observations(external_message_id)`, `run_unavailable_observations(observed_at)`  
**Mutability:** Immutable after insert.  
**Lifecycle:** Created per run per unavailable Message-ID. Never deleted. Does not prevent a later run from creating a `canonical_messages` row for the same Message-ID.

### 3.9 `message_relationships`

**Purpose:** Parent/reference relationships. Header-derived reply edges and explicit references. Versioned derived data.

| Column | Type | Notes |
|---|---|---|
| `child_message_id` | TEXT PK, FK→`canonical_messages` | |
| `parent_message_id` | TEXT FK→`canonical_messages` | NULL if parent is unresolved or unavailable |
| `parent_external_message_id` | TEXT | Raw `In-Reply-To` value (may be NULL) |
| `authority` | TEXT | `header`, `archive`, `inferred` |
| `certainty` | TEXT | `direct`, `heuristic`, `unresolved` |
| `parser_version` | TEXT | Version of parser that produced this edge |
| `projected_at` | TEXT | ISO 8601 UTC |

**PK:** `child_message_id`  
**FK:** `child_message_id` → `canonical_messages(normalized_message_id)`, `parent_message_id` → `canonical_messages(normalized_message_id)`  
**Check:** `authority IN ('header','archive','inferred')`, `certainty IN ('direct','heuristic','unresolved')`, `(parent_message_id IS NULL) = (certainty = 'unresolved')`  
**Indexes:** `message_relationships(parent_message_id, child_message_id)`, `message_relationships(authority, certainty)`  
**Mutability:** Immutable per `(child_message_id, parser_version)`. Replaced wholesale on projection rebuild.  
**Lifecycle:** Regenerated from `message_headers` on projection rebuild.

### 3.10 `message_references`

**Purpose:** Reference relationships beyond immediate parent. Stores `References` header entries as explicit edges for graph traversal.

| Column | Type | Notes |
|---|---|---|
| `message_id` | TEXT PK, FK→`canonical_messages` | The message containing the references |
| `referenced_message_id` | TEXT PK, FK→`canonical_messages` | Referenced message (may be NULL if not retained) |
| `referenced_external_message_id` | TEXT | Raw referenced Message-ID |
| `position` | INTEGER | Position in References header |
| `parser_version` | TEXT | |

**PK:** `(message_id, position)`  
**FK:** `message_id` → `canonical_messages(normalized_message_id)`, `referenced_message_id` → `canonical_messages(normalized_message_id)` (nullable)  
**Indexes:** `message_references(referenced_message_id)`, `message_references(message_id, position)`  
**Mutability:** Immutable per `(message_id, position, parser_version)`. Replaced wholesale on projection rebuild.  
**Lifecycle:** Regenerated from `message_headers`.

### 3.11 `message_discussions`

**Purpose:** Discussion roots. One row per connected discussion component.

| Column | Type | Notes |
|---|---|---|
| `discussion_id` | TEXT PK | `discussion-<hash>` |
| `root_message_id` | TEXT UNIQUE, FK→`canonical_messages` | |
| `connectivity_state` | TEXT | `connected`, `truncated`, `incomplete`, `quarantined` |
| `descendant_truncated` | INTEGER 0/1 | |
| `descendant_policy_limited` | INTEGER 0/1 | |
| `message_count` | INTEGER | |
| `first_message_at` | TEXT | ISO 8601 UTC (may be NULL) |
| `last_message_at` | TEXT | ISO 8601 UTC (may be NULL) |
| `tombstone_count` | INTEGER | |
| `canonical_json` | TEXT | Full canonical discussion record |
| `projected_at` | TEXT | ISO 8601 UTC |
| `parser_version` | TEXT | |

**PK:** `discussion_id`  
**FK:** `root_message_id` → `canonical_messages(normalized_message_id)`  
**Unique:** `root_message_id`  
**Check:** `connectivity_state IN ('connected','truncated','incomplete','quarantined')`, `descendant_truncated IN (0,1)`, `descendant_policy_limited IN (0,1)`  
**Indexes:** `message_discussions(root_message_id)`, `message_discussions(connectivity_state)`  
**Mutability:** Immutable per `parser_version`. Replaced wholesale on projection rebuild.  
**Lifecycle:** Regenerated from `message_relationships` + `message_headers`.

### 3.12 `discussion_members`

**Purpose:** Discussion membership with depth. Many-to-many between discussions and messages.

| Column | Type | Notes |
|---|---|---|
| `discussion_id` | TEXT PK, FK→`message_discussions` | |
| `message_id` | TEXT PK, FK→`canonical_messages` | |
| `depth` | INTEGER | Distance from root |
| `parser_version` | TEXT | |

**PK:** `(discussion_id, message_id)`  
**FK:** `discussion_id` → `message_discussions(discussion_id)`, `message_id` → `canonical_messages(normalized_message_id)`  
**Check:** `depth >= 0`  
**Indexes:** `discussion_members(message_id)`, `discussion_members(discussion_id, depth)`  
**Mutability:** Immutable per `parser_version`. Replaced wholesale on projection rebuild.  
**Lifecycle:** Regenerated from `message_relationships`.

### 3.13 `patch_series`

**Purpose:** Patch-series and revision relationships. Groups messages that form a patch series (e.g., `[PATCH v1 0/3]`, `[PATCH v1 1/3]`, `[PATCH v1 2/3]`, `[PATCH v1 3/3]`).

| Column | Type | Notes |
|---|---|---|
| `series_id` | TEXT PK | `series-<hash>` |
| `root_message_id` | TEXT FK→`canonical_messages` | First message in the series |
| `subject_prefix` | TEXT | Normalized subject prefix (e.g., `[patch v1]`) |
| `version` | INTEGER | Patch version number |
| `total_patches` | INTEGER | Expected number of patches |
| `is_complete` | INTEGER 0/1 | Whether all patches are present |
| `created_at` | TEXT | ISO 8601 UTC |
| `parser_version` | TEXT | |

**PK:** `series_id`  
**FK:** `root_message_id` → `canonical_messages(normalized_message_id)`  
**Check:** `version >= 1`, `total_patches >= 1`, `is_complete IN (0,1)`  
**Indexes:** `patch_series(root_message_id)`, `patch_series(subject_prefix)`  
**Mutability:** Immutable per `parser_version`. Replaced wholesale on projection rebuild.  
**Lifecycle:** Regenerated from `message_headers` subject parsing.

### 3.14 `patch_series_revisions`

**Purpose:** Individual patch messages within a series, ordered by patch number.

| Column | Type | Notes |
|---|---|---|
| `series_id` | TEXT PK, FK→`patch_series` | |
| `message_id` | TEXT PK, FK→`canonical_messages` | |
| `patch_number` | INTEGER | 1-based position in series |
| `is_cover_letter` | INTEGER 0/1 | Whether this is the cover letter (0/N) |
| `parser_version` | TEXT | |

**PK:** `(series_id, message_id)`  
**FK:** `series_id` → `patch_series(series_id)`, `message_id` → `canonical_messages(normalized_message_id)`  
**Check:** `patch_number >= 0`, `is_cover_letter IN (0,1)`  
**Unique:** `(series_id, patch_number)`  
**Indexes:** `patch_series_revisions(message_id)`, `patch_series_revisions(series_id, patch_number)`  
**Mutability:** Immutable per `parser_version`. Replaced wholesale on projection rebuild.  
**Lifecycle:** Regenerated from `message_headers` subject parsing.

### 3.15 `projection_versions`

**Purpose:** Parser/schema/projection versioning. Tracks which parser version produced each derived table, enabling targeted regeneration.

| Column | Type | Notes |
|---|---|---|
| `projection_name` | TEXT PK | Name of the derived table (e.g., `message_relationships`) |
| `parser_version` | TEXT PK | Version that produced this projection |
| `projected_at` | TEXT | ISO 8601 UTC |
| `record_count` | INTEGER | Number of rows in the projection |
| `sha256` | TEXT | SHA-256 of the projection's canonical JSON |

**PK:** `(projection_name, parser_version)`  
**Check:** `record_count >= 0`, `length(sha256) = 64`  
**Indexes:** `projection_versions(projected_at DESC)`  
**Mutability:** Immutable after insert. New parser version creates a new row.  
**Lifecycle:** Updated on each projection rebuild.

### 3.16 `message_integrity`

**Purpose:** Integrity and corruption state. Tracks verification results for canonical messages.

| Column | Type | Notes |
|---|---|---|
| `canonical_message_id` | TEXT PK, FK→`canonical_messages` | |
| `sha256_verified` | INTEGER 0/1 | Whether artifact bytes match stored SHA-256 |
| `last_verified_at` | TEXT | ISO 8601 UTC |
| `corruption_state` | TEXT | `ok`, `missing_bytes`, `checksum_mismatch`, `quarantined` |
| `verification_error` | TEXT | Error message if verification failed (may be NULL) |

**PK:** `canonical_message_id`  
**FK:** `canonical_message_id` → `canonical_messages(normalized_message_id)`  
**Check:** `sha256_verified IN (0,1)`, `corruption_state IN ('ok','missing_bytes','checksum_mismatch','quarantined')`  
**Indexes:** `message_integrity(corruption_state)`, `message_integrity(last_verified_at)`  
**Mutability:** Updated on each integrity verification.  
**Lifecycle:** Updated by `verify_integrity` operations.

### 3.17 `run_inclusion_reasons`

**Purpose:** Aggregated inclusion-reason counts per run, replacing the `inclusion_reasons` JSON dict in the manifest.

| Column | Type | Notes |
|---|---|---|
| `run_id` | TEXT PK, FK→`acquisition_runs` | |
| `inclusion_reason` | TEXT PK | `seed_match`, `explicit_request`, `ancestor_context`, `descendant_context`, `relationship_context` |
| `count` | INTEGER | |

**PK:** `(run_id, inclusion_reason)`  
**FK:** `run_id` → `acquisition_runs(run_id)`  
**Check:** `count >= 0`  
**Mutability:** Immutable after insert.  
**Lifecycle:** Created per run per inclusion reason.

---

## 4. Behavioral Invariants

| # | Invariant | Enforced by |
|---|---|---|
| 1 | One canonical retained message may be referenced by many acquisition observations | `run_observations.canonical_message_id` → `canonical_messages` (many-to-one) |
| 2 | A later acquisition may reuse a valid canonical message without claiming it downloaded the message | `run_observations.observation_type = 'reused'` does not create a new `message_raw_artifacts` row |
| 3 | Every acquisition still records its own discovery and coverage evidence | `acquisition_runs` + `run_observations` + `acquisition_windows` are per-run |
| 4 | Identical Message-ID plus identical bytes reuses the canonical artifact | `canonical_messages.sha256` UNIQUE constraint; `retain_message` checks existing artifact |
| 5 | Identical Message-ID plus different bytes fails closed or records a quarantined conflict | `message_id_conflict` error in `retain_message`; `message_integrity.corruption_state = 'quarantined'` |
| 6 | Unavailable markers do not permanently suppress a later successful fetch | `run_unavailable_observations` has no FK to `canonical_messages`; later `run_observations` can reference a canonical message |
| 7 | Derived metadata can be regenerated from immutable raw artifacts | `message_metadata` is derived from `message_raw_artifacts` via `parser_version`; `projection_versions` tracks regeneration |
| 8 | Acquisition coverage remains independent from canonical message existence | `acquisition_windows.coverage_complete` is updated per-window; `canonical_messages` is independent |
| 9 | Overlapping windows may reuse canonical content while retaining independent observation records | `run_observations` is keyed by `(run_id, external_message_id)`; multiple runs can reference the same `canonical_message_id` |

---

## 5. Example Query Paths

### 5.1 Fetch a discussion root and all descendants

```sql
-- Get the root message and all members of a discussion, ordered by depth
SELECT m.normalized_message_id, m.document_id, m.subject, m.message_date,
       dm.depth, m.is_tombstone
FROM message_discussions md
JOIN discussion_members dm ON dm.discussion_id = md.discussion_id
JOIN canonical_messages m ON m.normalized_message_id = dm.message_id
WHERE md.discussion_id = :discussion_id
ORDER BY dm.depth ASC, m.message_date ASC;
```

### 5.2 Fetch a patch series across revisions

```sql
-- Get all patches in a series, ordered by patch number
SELECT m.normalized_message_id, m.subject, m.message_date,
       psr.patch_number, psr.is_cover_letter, ps.version
FROM patch_series ps
JOIN patch_series_revisions psr ON psr.series_id = ps.series_id
JOIN canonical_messages m ON m.normalized_message_id = psr.message_id
WHERE ps.subject_prefix = :subject_prefix
ORDER BY ps.version ASC, psr.patch_number ASC;
```

### 5.3 Fetch a message with parent, children, references, and acquisition provenance

```sql
-- Get a message with its parent, children, references, and all acquisition observations
WITH msg AS (
  SELECT * FROM canonical_messages WHERE normalized_message_id = :message_id
),
parent AS (
  SELECT mr.parent_message_id, m.subject AS parent_subject
  FROM message_relationships mr
  JOIN canonical_messages m ON m.normalized_message_id = mr.parent_message_id
  WHERE mr.child_message_id = :message_id
),
children AS (
  SELECT mr.child_message_id, m.subject AS child_subject
  FROM message_relationships mr
  JOIN canonical_messages m ON m.normalized_message_id = mr.child_message_id
  WHERE mr.parent_message_id = :message_id
),
refs AS (
  SELECT mr.referenced_external_message_id, mr.referenced_message_id
  FROM message_references mr
  WHERE mr.message_id = :message_id
),
observations AS (
  SELECT ro.run_id, ro.observation_type, ro.inclusion_reason, ro.is_seed,
         ro.connectivity_state, ar.requested_at
  FROM run_observations ro
  JOIN acquisition_runs ar ON ar.run_id = ro.run_id
  WHERE ro.canonical_message_id = :message_id
)
SELECT
  (SELECT json_object('message_id', normalized_message_id, 'subject', subject,
                      'sender', sender, 'message_date', message_date,
                      'is_tombstone', is_tombstone, 'sha256', sha256) FROM msg) AS message,
  (SELECT json_group_array(json_object('parent_message_id', parent_message_id,
                                       'parent_subject', parent_subject)) FROM parent) AS parents,
  (SELECT json_group_array(json_object('child_message_id', child_message_id,
                                       'child_subject', child_subject)) FROM children) AS children,
  (SELECT json_group_array(json_object('referenced_external_message_id',
                                       referenced_external_message_id,
                                       'referenced_message_id', referenced_message_id)) FROM refs) AS references,
  (SELECT json_group_array(json_object('run_id', run_id, 'observation_type', observation_type,
                                       'inclusion_reason', inclusion_reason, 'is_seed', is_seed,
                                       'connectivity_state', connectivity_state,
                                       'observed_at', requested_at)) FROM observations) AS provenance;
```

### 5.4 Fetch only the minimal metadata needed to decide what message bodies an LLM should load

```sql
-- Minimal metadata for LLM triage: only messages that are not tombstones,
-- with their discussion root, depth, and connectivity state
SELECT m.normalized_message_id, m.subject, m.message_date, m.sender,
       m.sha256, m.byte_count, m.media_type,
       m.is_tombstone, m.connectivity_state,
       dm.discussion_id, dm.depth,
       md.root_message_id
FROM canonical_messages m
JOIN discussion_members dm ON dm.message_id = m.normalized_message_id
JOIN message_discussions md ON md.discussion_id = dm.discussion_id
WHERE m.is_tombstone = 0
  AND m.normalized_message_id IN (:message_ids)
ORDER BY md.discussion_id, dm.depth;
```

### 5.5 Identify missing ancestors or unresolved references

```sql
-- Messages whose In-Reply-To parent is not retained as a canonical message
SELECT m.normalized_message_id, m.in_reply_to
FROM message_headers m
WHERE m.in_reply_to IS NOT NULL
  AND m.in_reply_to NOT IN (
    SELECT normalized_message_id FROM canonical_messages
  )
  AND m.in_reply_to NOT IN (
    SELECT external_message_id FROM run_unavailable_observations
  );
```

### 5.6 Identify messages whose deterministic metadata needs regeneration after a parser-version change

```sql
-- Messages whose metadata was produced by an older parser version
SELECT m.normalized_message_id, mm.parser_version AS current_parser,
       :new_parser_version AS target_parser
FROM canonical_messages m
LEFT JOIN message_metadata mm ON mm.canonical_message_id = m.normalized_message_id
WHERE mm.parser_version IS NULL
   OR mm.parser_version < :new_parser_version
ORDER BY m.created_at ASC;
```

---

## 6. Migration Analysis

### 6.1 What can migrate losslessly

| Current concept | Maps to | Notes |
|---|---|---|
| `mailing_list_sources` | `governed_sources` (existing) + `canonical_messages.source_id` | Source records already exist; no change needed |
| `artifacts` table | `artifacts` (existing) | No change; `message_raw_artifacts` references existing rows |
| `documents` table | `canonical_messages.document_id` | Document IDs already exist; new table adds canonical message key |
| `acquisition_attempts` | Retained as-is | Existing acquisition substrate unchanged |
| `artifact_observations` | Retained as-is | Existing acquisition substrate unchanged |
| `mailing_list_runs.canonical_json` | `acquisition_runs.manifest_json` | Full manifest preserved as JSON; structured columns added |
| `mailing_list_run_items` | `run_observations` | One row per run per message; `observation_type` derived from whether artifact was created |
| `mailing_list_messages` | `canonical_messages` + `message_headers` + `message_metadata` | Parsed fields split into normalized headers and metadata |
| `mailing_list_relationships` | `message_relationships` | Same structure, global key instead of source-scoped |
| `mailing_list_discussions` | `message_discussions` | Same structure, global key |
| `mailing_list_discussion_members` | `discussion_members` | Same structure, global key |
| Tombstone artifacts | `canonical_messages` with `is_tombstone=1` | Tombstone artifacts already exist; new table marks them |

### 6.2 What must be recomputed

| Current concept | Recomputed as | Notes |
|---|---|---|
| `message_key(source_id, external_message_id)` | `normalized_message_id` (global) | Source-scoped key becomes global canonical key |
| `document_id(source_id, external_message_id)` | `canonical_messages.document_id` | Already stored; just needs canonical message linkage |
| `mailing_list_messages.canonical_json` | `message_metadata` + `message_headers` | Parsed fields extracted into normalized columns |
| `mailing_list_discussions.canonical_json` | `message_discussions.canonical_json` | Same JSON, new table |
| Discussion membership depth | `discussion_members` | Recomputed from relationship graph |
| Coverage status | `acquisition_windows.coverage_complete` | Recomputed from `acquisition_runs` |
| Inclusion reason counts | `run_inclusion_reasons` | Extracted from manifest JSON |
| Patch series | `patch_series` + `patch_series_revisions` | New — must be parsed from subjects |

### 6.3 What current concepts should remain

- `governed_sources` — unchanged
- `artifacts` — unchanged
- `documents` — unchanged
- `acquisition_attempts` — unchanged
- `artifact_observations` — unchanged
- `checkpoint_events` / `current_checkpoints` — unchanged
- `mailing_list_sources` — retained as a projection view over `governed_sources` (or replaced by a query)
- `mailing_list_fetch_history` / `mailing_list_fetch_events` — unchanged (TASK-032)

### 6.4 What current concepts should be retired or split

| Current concept | Fate | Rationale |
|---|---|---|
| `mailing_list_messages` | **Retired** (replaced by `canonical_messages` + `message_headers` + `message_metadata`) | Source-scoped key becomes global; parsed fields split into headers and metadata |
| `mailing_list_relationships` | **Retired** (replaced by `message_relationships` + `message_references`) | Source-scoped key becomes global; References header split into explicit edges |
| `mailing_list_discussions` | **Retired** (replaced by `message_discussions`) | Source-scoped key becomes global |
| `mailing_list_discussion_members` | **Retired** (replaced by `discussion_members`) | Source-scoped key becomes global |
| `mailing_list_runs.canonical_json` | **Split** (structured columns + `manifest_json`) | Manifest JSON retained for backward compatibility; structured columns for efficient querying |
| `mailing_list_run_items` | **Split** (replaced by `run_observations` + `run_unavailable_observations`) | Observation type distinguishes fetched/reused/unavailable; unavailable markers separated |
| `message_key()` function | **Retired** | Replaced by global `normalized_message_id` |
| `document_id()` function | **Retired** | Document IDs already exist in `documents` table; canonical messages reference them |

### 6.5 Sequencing risks

1. **Global Message-ID key migration** — The current `message_key()` is source-scoped. The new `normalized_message_id` is global. If two sources retain the same Message-ID with different bytes, the conflict must be detected and quarantined. This requires a pre-migration scan.

2. **Discussion membership rebuild** — The current `derive_projection()` function rebuilds all discussion state from `retained_records()`. The migration must run this rebuild against the new global canonical messages.

3. **Run item migration** — `mailing_list_run_items` records must be split into `run_observations` (for fetched/reused) and `run_unavailable_observations` (for tombstones). The `observation_type` must be derived from whether the artifact was newly created or reused.

4. **Parser version tracking** — The current system has no explicit parser version. The migration must assign a baseline parser version (e.g., `v1-header-derived`) to all existing derived data.

### 6.6 Rollback considerations

- **No automatic rollback** — The migration is a one-way transformation from source-scoped to global canonical keys. Rolling back requires restoring from backup.
- **Backup before migration** — `rfi backup` must be run before migration begins.
- **Staged migration** — The migration can be staged: (1) create new tables, (2) populate from existing data, (3) switch queries to new tables, (4) drop old tables. Each stage is independently reversible until step 4.
- **Dual-read compatibility** — During migration, both old and new tables can coexist. Queries can fall back to old tables if new tables are not yet populated.

### 6.7 Compatibility strategy during migration

1. **Phase 1 — Schema addition**: Add new tables alongside existing ones. No data migration.
2. **Phase 2 — Dual write**: New acquisitions write to both old and new tables.
3. **Phase 3 — Backfill**: Migrate existing data from old tables to new tables in batches.
4. **Phase 4 — Query switch**: Switch all queries to use new tables.
5. **Phase 5 — Old table retirement**: Drop old tables after verification.

During phases 2–4, the system operates with both authorities. The `repository_revision` advances on every mutation, so snapshot-bound queries remain consistent.

---

## 7. Alternatives Considered

### 7.1 Single-table approach

Store all message data in one wide table with JSON columns for headers and metadata.

**Rejected because:** Violates the principle of separating immutable source facts from deterministic extracted facts from versioned derived relationships. A single table cannot express the different mutability rules for each layer.

### 7.2 Graph database

Use a graph database (e.g., Neo4j) for message relationships.

**Rejected because:** The project explicitly chose SQLite as the sole structured authority (TASK-020/TASK-021). A graph database would create a second authority, complicate backup/restore, and leak persistence concerns into the browser.

### 7.3 Content-addressed Message-ID

Use the SHA-256 of the normalized Message-ID as the primary key instead of the Message-ID string itself.

**Rejected because:** The normalized Message-ID is already a stable, human-readable identifier. Using it directly makes debugging and inspection easier. The SHA-256 of bytes is already captured in `canonical_messages.sha256`.

### 7.4 Per-source canonical messages

Keep the current source-scoped `message_key()` approach and add a global mapping table.

**Rejected because:** The objective explicitly requires a "global canonical message store keyed by normalized Message-ID." Source-scoping prevents reuse across sources and complicates cross-archive deduplication.

### 7.5 Event sourcing

Store all state changes as an immutable event log.

**Rejected because:** The current architecture already uses append-only immutable records for acquisition attempts and observations. Adding a full event-sourcing layer would be over-engineering for the current scope.

### 7.6 Separate databases per source

Use one SQLite database per mailing-list source.

**Rejected because:** The global canonical message store requires cross-source deduplication and relationship traversal. A single database with proper indexing is simpler and sufficient.

---

## 8. Open Questions Requiring Human Decision

1. **Global vs. source-scoped canonical messages**: Should the same Message-ID from different archives (e.g., `linux-block` and `linux-kernel`) be treated as the same canonical message? The current design says yes, but this may not always be correct if archives serve different content for the same Message-ID.

2. **Patch-series parser**: Should patch-series detection be a separate parser version, or should it be integrated into the main header parser? The current design treats it as a separate projection, but the subject parsing logic overlaps.

3. **Cross-list references**: The `References` header may contain Message-IDs from other mailing lists. Should `message_references` create edges to canonical messages from other sources, or should references be source-scoped?

4. **Tombstone supersession**: TASK-030 notes that if Lore later serves a message that was previously tombstoned, a supersession policy is needed. Should the canonical message be updated to point to the new artifact, or should a new canonical message be created with a reference to the old tombstone?

5. **Parser version naming**: What naming convention should be used for parser versions? The current design uses opaque strings, but a semantic versioning scheme may be more useful.

6. **Metadata regeneration trigger**: Should metadata regeneration be triggered automatically when a new parser version is detected, or should it require an explicit operator command?

7. **Coverage window boundaries**: The current design uses 31-day windows. Should this be configurable per source, or should it remain a fixed constant?

8. **Observation type for tombstones**: Should tombstone observations use `observation_type = 'unavailable'` in `run_observations`, or should they only appear in `run_unavailable_observations`? The current design uses the latter, but this may complicate queries that need to see all observed Message-IDs for a run.

9. **Discussion ID stability**: The current `discussion_id` is `discussion-{hash}`. Should this remain stable across parser versions, or should it be regenerated? The current design keeps it stable per parser version.

10. **Integrity verification frequency**: Should `message_integrity` be updated on every read, or only on explicit verification? The current design uses explicit verification.

---

## 9. Recommended Minimal First Implementation Slice

### Phase 1: Canonical message identity (no schema change)

1. Add a `canonical_messages` table with `normalized_message_id` as PK, referencing existing `documents` and `artifacts`.
2. Populate it from `mailing_list_messages` during a one-time migration.
3. Add a query method to `MailingListRepository` that resolves a normalized Message-ID to a canonical message.

### Phase 2: Acquisition observation separation

1. Add `run_observations` table with `observation_type` column.
2. Migrate `mailing_list_run_items` data into `run_observations`, deriving `observation_type` from whether the artifact was newly created.
3. Add `run_unavailable_observations` table for tombstone observations.
4. Migrate tombstone data from `mailing_list_run_items` into `run_unavailable_observations`.

### Phase 3: Acquisition windows and coverage

1. Add `acquisition_windows` table.
2. Add `window_id` FK to `acquisition_runs`.
3. Populate windows from existing `mailing_list_runs` data (one window per run, or group by date range).
4. Update coverage logic to use `acquisition_windows.coverage_complete`.

### Phase 4: Parser versioning and projection regeneration

1. Add `projection_versions` table.
2. Add `parser_version` column to `message_metadata` (or create the table if not yet split).
3. Add a `rebuild_projections` command that regenerates derived tables from raw artifacts.
4. Record projection version after each rebuild.

### Phase 5: Patch-series detection

1. Add `patch_series` and `patch_series_revisions` tables.
2. Implement subject-based patch-series parser.
3. Populate from `message_headers`.

### Phase 6: Old table retirement

1. Switch all queries to use new tables.
2. Drop `mailing_list_messages`, `mailing_list_relationships`, `mailing_list_discussions`, `mailing_list_discussion_members`.
3. Drop `mailing_list_run_items` (replaced by `run_observations`).

Each phase is independently testable and reversible (except Phase 6, which requires backup).

---

## 10. Architectural Status Summary

| Subsystem | Responsibility | Status |
|---|---|---|
| Canonical message store | Global Message-ID identity, immutable source facts | Proposed |
| Immutable raw artifacts | Exact bytes, content-addressed | Proposed |
| Normalized headers | Deterministic extracted header fields | Proposed |
| Parsed metadata | Deterministic extracted body/text metadata | Proposed |
| Acquisition runs | Immutable run manifests | Proposed |
| Acquisition windows | Coverage scope and completion tracking | Proposed |
| Run observations | Per-run per-message acquisition evidence | Proposed |
| Unavailable observations | Confirmed-absence evidence | Proposed |
| Message relationships | Header-derived reply edges | Proposed |
| Message references | References header edges | Proposed |
| Discussion membership | Connected component organization | Proposed |
| Patch series | Subject-based patch grouping | Proposed |
| Projection versioning | Parser/schema version tracking | Proposed |
| Integrity state | Corruption detection and quarantine | Proposed |

---

## Addendum: Architectural Self-Review

> **Purpose:** This addendum critiques the original design proposal as if written by an
> independent principal architect. It re-evaluates the domain model, authority boundaries,
> identity strategy, conceptual complexity, architectural alternatives, and long-term vision
> alignment. Only if the review reveals material flaws does it revise the proposed schema.

---

### 1. Domain Model First (Conceptual, Pre-SQL)

The repository's durable domain objects, independent of any storage layout:

#### 1.1 `CanonicalMessage`

- **Purpose:** The single source of truth for one unique email message, identified by its
  normalized `Message-ID`. Holds the immutable raw bytes (via a content-addressed artifact
  reference) and the deterministic extracted header metadata.
- **Authority:** The repository. Bytes are immutable; headers are deterministic extractions.
- **Lifecycle:** Created once when first retained. Never updated. Never deleted.
- **Owner:** Repository domain.
- **Mutability:** Immutable after creation. The `artifact_id` may be superseded only if the
  same `Message-ID` is later found with different bytes — this is a conflict, not an update.
- **Relationships:** Has one `RawArtifact` (the exact bytes). Has zero-or-one `ParsedMetadata`.
  May be referenced by many `AcquisitionObservation` records. May participate in zero-or-one
  `MessageRelationship` as a child. May be a member of zero-or-one `Discussion`. May be part
  of zero-or-one `PatchSeries`.

#### 1.2 `RawArtifact`

- **Purpose:** Immutable, content-addressed exact bytes. The physical evidence.
- **Authority:** Content-addressed filesystem + `artifacts` table metadata.
- **Lifecycle:** Created once per unique byte sequence. Never updated. Never deleted.
- **Owner:** Acquisition substrate (existing `artifacts` table).
- **Mutability:** Immutable.
- **Relationships:** Referenced by `CanonicalMessage`. Referenced by `AcquisitionObservation`.

#### 1.3 `AcquisitionObservation`

- **Purpose:** Records that one acquisition run observed one Message-ID, and what it did with
  it (discovered, fetched, reused, unavailable). This is acquisition-specific evidence, not
  canonical message truth.
- **Authority:** The acquisition run that produced it.
- **Lifecycle:** Created per run per observed Message-ID. Never updated. Never deleted.
- **Owner:** Acquisition subsystem.
- **Mutability:** Immutable.
- **Relationships:** References one `CanonicalMessage` (nullable for unavailable). References
  one `AcquisitionRun`. References one `RawArtifact` (nullable for unavailable/reused).

#### 1.4 `AcquisitionRun`

- **Purpose:** Immutable record of one bounded acquisition execution. Records what was
  requested, when, with what limits, and what terminal state was reached.
- **Authority:** The acquisition engine.
- **Lifecycle:** Created once per run. Never updated. Never deleted.
- **Owner:** Acquisition subsystem.
- **Mutability:** Immutable.
- **Relationships:** Has many `AcquisitionObservation` records. References one
  `AcquisitionWindow` (the scope it was part of).

#### 1.5 `AcquisitionWindow`

- **Purpose:** A bounded scope (e.g., a date range) within which one or more acquisition runs
  may execute. Tracks coverage completion for that scope.
- **Authority:** The acquisition orchestration layer.
- **Lifecycle:** Created per bounded scope. `coverage_complete` is updated as runs complete.
- **Owner:** Acquisition subsystem.
- **Mutability:** `coverage_complete` is mutable; all other fields immutable.
- **Relationships:** Has many `AcquisitionRun` records.

#### 1.6 `ParsedMetadata`

- **Purpose:** Deterministic extraction from raw bytes — text content, parse warnings,
  attachment information. Regenerable from `RawArtifact`.
- **Authority:** The parser.
- **Lifecycle:** Created when first parsed. Regenerated (replaced) when parser version changes.
- **Owner:** Repository domain (but produced by a parser).
- **Mutability:** Immutable per parser version. Replaced wholesale on version change.
- **Relationships:** Belongs to one `CanonicalMessage`.

#### 1.7 `MessageRelationship`

- **Purpose:** The reply edge from one message to its parent (`In-Reply-To`). Header-derived
  authority.
- **Authority:** The parser (deterministic from headers).
- **Lifecycle:** Regenerated on projection rebuild.
- **Owner:** Derived projection.
- **Mutability:** Immutable per parser version. Replaced wholesale on rebuild.
- **Relationships:** Child is a `CanonicalMessage`. Parent is a `CanonicalMessage` (nullable
  if unresolved).

#### 1.8 `MessageReference`

- **Purpose:** The `References` header entries — explicit references beyond the immediate
  parent. Header-derived authority.
- **Authority:** The parser.
- **Lifecycle:** Regenerated on projection rebuild.
- **Owner:** Derived projection.
- **Mutability:** Immutable per parser version. Replaced wholesale on rebuild.
- **Relationships:** Belongs to one `CanonicalMessage`. References zero-or-one
  `CanonicalMessage` (nullable if not retained).

#### 1.9 `Discussion`

- **Purpose:** A connected component of messages linked by reply edges. One root message.
- **Authority:** Derived from `MessageRelationship` graph.
- **Lifecycle:** Regenerated on projection rebuild.
- **Owner:** Derived projection.
- **Mutability:** Immutable per parser version. Replaced wholesale on rebuild.
- **Relationships:** Has one root `CanonicalMessage`. Has many `CanonicalMessage` members
  via `DiscussionMembership`.

#### 1.10 `DiscussionMembership`

- **Purpose:** Many-to-many link between `Discussion` and `CanonicalMessage`, with depth.
- **Authority:** Derived from `MessageRelationship` graph.
- **Lifecycle:** Regenerated on projection rebuild.
- **Owner:** Derived projection.
- **Mutability:** Immutable per parser version. Replaced wholesale on rebuild.
- **Relationships:** References one `Discussion` and one `CanonicalMessage`.

#### 1.11 `PatchSeries`

- **Purpose:** A group of messages forming a patch series (e.g., `[PATCH v1 0/3]` through
  `[PATCH v1 3/3]`). Subject-derived authority.
- **Authority:** The parser (subject parsing).
- **Lifecycle:** Regenerated on projection rebuild.
- **Owner:** Derived projection.
- **Mutability:** Immutable per parser version. Replaced wholesale on rebuild.
- **Relationships:** Has one root `CanonicalMessage`. Has many `PatchSeriesRevision` entries.

#### 1.12 `PatchSeriesRevision`

- **Purpose:** One message within a patch series, with its patch number and cover-letter flag.
- **Authority:** The parser.
- **Lifecycle:** Regenerated on projection rebuild.
- **Owner:** Derived projection.
- **Mutability:** Immutable per parser version. Replaced wholesale on rebuild.
- **Relationships:** References one `PatchSeries` and one `CanonicalMessage`.

#### 1.13 `UnavailableObservation`

- **Purpose:** Records that a Message-ID was conclusively confirmed absent (HTTP 404 from both
  archives). Does not create a `CanonicalMessage`. Does not suppress future successful fetches.
- **Authority:** The acquisition run that confirmed absence.
- **Lifecycle:** Created per run per unavailable Message-ID. Never updated. Never deleted.
- **Owner:** Acquisition subsystem.
- **Mutability:** Immutable.
- **Relationships:** References one `AcquisitionRun`. Does not reference `CanonicalMessage`.

#### 1.14 `ProjectionVersion`

- **Purpose:** Tracks which parser version produced each derived projection table, enabling
  targeted regeneration.
- **Authority:** The projection rebuild process.
- **Lifecycle:** Created/updated on each projection rebuild.
- **Owner:** Repository domain.
- **Mutability:** Immutable per `(projection_name, parser_version)`. New rows on version change.
- **Relationships:** None (metadata about other tables).

#### 1.15 `IntegrityRecord`

- **Purpose:** Tracks verification results for canonical messages — whether bytes match stored
  SHA-256, and corruption state.
- **Authority:** The integrity verification process.
- **Lifecycle:** Updated on each verification run.
- **Owner:** Repository domain.
- **Mutability:** Updated per verification.
- **Relationships:** References one `CanonicalMessage`.

---

### 2. Repository Architecture vs. Acquisition Architecture

**Critical challenge:** Several proposed entities blur the line between repository authority and
acquisition implementation.

| Entity | Classification | Rationale |
|---|---|---|
| `CanonicalMessage` | **Repository Authority** | Core identity of retained evidence. Must be global and durable. |
| `RawArtifact` | **Repository Authority** | Existing `artifacts` table. Immutable bytes. |
| `ParsedMetadata` | **Derived Projection** | Regenerable from raw bytes. Parser-versioned. |
| `MessageRelationship` | **Derived Projection** | Header-derived. Regenerable. |
| `MessageReference` | **Derived Projection** | Header-derived. Regenerable. |
| `Discussion` | **Derived Projection** | Computed from relationship graph. Regenerable. |
| `DiscussionMembership` | **Derived Projection** | Computed from relationship graph. Regenerable. |
| `PatchSeries` | **Derived Projection** | Subject-derived. Regenerable. |
| `PatchSeriesRevision` | **Derived Projection** | Subject-derived. Regenerable. |
| `AcquisitionObservation` | **Acquisition Observation** | Per-run evidence. Acquisition-specific. |
| `AcquisitionRun` | **Acquisition Observation** | Per-run record. Acquisition-specific. |
| `AcquisitionWindow` | **Acquisition Observation** | Today's implementation uses 31-day windows. This is an acquisition orchestration concept, not canonical repository truth. |
| `UnavailableObservation` | **Acquisition Observation** | Per-run negative evidence. Acquisition-specific. |
| `ProjectionVersion` | **Repository Authority** | Metadata about projection state. Needed for rebuild targeting. |
| `IntegrityRecord` | **Repository Authority** | Verification state. Needed for corruption detection. |
| `run_inclusion_reasons` | **Operational State** | Aggregated counts for operator display. Can be computed from `AcquisitionObservation`. |

**Key finding:** `AcquisitionWindow` is **not** a canonical repository concept. It describes
today's date-windowed acquisition implementation. If the acquisition strategy changes (e.g., to
event-driven polling, or to explicit Message-ID lists without date windows), the window concept
becomes meaningless. It belongs in the acquisition subsystem, not the canonical repository.

**Key finding:** `run_inclusion_reasons` is **operational state**, not authority. It can be
computed from `AcquisitionObservation` records. It should not be a separate table.

**Key finding:** `UnavailableObservation` is acquisition-specific evidence, but it records
canonical truth about a Message-ID's availability. The question is whether the *fact* that a
Message-ID was unavailable is canonical repository truth or acquisition-specific evidence.
The current design treats it as acquisition-specific (per-run), which is correct — a later run
may successfully fetch the same Message-ID.

---

### 3. Re-evaluate Identity

**Challenge:** Should `normalized_message_id` be the primary identity of a `CanonicalMessage`?

#### 3.1 Problems with Message-ID as primary key

1. **Malformed Message-IDs:** The current parser handles messages with no `Message-ID` header
   by generating `malformed-<sha256>`. These cannot be canonical messages — they have no
   stable external identity. They should remain acquisition observations only.

2. **Message-ID conflicts:** If two different sources (or two different fetches) provide the
   same normalized Message-ID with different bytes, this is a conflict. Using Message-ID as
   PK means we must either fail closed or quarantine. The current design handles this with
   `message_id_conflict` errors, but this creates a difficult operational situation.

3. **Multiple external identifiers:** A message may be known by different Message-IDs across
   archives (e.g., Lore may rewrite Message-IDs). A single canonical message may need
   multiple external aliases.

4. **Future extensibility:** If RFI later acquires non-email content (e.g., web pages, PDFs)
   that should participate in the same canonical store, Message-ID is not a universal key.

#### 3.2 Alternative: Repository-generated canonical identifiers

Use a repository-generated opaque ID (e.g., `msg-<uuid>` or `msg-<sha256>`) as the primary key,
with `normalized_message_id` as a unique indexed attribute.

**Pros:**
- Decouples canonical identity from external identifier stability
- Handles malformed Message-IDs gracefully (no external ID → no canonical message)
- Supports multiple external aliases via an alias table
- Extensible to non-email content

**Cons:**
- Loses human-readability of the primary key
- Requires an additional lookup to resolve external Message-ID → canonical ID
- The current codebase heavily uses `message_key(source_id, external_message_id)` as the
  primary key, so this is a larger conceptual shift

#### 3.3 Alternative: External identity alias table

Keep `normalized_message_id` as a unique attribute but introduce a `message_id_aliases` table
that maps multiple external identifiers to one canonical message.

**Pros:**
- Handles cross-archive Message-ID differences
- Preserves Message-ID as the primary identity for email
- Explicit about alias relationships

**Cons:**
- Adds complexity for a case that may not occur in practice (Lore generally preserves
  Message-IDs across archives)
- The alias resolution adds a join to every message lookup

#### 3.4 Recommendation: Repository-generated canonical identifier with external alias

**Most durable architecture:** Use a repository-generated `canonical_message_id` (e.g.,
`msg-<sha256_of_normalized_message_id>`) as the primary key. Store `normalized_message_id`
as a unique attribute. This:

- Handles malformed Message-IDs (they never get a canonical message)
- Supports future alias expansion via a simple unique constraint
- Decouples internal identity from external identifier format
- Is extensible to non-email content
- Preserves the property that identical Message-ID + identical bytes = same canonical message

The `canonical_message_id` is derived deterministically from the normalized Message-ID, so
it is stable and reproducible — not a random UUID.

---

### 4. Reduce Conceptual Complexity

The original proposal has 17 tables. Let me identify which are truly independent concepts:

#### 4.1 Merge opportunities

| Original Tables | Merged Into | Rationale |
|---|---|---|
| `message_headers` + `message_metadata` | `canonical_message_metadata` | Both are deterministic extractions from the same raw bytes. Headers are just metadata with a different structure. A single table with a `metadata_json` column or typed columns suffices. |
| `message_relationships` + `message_references` | `message_edges` | Both are directed edges between messages. `In-Reply-To` is a parent edge; `References` are reference edges. A single edge table with an `edge_type` column is simpler. |
| `message_discussions` + `discussion_members` | `discussion_members` (with root flag) | The discussion root is just a member with depth=0. A single membership table with a `is_root` flag eliminates the need for a separate discussions table. |
| `patch_series` + `patch_series_revisions` | `patch_series_members` (with series root) | Same pattern as discussions — the series root is a member with patch_number=0. |
| `run_inclusion_reasons` | Eliminated | Computed from `run_observations`. Not a separate concept. |
| `acquisition_windows` | Moved to acquisition subsystem | Not canonical repository truth. |

#### 4.2 Simplified conceptual model

After merging, the durable domain objects are:

1. **`CanonicalMessage`** — global canonical identity + artifact reference (Repository Authority)
2. **`CanonicalMessageMetadata`** — deterministic extracted header + body metadata, parser-versioned (Derived Projection)
3. **`MessageEdge`** — directed edge between messages (parent or reference), parser-versioned (Derived Projection)
4. **`Discussion`** — connected component with root and members, parser-versioned (Derived Projection)
5. **`PatchSeries`** — subject-derived patch grouping, parser-versioned (Derived Projection)
6. **`AcquisitionRun`** — immutable run record (Acquisition Observation)
7. **`AcquisitionObservation`** — per-run per-message observation (Acquisition Observation)
8. **`UnavailableObservation`** — per-run confirmed-absence (Acquisition Observation)
9. **`ProjectionVersion`** — parser version tracking (Repository Authority)
10. **`IntegrityRecord`** — verification state (Repository Authority)

This reduces 17 tables to 10 conceptual objects, with `AcquisitionWindow` moved to the
acquisition subsystem and `run_inclusion_reasons` eliminated.

---

### 5. Revised Architectural Alternatives

#### Alternative A: Repository-Centric Relational Model

**Concept:** A single SQLite database with normalized tables for all canonical, derived, and
observation entities. Foreign keys enforce all relationships.

- **Conceptual simplicity:** Moderate. Normalized tables are familiar but require many joins
  for traversal queries.
- **Authority boundaries:** Clear. Repository tables are immutable; derived tables are
  regenerable; observation tables are per-run.
- **Migration complexity:** High. Requires transforming source-scoped keys to global keys,
  splitting manifest JSON into structured columns, and rebuilding all derived tables.
- **Rebuildability:** Excellent. Each derived table can be rebuilt independently from raw
  artifacts + observation records.
- **Operational complexity:** Moderate. SQLite is simple to operate but requires careful
  transaction management for multi-table updates.
- **LLM traversal efficiency:** Moderate. Graph traversal requires recursive CTEs or
  iterative queries. Joins add overhead.
- **Long-term maintainability:** Good. Standard SQL is widely understood. Schema evolution
  is well-understood.

#### Alternative B: Artifact-First Repository with Materialized Projections

**Concept:** The canonical repository is a content-addressed store of immutable artifacts (raw
bytes + metadata). All derived structure (relationships, discussions, patch series) is
materialized as separate projection stores that can be rebuilt from the artifact store.
The artifact store is the only authority; projections are disposable.

- **Conceptual simplicity:** High. The mental model is simple: "artifacts are truth,
  everything else is a view."
- **Authority boundaries:** Excellent. The artifact store is the sole authority. Projections
  are explicitly disposable and regenerable.
- **Migration complexity:** Moderate. Migration is just a rebuild — no schema transformation
  needed. Old projections are discarded; new ones are generated from artifacts.
- **Rebuildability:** Excellent. Projections are always rebuildable from the artifact store.
  A parser version change triggers a full or partial rebuild.
- **Operational complexity:** Low. No multi-table transactions. Projections are built
  offline and swapped atomically.
- **LLM traversal efficiency:** High. Projections can be optimized for traversal (e.g.,
  adjacency lists, precomputed discussion membership, materialized path strings).
- **Long-term maintainability:** Excellent. The artifact store never changes schema. Only
  projections evolve. New projection types can be added without touching existing ones.

**Key difference:** In Alternative A, the canonical message table is the authority and
projections reference it. In Alternative B, the artifact store is the authority and
projections are self-contained materialized views that happen to reference artifact IDs.

**Why Alternative B is better for long-term vision:**

The RFI architecture document states: "Immutable evidence, canonical knowledge, retrieval,
intelligence, and user workflows remain separate layers." Alternative B makes this separation
explicit and physical. The artifact store is immutable evidence. Projections are canonical
knowledge. They can evolve independently.

Alternative B also aligns with the existing architecture: the acquisition substrate already
treats artifacts as the authority and `document_index()` as a rebuildable projection. The
mailing-list discussion projection is already a rebuildable derived state. Alternative B
simply makes this explicit for all derived structure.

---

### 6. Evaluation Against Long-Term Vision

The intended evolution is:

```
immutable evidence → deterministic extracted knowledge → versioned projections →
bounded LLM traversal → future intelligence generation
```

#### Alternative A (Relational)

- **Immutable evidence:** Stored in `artifacts` + `canonical_messages`. Good.
- **Deterministic extracted knowledge:** Stored in `message_headers` + `message_metadata`.
  Good, but split across tables.
- **Versioned projections:** `message_relationships`, `message_discussions`, `patch_series`
  with `parser_version` columns. Good.
- **Bounded LLM traversal:** Requires recursive CTEs and joins. Moderate efficiency.
- **Future intelligence:** New tables can be added. But schema evolution requires careful
  migration.

#### Alternative B (Artifact-First)

- **Immutable evidence:** Content-addressed artifact store. Excellent — already the
  established pattern.
- **Deterministic extracted knowledge:** Materialized as projection tables. Good.
- **Versioned projections:** Each projection has a version and can be rebuilt independently.
  Excellent.
- **Bounded LLM traversal:** Projections can be optimized for traversal (precomputed
  adjacency, materialized paths, etc.). Excellent.
- **Future intelligence:** New projection types added without touching artifact store.
  Excellent — the artifact store never changes.

**Verdict:** Alternative B better supports the long-term vision because it makes the
evidence/projection boundary explicit and physical, rather than logical. It also eliminates
the migration complexity of transforming source-scoped keys to global keys — the artifact
store already uses global content-addressed identity.

---

### 7. Revised Recommendation

After this architectural review, I recommend **Alternative B: Artifact-First Repository with
Materialized Projections**, with the following simplifications:

#### 7.1 Revised conceptual model

1. **Artifact Store** (existing `artifacts` + filesystem) — immutable, content-addressed.
   No schema changes needed.

2. **Canonical Message Registry** — a simple mapping from `normalized_message_id` to
   `artifact_id` + `document_id`. This is the only new canonical table. It answers: "given
   a Message-ID, what artifact do we have?"

3. **Acquisition Observations** — per-run records of what was discovered, fetched, reused,
   or found unavailable. References `artifact_id` and `normalized_message_id`.

4. **Materialized Projections** — rebuildable tables for relationships, discussions, patch
   series, and parsed metadata. Each projection is tagged with a `parser_version` and can
   be rebuilt from the artifact store + canonical message registry.

5. **Projection Versions** — tracks which version produced each projection.

6. **Integrity Records** — verification state per canonical message.

#### 7.2 Schema changes from original proposal

The original 17-table proposal is reduced to:

| Revised Table | Original Equivalent | Change |
|---|---|---|
| `canonical_messages` | `canonical_messages` | Simplified: PK is `canonical_message_id` (derived from Message-ID hash), `normalized_message_id` is unique attribute |
| `message_raw_artifacts` | `message_raw_artifacts` | **Eliminated** — raw artifacts are already in `artifacts` table |
| `message_headers` + `message_metadata` | `message_headers` + `message_metadata` | **Merged** into `message_parsed_metadata` (single table, parser-versioned) |
| `message_relationships` + `message_references` | `message_relationships` + `message_references` | **Merged** into `message_edges` (single edge table with `edge_type`) |
| `message_discussions` + `discussion_members` | `message_discussions` + `discussion_members` | **Simplified** to `discussion_members` with `is_root` flag |
| `patch_series` + `patch_series_revisions` | `patch_series` + `patch_series_revisions` | **Simplified** to `patch_series_members` with `is_root` flag |
| `acquisition_runs` | `acquisition_runs` | **Unchanged** in concept |
| `run_observations` | `run_observations` | **Unchanged** in concept |
| `run_unavailable_observations` | `run_unavailable_observations` | **Unchanged** in concept |
| `acquisition_windows` | `acquisition_windows` | **Moved to acquisition subsystem** — not canonical repository truth |
| `projection_versions` | `projection_versions` | **Unchanged** |
| `message_integrity` | `message_integrity` | **Unchanged** |
| `run_inclusion_reasons` | `run_inclusion_reasons` | **Eliminated** — computed from `run_observations` |

**Net result:** 11 tables (down from 17), with clearer authority boundaries and better
alignment with the existing artifact-first architecture.

#### 7.3 Key architectural decisions after review

1. **Repository-generated canonical ID** — `canonical_message_id = msg-<sha256(normalized_message_id)>`.
   This decouples internal identity from external identifier format and handles malformed
   Message-IDs gracefully.

2. **No source-scoping** — canonical messages are global. The `source_id` is an attribute
   of the first observation, not part of the key.

3. **Projections are disposable** — all derived tables (metadata, edges, discussions, patch
   series) are tagged with `parser_version` and can be rebuilt from the artifact store.
   They are not authoritative.

4. **Acquisition windows are not canonical** — they describe today's date-windowed
   acquisition implementation. Coverage tracking belongs in the acquisition subsystem.

5. **Single edge table** — `In-Reply-To` and `References` are both directed edges between
   messages. A single `message_edges` table with `edge_type` is simpler than two tables.

6. **Discussion and patch series as membership tables** — the root is just a member with
   `is_root = 1` and `depth = 0` (or `patch_number = 0`). No separate root table needed.

#### 7.4 Why the original design was flawed

1. **Over-normalization** — 17 tables for concepts that can be expressed in 11. Some tables
   (like `run_inclusion_reasons`) are just aggregations that can be computed.

2. **Source-scoping in canonical identity** — The original design still used
   `normalized_message_id` as PK, which is correct, but the `message_key()` function
   remained source-scoped. The review clarifies that canonical identity must be global.

3. **Acquisition concepts in the repository** — `acquisition_windows` is an acquisition
   orchestration concept, not canonical repository truth. It should not be in the canonical
   schema.

4. **No explicit artifact-first principle** — The original design treated `canonical_messages`
   as the authority, but the repository already treats `artifacts` as the authority. The
   review aligns the design with the existing architecture.

5. **Identity coupling** — Using `normalized_message_id` directly as PK couples internal
   identity to external format. The repository-generated ID is more durable.

---

### 8. Revised Table-by-Table Schema (Minimal Changes)

The following tables are **new** or **modified** from the original proposal:

#### 8.1 `canonical_messages` (revised)

```sql
CREATE TABLE canonical_messages (
    canonical_message_id TEXT PRIMARY KEY,  -- msg-<sha256(normalized_message_id)>
    normalized_message_id TEXT NOT NULL UNIQUE,  -- <local@domain.casefold()>
    source_id TEXT REFERENCES governed_sources(source_id),
    document_id TEXT NOT NULL UNIQUE,
    artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    media_type TEXT NOT NULL,
    sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
    byte_count INTEGER NOT NULL CHECK (byte_count >= 0),
    is_tombstone INTEGER NOT NULL DEFAULT 0 CHECK (is_tombstone IN (0, 1)),
    first_observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    canonical_json TEXT NOT NULL  -- full canonical record for backward compatibility
) STRICT;
```

**Key change:** PK is now `canonical_message_id` (repository-generated), not
`normalized_message_id`. The `normalized_message_id` is a unique attribute. `sha256` and
`byte_count` are denormalized from the artifact for fast lookup.

#### 8.2 `message_parsed_metadata` (merged from headers + metadata)

```sql
CREATE TABLE message_parsed_metadata (
    canonical_message_id TEXT PRIMARY KEY REFERENCES canonical_messages(canonical_message_id),
    parser_version TEXT NOT NULL,
    message_id_raw TEXT,
    subject TEXT NOT NULL,
    normalized_subject TEXT NOT NULL,
    sender TEXT NOT NULL,
    sender_name TEXT,
    sender_email TEXT,
    message_date TEXT,
    date_raw TEXT,
    in_reply_to TEXT,
    references_raw TEXT,
    text_content TEXT NOT NULL,
    has_attachments INTEGER NOT NULL CHECK (has_attachments IN (0, 1)),
    attachment_count INTEGER NOT NULL CHECK (attachment_count >= 0),
    content_language TEXT,
    normalized_subject_is_identity INTEGER NOT NULL CHECK (normalized_subject_is_identity IN (0, 1)),
    parse_warnings TEXT NOT NULL,  -- JSON array
    extracted_at TEXT NOT NULL,
    UNIQUE (canonical_message_id, parser_version)
) STRICT;
```

**Key change:** Merged `message_headers` and `message_metadata` into one table. All parsed
fields are in one row per message per parser version.

#### 8.3 `message_edges` (merged from relationships + references)

```sql
CREATE TABLE message_edges (
    source_message_id TEXT NOT NULL REFERENCES canonical_messages(canonical_message_id),
    target_message_id TEXT REFERENCES canonical_messages(canonical_message_id),
    target_external_message_id TEXT,
    edge_type TEXT NOT NULL CHECK (edge_type IN ('parent', 'reference')),
    authority TEXT NOT NULL CHECK (authority IN ('header', 'archive', 'inferred')),
    certainty TEXT NOT NULL CHECK (certainty IN ('direct', 'heuristic', 'unresolved')),
    position INTEGER,  -- position in References header (NULL for parent edges)
    parser_version TEXT NOT NULL,
    projected_at TEXT NOT NULL,
    PRIMARY KEY (source_message_id, edge_type, COALESCE(position, 0))
) STRICT;
```

**Key change:** Merged `message_relationships` and `message_references` into one edge table.
`edge_type` distinguishes `In-Reply-To` (parent) from `References` (reference). `position`
orders references within a message.

#### 8.4 `discussion_members` (simplified from discussions + members)

```sql
CREATE TABLE discussion_members (
    discussion_id TEXT NOT NULL,
    message_id TEXT NOT NULL REFERENCES canonical_messages(canonical_message_id),
    is_root INTEGER NOT NULL CHECK (is_root IN (0, 1)),
    depth INTEGER NOT NULL CHECK (depth >= 0),
    parser_version TEXT NOT NULL,
    projected_at TEXT NOT NULL,
    PRIMARY KEY (discussion_id, message_id)
) STRICT;
CREATE UNIQUE INDEX discussion_roots ON discussion_members(discussion_id) WHERE is_root = 1;
```

**Key change:** Eliminated `message_discussions` table. The root is just a member with
`is_root = 1`. `discussion_id` is derived from the root message ID.

#### 8.5 `patch_series_members` (simplified from series + revisions)

```sql
CREATE TABLE patch_series_members (
    series_id TEXT NOT NULL,
    message_id TEXT NOT NULL REFERENCES canonical_messages(canonical_message_id),
    is_root INTEGER NOT NULL CHECK (is_root IN (0, 1)),
    patch_number INTEGER NOT NULL CHECK (patch_number >= 0),
    is_cover_letter INTEGER NOT NULL CHECK (is_cover_letter IN (0, 1)),
    parser_version TEXT NOT NULL,
    projected_at TEXT NOT NULL,
    PRIMARY KEY (series_id, message_id),
    UNIQUE (series_id, patch_number)
) STRICT;
CREATE UNIQUE INDEX patch_series_roots ON patch_series_members(series_id) WHERE is_root = 1;
```

**Key change:** Eliminated `patch_series` table. The root is just a member with `is_root = 1`.

#### 8.6 `acquisition_runs` (unchanged concept, no `window_id`)

```sql
CREATE TABLE acquisition_runs (
    run_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES governed_sources(source_id),
    requested_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('connected','truncated','incomplete','quarantined')),
    lifecycle_status TEXT NOT NULL CHECK (
        lifecycle_status IN ('succeeded','partial','retryable_failure','terminal_failure')
    ),
    error_code TEXT,
    retryable INTEGER NOT NULL DEFAULT 0 CHECK (retryable IN (0, 1)),
    seed_limit INTEGER NOT NULL CHECK (seed_limit > 0),
    context_limit INTEGER NOT NULL CHECK (context_limit > 0),
    seed_count INTEGER NOT NULL CHECK (seed_count >= 0),
    message_count INTEGER NOT NULL CHECK (message_count >= 0),
    artifact_count_created INTEGER NOT NULL DEFAULT 0 CHECK (artifact_count_created >= 0),
    idempotent_messages INTEGER NOT NULL DEFAULT 0 CHECK (idempotent_messages >= 0),
    tombstone_count INTEGER NOT NULL DEFAULT 0 CHECK (tombstone_count >= 0),
    relationship_count INTEGER NOT NULL DEFAULT 0 CHECK (relationship_count >= 0),
    discussion_count INTEGER NOT NULL DEFAULT 0 CHECK (discussion_count >= 0),
    discovery_offset INTEGER NOT NULL DEFAULT 0 CHECK (discovery_offset >= 0),
    discovery_has_more INTEGER NOT NULL DEFAULT 0 CHECK (discovery_has_more IN (0, 1)),
    coverage_batch_id TEXT,
    coverage_complete INTEGER NOT NULL DEFAULT 0 CHECK (coverage_complete IN (0, 1)),
    relationship_status TEXT NOT NULL CHECK (
        relationship_status IN ('complete','continuation_pending','policy_truncated','failed')
    ),
    relationship_continuation TEXT,  -- JSON, nullable
    relationship_records_processed INTEGER NOT NULL DEFAULT 0,
    truncated INTEGER NOT NULL DEFAULT 0 CHECK (truncated IN (0, 1)),
    unexpected_truncation INTEGER NOT NULL DEFAULT 0 CHECK (unexpected_truncation IN (0, 1)),
    discovery_complete INTEGER NOT NULL DEFAULT 0 CHECK (discovery_complete IN (0, 1)),
    required_ancestry_complete INTEGER NOT NULL DEFAULT 0 CHECK (required_ancestry_complete IN (0, 1)),
    descendant_policy_complete INTEGER NOT NULL DEFAULT 0 CHECK (descendant_policy_complete IN (0, 1)),
    descendant_policy_limited INTEGER NOT NULL DEFAULT 0 CHECK (descendant_policy_limited IN (0, 1)),
    manifest_json TEXT NOT NULL
) STRICT;
```

**Key change:** Removed `window_id` FK. Windows are an acquisition orchestration concept,
not canonical repository truth.

#### 8.7 `run_observations` (unchanged)

No changes from original proposal.

#### 8.8 `run_unavailable_observations` (unchanged)

No changes from original proposal.

#### 8.9 `projection_versions` (unchanged)

No changes from original proposal.

#### 8.10 `message_integrity` (unchanged)

No changes from original proposal.

#### 8.11 Eliminated tables

| Table | Fate |
|---|---|
| `message_raw_artifacts` | Eliminated — raw artifacts already in `artifacts` table |
| `run_inclusion_reasons` | Eliminated — computed from `run_observations` |
| `acquisition_windows` | Moved to acquisition subsystem |

---

### 9. Revised Behavioral Invariants

The invariants remain the same as the original proposal, with the clarification that
`AcquisitionWindow` is no longer a canonical repository entity — coverage tracking is an
acquisition subsystem concern.

| # | Invariant | Enforced by |
|---|---|---|
| 1 | One canonical retained message may be referenced by many acquisition observations | `run_observations.canonical_message_id` → `canonical_messages` (many-to-one) |
| 2 | A later acquisition may reuse a valid canonical message without claiming it downloaded the message | `run_observations.observation_type = 'reused'` does not create a new artifact |
| 3 | Every acquisition still records its own discovery and coverage evidence | `acquisition_runs` + `run_observations` are per-run |
| 4 | Identical Message-ID plus identical bytes reuses the canonical artifact | `canonical_messages.sha256` UNIQUE; `retain_message` checks existing artifact |
| 5 | Identical Message-ID plus different bytes fails closed or records a quarantined conflict | `message_id_conflict` error; `message_integrity.corruption_state = 'quarantined'` |
| 6 | Unavailable markers do not permanently suppress a later successful fetch | `run_unavailable_observations` has no FK to `canonical_messages` |
| 7 | Derived metadata can be regenerated from immutable raw artifacts | `message_parsed_metadata` is derived from `artifacts` via `parser_version` |
| 8 | Acquisition coverage remains independent from canonical message existence | `acquisition_runs.coverage_complete` is per-run; `canonical_messages` is independent |
| 9 | Overlapping windows may reuse canonical content while retaining independent observation records | `run_observations` is keyed by `(run_id, external_message_id)` |

---

### 10. Revised Example Query Paths

The query sketches from Section 5 remain valid with minor adjustments:

- Discussion root and descendants: now uses `discussion_members` with `is_root` flag
- Patch series: now uses `patch_series_members` with `is_root` flag
- Message with provenance: unchanged
- LLM triage: unchanged
- Missing ancestors: unchanged
- Parser version regeneration: unchanged

The key change is that `discussion_id` and `series_id` are now derived from the root message
ID rather than being independent identities.

---

### 11. Revised Migration Analysis

The migration strategy is simplified because:

1. **No `AcquisitionWindow` table** — windows remain in the acquisition subsystem.
2. **No `message_raw_artifacts` table** — raw artifacts already exist in `artifacts`.
3. **No `run_inclusion_reasons` table** — computed from observations.
4. **Repository-generated canonical IDs** — `canonical_message_id = msg-<sha256(normalized_message_id)>`.
   This is deterministic and reproducible.
5. **Merged tables** — `message_headers` + `message_metadata` → `message_parsed_metadata`;
   `message_relationships` + `message_references` → `message_edges`;
   `message_discussions` + `discussion_members` → `discussion_members`;
   `patch_series` + `patch_series_revisions` → `patch_series_members`.

The migration is now:

1. Create new tables alongside existing ones.
2. Populate `canonical_messages` from `mailing_list_messages` (global key).
3. Populate `message_parsed_metadata` from parsed raw artifacts.
4. Populate `message_edges` from `mailing_list_relationships` + `message_headers.references`.
5. Populate `discussion_members` from `mailing_list_discussions` + `mailing_list_discussion_members`.
6. Populate `patch_series_members` from subject parsing.
7. Populate `acquisition_runs` from `mailing_list_runs` (structured columns).
8. Populate `run_observations` from `mailing_list_run_items`.
9. Populate `run_unavailable_observations` from tombstone run items.
10. Switch queries to new tables.
11. Drop old tables.

---

### 12. Revised Open Questions

The following open questions from Section 8 remain relevant. Additional questions:

11. **Canonical message ID format**: Should `canonical_message_id` be `msg-<sha256>` or
    `msg-<uuid>`? SHA-256 is deterministic and reproducible; UUID is simpler but requires
    storage.

12. **Edge table position semantics**: For `References` edges, should `position` be the
    index in the References header, or should each referenced Message-ID get its own row
    regardless of position?

13. **Discussion ID derivation**: Should `discussion_id` be derived from the root message ID,
    or should it be an independent identity? Deriving from root is simpler but means
    re-rooting a discussion changes its ID.

14. **Patch series root detection**: The current design uses `patch_number = 0` for the
    cover letter. But some series don't have a cover letter. Should the root be the first
    patch by number, or should it be independently identified?

15. **Projection rebuild scope**: When a parser version changes, should all projections be
    rebuilt, or only those affected by the change? The current design rebuilds all.

---

### 13. Revised Minimal First Implementation Slice

The implementation phases are simplified:

**Phase 1:** Add `canonical_messages` table. Populate from existing `mailing_list_messages`.
Add query method to resolve Message-ID → canonical message.

**Phase 2:** Add `run_observations` and `run_unavailable_observations`. Migrate
`mailing_list_run_items` data.

**Phase 3:** Add `message_parsed_metadata` (merged headers + metadata). Populate from parsed
raw artifacts.

**Phase 4:** Add `message_edges` (merged relationships + references). Populate from existing
relationship and header data.

**Phase 5:** Add `discussion_members` (simplified discussions + members). Populate from
existing discussion data.

**Phase 6:** Add `patch_series_members`. Implement subject-based patch-series parser.

**Phase 7:** Add `projection_versions` and `message_integrity`.

**Phase 8:** Add `acquisition_runs` (structured columns). Migrate `mailing_list_runs`.

**Phase 9:** Switch all queries to new tables.

**Phase 10:** Drop old tables.

Phases 1–3 can be done independently and provide immediate value (global canonical identity,
observation separation, parsed metadata). Phases 4–6 add derived projections. Phases 7–10
add operational tooling and clean up.

---

### 14. Conclusion

The architectural self-review revealed that the original 17-table proposal over-normalized
the schema and blurred the boundary between canonical repository truth and acquisition
implementation details. The revised design:

- Reduces 17 tables to 11 (3 eliminated, 4 merged)
- Moves `acquisition_windows` to the acquisition subsystem
- Eliminates `message_raw_artifacts` (already in `artifacts` table)
- Eliminates `run_inclusion_reasons` (computed from observations)
- Merges headers + metadata into `message_parsed_metadata`
- Merges relationships + references into `message_edges`
- Simplifies discussions + members into `discussion_members` with `is_root` flag
- Simplifies patch series + revisions into `patch_series_members` with `is_root` flag
- Uses repository-generated canonical IDs for future extensibility
- Aligns with the existing artifact-first architecture

The revised design is simpler, more durable, and better aligned with the repository's
long-term vision of evidence → knowledge → projections → traversal → intelligence.

---

## Final Mailing-List Architecture Stress Review

> **Purpose:** Independent principal-architect stress test of the revised canonical mailing-list
> message store, assuming five years of production operation with tens of millions of messages,
> overlapping acquisitions, conflicting evidence, and multiple parser generations.

---

### Executive Verdict

**ACCEPTABLE with MUST-FIX corrections.** The revised design correctly separates immutable
evidence from derived projections and acquisition observations. However, three critical flaws
threaten long-term durability: (1) the `canonical_message_id` derivation from
`sha256(normalized_message_id)` creates an unresolvable collision risk for malformed Message-IDs,
(2) the `message_edges` table merges parent and reference edges with incompatible lifecycle rules,
and (3) discussion identity derived from root message ID is unstable under re-rooting. These must
be corrected before implementation. Two additional SHOULD-FIX items address query efficiency
and patch-series adequacy.

---

### Prioritized Findings

#### MUST FIX

**F1. Malformed Message-ID collision in canonical_message_id derivation**

- **Finding:** `canonical_message_id = msg-<sha256(normalized_message_id)>`. When `Message-ID`
  is absent or malformed, the parser generates `malformed-<sha256(raw_bytes)>`. Two different
  malformed messages could theoretically collide if their raw bytes happen to produce the same
  SHA-256 (astronomically unlikely but architecturally unsound). More importantly, the
  `malformed-` prefix embeds the raw bytes hash into the identity, coupling internal identity
  to content — which violates the principle that canonical identity should be stable regardless
  of content changes.
- **Failure scenario:** A malformed message is retained. Later, a corrected version of the same
  message (with a proper Message-ID) is acquired. The system cannot recognize these as the same
  logical message because the malformed identity is content-derived, not stable.
- **Classification:** MUST FIX
- **Correction:** For messages with a valid `normalized_message_id`, use
  `msg-<sha256(normalized_message_id)>`. For messages without a valid Message-ID, do **not**
  create a `canonical_messages` row — keep them as acquisition observations only. If a canonical
  message is later created for the same content (e.g., the message is reposted with a proper
  Message-ID), the observation can be linked retroactively.

**F2. `message_edges` merges incompatible lifecycle concepts**

- **Finding:** The `message_edges` table merges `In-Reply-To` (parent) edges and `References`
  edges. Parent edges have a strict one-parent-per-child constraint and are used for discussion
  tree construction. Reference edges are unordered, may have multiple targets, and are used for
  graph traversal. Merging them under a single `edge_type` column with `position` for ordering
  creates ambiguity: a parent edge has no position, but the PK includes `COALESCE(position, 0)`,
  meaning a message can have at most one parent edge and one reference edge at position 0.
- **Failure scenario:** A message has both an `In-Reply-To` and a `References` entry pointing to
  the same parent. The PK constraint `(source_message_id, edge_type, COALESCE(position, 0))`
  allows both (different `edge_type`), but downstream code that filters by `edge_type = 'parent'`
  may miss the reference edge, and vice versa. More critically, if a parser change reclassifies
  a reference as a parent (or vice versa), the old edge is not invalidated.
- **Classification:** MUST FIX
- **Correction:** Split back into two tables: `message_parent_edges` (one parent per child,
  `certainty` determines if parent is resolved) and `message_reference_edges` (many references
  per message, ordered by position). This preserves the different integrity rules: parent edges
  have a `CHECK` that enforces one-parent-per-child; reference edges allow many.

**F3. Discussion identity instability under re-rooting**

- **Finding:** `discussion_id` is derived from the root message ID. If the discussion tree is
  re-rooted (e.g., a new earliest message is discovered that becomes the new root), the
  `discussion_id` changes, breaking all external references to the old discussion.
- **Failure scenario:** A discussion has 5,000 messages rooted at message A. Later, a message
  predating A is discovered and becomes the new root. The `discussion_id` changes from
  `discussion-<hash(A)>` to `discussion-<hash(new_root)>`. All LLM traversal queries, bookmarks,
  and external references to the old discussion_id are broken.
- **Classification:** MUST FIX
- **Correction:** Use a stable `discussion_id` that is independent of the root message. Options:
  (a) Generate a UUID at first projection and persist it in `discussion_members`; (b) Derive from
  the earliest message date + source_id (stable but may change if earlier messages are found);
  (c) Use a content hash of the full discussion membership set (stable but expensive to recompute).
  Option (a) is simplest and most durable.

#### SHOULD FIX

**F4. Missing index on `message_edges.target_message_id` for reverse traversal**

- **Finding:** The `message_edges` table has no index on `target_message_id`, which is needed
  for reverse traversal (finding children of a message). With tens of millions of edges, this
  requires a full table scan.
- **Failure scenario:** An LLM traversal query asks "find all children of message X." Without
  an index on `target_message_id`, this scans the entire `message_edges` table.
- **Classification:** SHOULD FIX
- **Correction:** Add `CREATE INDEX message_edges_target ON message_edges(target_message_id,
  edge_type)`.

**F5. Patch-series cross-thread revision detection is inadequate**

- **Finding:** The `patch_series_members` table uses `series_id` derived from the root message.
  Cross-thread revisions (where a v2 repost appears in a different thread) are not linked.
  The `is_root` flag only identifies the first message in a series within one thread.
- **Failure scenario:** `[PATCH v1 0/3]` starts a thread. `[PATCH v2 0/3]` starts a new thread
  but references the v1 cover letter in its `References` header. The system creates two
  separate `series_id`s, missing the revision lineage.
- **Classification:** SHOULD FIX
- **Correction:** Add a `parent_series_id` column to `patch_series_members` that links to the
  previous version's series. This is populated by the parser when it detects cross-thread
  revision references in the `References` or `In-Reply-To` headers.

#### ACCEPTABLE RISK

**F6. `canonical_messages.sha256` denormalization may diverge from `artifacts.sha256`**

- **Finding:** `canonical_messages.sha256` is denormalized from `artifacts.sha256`. If the
  artifact is updated (e.g., due to a conflict resolution), the canonical message's SHA-256
  may become stale.
- **Risk:** Low. The `canonical_messages` table is immutable after creation. Artifact updates
  require creating a new canonical message (conflict scenario), not updating the existing one.
- **Classification:** ACCEPTABLE RISK
- **Mitigation:** Add a `CHECK` constraint or trigger to verify `canonical_messages.sha256 =
  artifacts.sha256` on insert. Or remove the denormalized column and always join to `artifacts`.

**F7. `message_integrity` updated on every verification creates write contention**

- **Finding:** `message_integrity` is updated on every verification run. With tens of millions
  of messages, this creates significant write load.
- **Risk:** Moderate. Verification is typically run offline and can be batched.
- **Classification:** ACCEPTABLE RISK
- **Mitigation:** Batch integrity updates in a single transaction. Consider partitioning by
  `last_verified_at` for incremental verification.

**F8. `run_observations` row count explosion**

- **Finding:** With tens of millions of messages and hundreds of acquisition runs,
  `run_observations` could have billions of rows.
- **Risk:** Low. Each row is small (8 columns, mostly TEXT FKs). SQLite handles billions of
  rows, though query performance requires careful indexing.
- **Classification:** ACCEPTABLE RISK
- **Mitigation:** Ensure indexes on `(run_id, external_message_id)`, `(canonical_message_id)`,
  and `(observation_type)`. Consider partitioning by `run_id` if needed.

#### DEFERRED FEATURE

**F9. Cross-archive Message-ID alias resolution**

- **Finding:** The same logical message may have different Message-IDs in different archives
  (e.g., Lore may rewrite Message-IDs). The current design assumes `normalized_message_id` is
  globally unique, which may not hold.
- **Risk:** Low for Linux kernel mailing lists (Lore preserves Message-IDs), but could be an
  issue for cross-archive federation.
- **Classification:** DEFERRED FEATURE
- **Future work:** Add a `message_id_aliases` table mapping alternative Message-IDs to the
  canonical message. Populate when cross-archive evidence is detected.

---

### Failure Scenarios

#### Scenario 1: Conflicting bytes for same Message-ID

1. Run A acquires `<abc@def>` with bytes hash H1. Creates `canonical_messages` row.
2. Run B acquires `<abc@def>` with bytes hash H2 (different content).
3. `retain_message` detects `artifact_id` mismatch and raises `message_id_conflict`.
4. **Current behavior:** Acquisition fails. The conflict is not recorded.
5. **Risk:** The operator cannot inspect the conflict later. The run is lost.
6. **Correction:** Record the conflict in `message_integrity` with
   `corruption_state = 'quarantined'` and `verification_error = 'conflicting_bytes'`.
   Allow the acquisition to continue for other messages.

#### Scenario 2: Long discussion with 5,000 descendants

1. A discussion root has 5,000 direct and indirect children.
2. `discussion_members` has 5,001 rows for this discussion.
3. LLM traversal query: "fetch root and all descendants."
4. **Current behavior:** Single query with JOIN on `discussion_members`. Returns 5,001 rows.
5. **Risk:** Query may return too much data for a single LLM context window.
6. **Mitigation:** Add `LIMIT` and `OFFSET` to traversal queries. Use `depth` for
   depth-limited traversal.

#### Scenario 3: Parser version change requires full rebuild

1. Parser v2 is deployed. All `message_parsed_metadata`, `message_edges`, `discussion_members`,
   and `patch_series_members` rows are invalidated.
2. Rebuild scans all `canonical_messages` and re-parses all raw artifacts.
3. **Current behavior:** Full rebuild of all derived tables. Takes hours for 10M messages.
4. **Risk:** Extended downtime during rebuild.
5. **Mitigation:** Allow incremental rebuild by `parser_version`. Rebuild one table at a time.
   Use `projection_versions` to track which tables are stale.

#### Scenario 4: Unavailable message later becomes available

1. Run A confirms `<xyz@def>` is unavailable (404 from both archives). Creates
   `run_unavailable_observations` row.
2. Run B (months later) successfully fetches `<xyz@def>`.
3. **Current behavior:** Run B creates a `canonical_messages` row. Run A's unavailable
   observation remains.
4. **Risk:** None. The invariant "unavailable markers do not permanently suppress a later
   successful fetch" is satisfied.
5. **Verification:** Query `run_observations` for `<xyz@def>` — should show both
   `observation_type = 'unavailable'` (from Run A) and `observation_type = 'fetched'`
   (from Run B).

---

### Recommended Corrections

1. **MUST FIX — Malformed Message-ID handling:** Do not create `canonical_messages` rows for
   messages without a valid `normalized_message_id`. Keep them as acquisition observations only.

2. **MUST FIX — Split `message_edges`:** Create `message_parent_edges` (one parent per child,
   with `certainty` determining resolution) and `message_reference_edges` (many references per
   message, ordered by position).

3. **MUST FIX — Stable discussion identity:** Generate `discussion_id` as a UUID at first
   projection, stored in `discussion_members`. Do not derive from root message ID.

4. **SHOULD FIX — Add reverse-traversal index:** `CREATE INDEX message_edges_target ON
   message_edges(target_message_id, edge_type)`.

5. **SHOULD FIX — Patch-series revision linkage:** Add `parent_series_id` column to
   `patch_series_members` for cross-thread revision detection.

6. **SHOULD FIX — Conflict recording:** Record `message_id_conflict` in `message_integrity`
   with `corruption_state = 'quarantined'` instead of failing the acquisition.

---

### Revised Implementation Gate

Before implementation begins, the following must be resolved:

1. ✅ Canonical message identity uses repository-generated `canonical_message_id` (not
   `normalized_message_id` as PK)
2. ✅ Malformed Message-IDs do not create canonical messages
3. ❌ `message_edges` split into `message_parent_edges` and `message_reference_edges`
4. ❌ `discussion_id` is a stable UUID, not derived from root message ID
5. ❌ Reverse-traversal index on `target_message_id`
6. ❌ `parent_series_id` for cross-thread patch-series revisions
7. ❌ Conflict recording in `message_integrity` instead of acquisition failure

**Gate status: NOT MET** — 5 of 7 corrections are unaddressed.

---

### Remaining Questions Requiring Human Decision

1. **Conflict resolution policy:** When conflicting bytes are found for the same Message-ID,
   should the acquisition fail, quarantine the conflict, or accept the newer bytes? The current
   design fails closed. Should this be configurable per source?

2. **Discussion ID persistence:** Should `discussion_id` UUIDs be persisted in
   `discussion_members` (requiring schema changes on rebuild), or should they be derived
   deterministically from a stable property (e.g., the root message's `canonical_message_id`
   + a salt)?

3. **Patch-series cross-thread detection:** How aggressively should the parser detect
   cross-thread revisions? Should it only follow `References` headers, or should it also
   match on subject similarity?

4. **Incremental rebuild granularity:** When a parser version changes, should all derived
   tables be rebuilt, or should each table track its own `parser_version` independently?
   The current design uses a single `parser_version` per table, but a parser change may only
   affect some tables.

5. **Integrity verification scope:** Should `message_integrity` be verified on every read
   (ensuring data integrity at query time), or only on explicit verification runs? On-read
   verification adds latency but catches corruption immediately.

6. **Observation retention:** With billions of `run_observations` rows, should old observations
   be archived or pruned? The current design says "never deleted," but this may not be
   operationally sustainable.

7. **Tombstone supersession:** When a previously unavailable message becomes available,
   should the `run_unavailable_observations` row be marked as superseded, or should it remain
   as historical evidence? The current design keeps it as historical evidence.

8. **Cross-archive deduplication:** Should the system attempt to detect when the same logical
   message appears under different Message-IDs in different archives? This requires content
   similarity analysis and is deferred, but the question of whether to attempt it at all
   remains open.

9. **LLM traversal pagination:** Should the traversal queries include built-in pagination
   (LIMIT/OFFSET), or should pagination be handled by the caller? With 5,000-message
   discussions, unbounded queries could overwhelm LLM context windows.

10. **Patch-series cover letter detection:** The current design uses `patch_number = 0` for
    the cover letter. But some series use `[PATCH 0/N]` and some don't have a cover letter
    at all. Should cover letter detection be heuristic (subject parsing) or structural
    (References header analysis)?
