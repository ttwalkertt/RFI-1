# Admin Console Preferences

RFI-1 keeps low-risk operator interface preferences behind one browser-side boundary. The current
implementation remembers the selected firm across Source Profiles, Pull Sources, navigation, and
ordinary refreshes in the local single-operator console.

## Contract

`src/rfi/admin/admin_preferences.js` is the only production code that accesses `localStorage`.
It exposes namespaced read, write, and remove operations plus firm-context helpers. Values are JSON
serialized under `rfi.admin.preferences.v1.<key>`. The current shared key is
`rfi.admin.preferences.v1.current_firm` and its value must be a non-empty string.

Every restoration validates the value against the current server-provided firm list. Source
Profiles chooses an explicit valid `firm_id` URL parameter, otherwise the remembered firm,
otherwise the first firm in canonical-name/ID order. Pull Sources restores the remembered firm only
when it appears in the configured-firms response. An empty list produces no selection.

Malformed JSON, unexpected value types, stale identifiers, missing storage, access exceptions,
quota/write failures, and removal failures are preference-local conditions. The console falls back
without reporting repository or domain corruption. Invalid readable values are removed when
possible; failed cleanup is harmless.

## Non-authoritative data only

Appropriate future values include filters, sort order, page size, selected tabs, and collapsed
panels. Do not store source-profile configuration, retrieval locators, acquisition policy,
repository identity, evidence, provenance, form drafts, credentials, tokens, secrets, or personal
data. Preference state is not sent to server APIs and is not stored beneath the RFI state directory.

Restoring firm context performs only server reads. Saving a source profile remains an explicit PUT
that creates a revision. Starting a pull remains an explicit POST. Correct CLI and server behavior
does not depend on browser storage.

## Future durable settings

A separate server-owned settings capability may be warranted if a value must follow `--state`, be
shared by browser and CLI, survive browser-profile replacement, participate in backup/restore,
coordinate multiple operators/processes, or serve as validated operational policy. Sensitive
values additionally require a purpose-built secret boundary. Neither case should extend this
disposable preference store.
