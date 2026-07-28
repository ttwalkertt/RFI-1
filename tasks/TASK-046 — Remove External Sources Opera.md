TASK-046 — Remove External Sources Operator Screen
Status
Complete
Objective
Remove the standalone External Sources operator presentation and its navigation entry while retaining the repository-global governed source registry, its HTTP APIs, persistence, validation, and all existing consumers unchanged.
This task removes a human-facing administration surface. It does not remove, relocate, or redesign source-registry capability.
Preferred change shape
Delete the page route, template, page composition, exclusive presentation assets, navigation entries, operator-facing links, and associated UI tests. Revise help and operator documentation, then add or adjust focused regression tests.
No production changes below the operator presentation and route-composition layer are expected. Any change to repository, service, API, acquisition, stream-domain, or persistence code requires explicit justification in the review report.
Scope
Remove the operator presentation
Remove External Sources from top-level operator navigation.
Remove the /external-sources operator-page route from normal route composition.
Remove the external_sources.html template.
Remove presentation assets used exclusively by the screen, including applicable:page-specific JavaScript;
page-specific CSS selectors;
route constants;
template registration;
navigation-test fixtures;
page-title or page-inventory entries.

Remove UI tests whose only purpose was verifying the deleted screen.
Update remaining UI tests to assert the revised operator-page inventory.
Do not remove shared API clients, source-profile serializers, validation logic, or styles used by other screens.
Revise remaining operator guidance
Remove links and instructions directing operators to /external-sources.
Revise Streams guidance to describe governed sources as repository-provided inputs.
Do not direct operators to another management page.
Do not imply that source creation or transport-policy management is available through the operator UI.
Remove or revise operator-help content that describes use of the deleted screen.
Preserve developer-, integration-, test-, and machine-facing API documentation.
Preserve internal registry use
The governed-source registry remains available to:
Streams;
Linux mailing-list workflows;
acquisition services;
repository initialization and restore;
existing API consumers;
tests and integrations.
Existing governed sources remain selectable and usable without the removed route or template.
Required invariants
The following must retain their existing contracts and behavior:
MailingListSourceService validation and creation.
MailingListRepository registration, lookup, enumeration, immutability, and conflict handling.
Governed-source persistence tables, constraints, migrations, identities, and transport policies.
Source-profile serializers and data models.
Existing API endpoints:GET /api/external-sources
POST /api/external-sources/validate
POST /api/external-sources

API request and response schemas, status codes, field semantics, documented ordering, validation errors, idempotency, and mutation effects.
Streams’ use of GET /api/external-sources.
Stream validation, YAML import/export, revisions, source references, and execution.
Linux mailing-list source resolution and reuse.
Initialization, backup, restore, and compatibility with existing records.
CLI and other machine-facing behavior.
GET /external-sources must be handled exactly like any other unknown operator-page route. The implementation must not add a special tombstone route.
Explicit non-goals
No replacement source-registry page.
No redirect from /external-sources.
No registry controls embedded in Streams, Linux Mailing Lists, Target Firms, or another page.
No new source-management workflow.
No API removal, renaming, versioning, or access-policy change.
No repository, schema, migration, or data-model change.
No changes to source identity or transport-policy rules.
No acquisition, publication, retrieval, or stream-execution behavior change.
No redesign of Streams or mailing-list workflows.
No suppression of machine-facing API documentation.
Acceptance criteria
External Sources is absent from every top-level operator navigation bar.
GET /external-sources receives the application’s ordinary unknown-route response and does not redirect.
The route table contains no dedicated /external-sources page handler.
No remaining operator link or instruction directs users to /external-sources.
Streams describe governed sources only as repository-provided inputs.
The removed screen is not relocated, embedded, renamed, or recreated elsewhere.
No operator page contains controls capable of creating, validating, or modifying governed source profiles or transport policies.
The three existing /api/external-sources endpoints retain their observable behavior.
Streams continue to list and select existing governed sources through the unchanged API.
Existing saved streams referencing governed source IDs still load, validate, export, and run unchanged.
One established Linux mailing-list workflow can resolve or reuse a governed source without the removed page route or template.
Existing governed-source records and immutable transport policies remain unchanged across startup.
Focused tests and the full repository validation suite pass.
Required evidence
Presentation removal
Rendered-page assertions showing the navigation entry is absent.
An ordinary unknown-route assertion for GET /external-sources.
A route-inventory assertion proving no dedicated handler remains.
Negative assertions proving no operator page contains governed-source management controls.
Repository search evidence showing no remaining operator-facing link to /external-sources.
API preservation
Provide a semantic before/after comparison of all three API endpoints from equivalent repository state, covering:
response status;
response schema;
field values;
ordering guarantees;
validation behavior;
idempotent repetition;
immutable-profile conflicts;
mutation effects.
Use exact fixture comparisons where responses are deterministic.
Consumer preservation
A focused regression proving Streams still obtain governed-source inputs through GET /api/external-sources.
A focused saved-stream regression using a pre-existing governed source.
Reuse an existing focused test, or add the smallest focused regression, proving that one established Linux mailing-list workflow resolves or reuses a governed source without the removed route or template.
Do not broaden or redesign that workflow.
Persistence preservation
A bounded proof demonstrating:
migration head or schema version is unchanged;
no migration files were added or modified;
governed-source table definitions are unchanged;
an existing-record startup test passes.
Completion evidence
Focused test results.
Full make validate results.
Review report identifying any unexpected changes below the presentation layer and justifying them.
Documented limitations.
Reproducible verification commands.
The required Architectural Status Summary.
Expected architectural result
Subsystem	Result
Operator presentation	External Sources screen removed
Navigation and help	Screen references removed
Governed-source registry	Complete and unchanged
HTTP APIs	Complete and unchanged
Persistence and data model	Complete and unchanged
Streams consumer	Complete and unchanged
Linux mailing-list consumers	Complete and unchanged
Replacement source-management UI	Not started; explicitly outside scope

The next architectural milestone is not determined by this subtractive presentation change.
