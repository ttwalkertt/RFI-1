# ADR 0013: Browser-local admin preferences and shared firm context

## Status

Accepted for TASK-017.

## Context

Source Profiles and Pull Sources are adjacent views of the same local, single-operator console.
Both use the repository-owned `firm_id` returned by their server APIs to identify the firm whose
acquisition configuration the operator is inspecting or acting upon. Losing that navigation
context on every page transition adds friction, but the context does not affect correct server
behavior and is not domain configuration.

## Decision

The console uses one packaged browser module, `admin_preferences.js`, backed by `localStorage`.
The namespace is `rfi.admin.preferences.v1`; the shared firm key is `current_firm`, producing the
complete storage key `rfi.admin.preferences.v1.current_firm`.

Firm context is console-wide rather than page-scoped. Source Profiles and Pull Sources express the
same operator concept: the current target firm. Source Profiles applies an explicit `firm_id` URL
parameter first, then a valid remembered firm, then the first firm in deterministic display order.
Pull Sources restores a valid remembered firm as its initial single selection. Each page validates
the identifier against its current server-provided list. Invalid stored values are discarded;
empty lists remain usable and select nothing.

The module owns key construction, JSON serialization, parsing, missing-value fallback, validation,
stale removal, and exception handling for storage discovery, reads, writes, and removals. Failures
return deterministic fallbacks or `false`; they never become API, profile, pull, acquisition, or
repository errors.

## Authority boundary

Browser preferences are disposable presentation state. They are never sent in source-profile
payloads, read by server services, stored below `--state`, revisioned, included in acquisition
identity or provenance, backed up with repository evidence, or used for secrets. Restoration uses
GET requests only. A profile PUT and pull POST remain explicit operator actions.

## Alternatives considered

- Page-scoped keys were rejected because they would preserve two conflicting meanings for the
  same current-firm concept across adjacent workflow pages.
- Query parameters alone were retained as explicit navigation overrides but rejected as session
  persistence because ordinary refresh/navigation does not consistently carry them.
- A server-side generic settings store was rejected because browser-local presentation state does
  not need CLI sharing, repository backup, audit, multi-operator coordination, or server authority.
- Cookies, a front-end framework, and a third-party state manager add transport or dependency
  surface without improving this bounded local-console requirement.

## Consequences and future boundary

Clearing or blocking browser storage loses the preference without affecting correctness. Browser
profiles and devices do not synchronize. A future state-directory-backed settings service is
justified only for non-secret operational values that must be shared with the CLI, follow `--state`,
participate in backup/restore, serve multiple operators or processes, or become validated policy.
Protected values require a separately designed credential or secret facility, never this module.
