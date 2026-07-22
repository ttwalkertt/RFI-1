# TASK-030 review — Confirmed-unavailable mailing-list ancestor tombstones

## Outcome

Bounded Lore acquisition now treats a required ancestor as conclusively unavailable only after the
configured list archive and Lore's `/all/` archive both return HTTP 404 for its exact Message-ID.
The repository retains an immutable JSON tombstone, resolves the child's header-authoritative reply
edge to that node, and permits the acquisition window to establish coverage when every other policy
condition completes.

No email content is fabricated. The tombstone uses
`application/vnd.rfi.mailing-list-tombstone+json`, records both attempted URLs and status codes, and
declares `content_synthesized: false`. The operator console reports **Connected with unavailable
ancestors** and labels the retained tombstone separately from real messages.

## Changed files

- `src/rfi/mailing_lists/provider.py` — separates HTTP 404 from generic rejection and confirms
  two-path absence.
- `src/rfi/mailing_lists/contracts.py` — carries sanitized error details and tombstone projection
  fields.
- `src/rfi/mailing_lists/parser.py` — creates the derived non-message tombstone projection.
- `src/rfi/mailing_lists/repository.py` — retains typed immutable tombstone evidence and rebuilds
  it offline.
- `src/rfi/mailing_lists/service.py` — admits confirmed tombstones into ancestor closure,
  connectivity, manifests, and queries.
- `src/rfi/mailing_lists/workflow.py` — distinguishes tombstone-complete evidence from ordinary
  complete evidence.
- `src/rfi/admin/linux_mailing_lists.html` — discloses tombstone state and suppresses dead Lore
  message links.
- `docs/operator-guide.md`, `docs/linux-mailing-list-operator-console.md`, and
  `docs/linux-kernel-mailing-list-intelligence-stream.md` — document semantics and recovery.
- `tests/test_task030.py` — deterministic acceptance and regression proof.

## Validation evidence

Focused TASK-030 suite:

```text
.venv/bin/python -m unittest tests.test_task030
Ran 5 tests in 0.062s
OK
```

Mailing-list regression suite:

```text
.venv/bin/python -m unittest \
  tests.test_task023 tests.test_task028 tests.test_task029 tests.test_task030
Ran 48 tests in 3.084s
OK
```

Full validation:

```text
.venv/bin/python -m unittest discover -s tests -q
315 discovered tests
exit status 0
```

`git diff --check` also completed without errors.

The TASK-030 tests prove:

- two 404 responses produce `archive_message_not_found` with both negative observations;
- 404 followed by 403 does not produce confirmed absence;
- 403 ancestor failure retains the existing incomplete behavior;
- the tombstone closes the ancestor path and sets `coverage_complete`;
- the stored content is typed JSON and explicitly says no content was synthesized;
- descendant enumeration does not repeatedly request the known-unavailable tombstone root;
- connectivity validation passes;
- offline rebuild reproduces the same tombstone path; and
- a repeated run creates no new artifacts and reports both retained records idempotent.

## Limitations

- Confirmation is specific to Lore and uses the two repository-supported namespaces at acquisition
  time; it does not assert that the message never existed outside Lore.
- A tombstone closes the known header-derived path. Unknown siblings beneath an unavailable root
  cannot be enumerated and are outside the retained component.
- Tombstones currently share the stable Message-ID document identity with the unavailable email.
  If Lore later begins serving that exact message, explicit tombstone supersession policy will be
  needed before replacing the current document observation.
- Existing repositories are changed only by a new acquisition. Historical incomplete runs are not
  rewritten or silently reclassified.

## Architectural Status Summary

| Subsystem | Responsibility | Status |
| --- | --- | --- |
| Lore adapter | Bounded retrieval, fallback, HTTP classification, two-path absence proof | Complete |
| Tombstone evidence | Immutable typed negative observation with no synthesized email | Complete |
| Ancestor closure | Resolve confirmed-unavailable connectors without weakening other failures | Complete |
| Discussion projection | Include tombstones in acyclic stored paths and expose tombstone counts | Complete |
| Coverage workflow | Advance only when tombstone closure and all other policies complete | Complete |
| Operator console | Distinguish ordinary complete, tombstone-complete, and incomplete evidence | Complete |
| Offline rebuild | Recreate tombstone nodes and relationships without network access | Complete |
| Tombstone supersession | Replace a tombstone if Lore later serves real content | Not Started |

The architectural change is a new explicit negative-evidence subtype inside the existing immutable
artifact authority. It does not add a datastore or a synthetic email representation. Relationship
authority remains the retained child's `In-Reply-To` header; the tombstone only supplies a durable
target for a connector whose content Lore conclusively does not provide.

The next architectural milestone, if operating evidence requires it, is a governed supersession
rule that preserves the tombstone observation while promoting subsequently available real message
content to the same stable document identity.
