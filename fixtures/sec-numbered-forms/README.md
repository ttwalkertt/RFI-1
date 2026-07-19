# TASK-022 SEC numbered-form fixtures

`CIK0001137789.json` is a bounded SEC submissions-shaped fixture containing reordered base and
amended records for Form 10-Q, Form 8-K, Form 20-F, and Form 6-K. The primary-document fixture is
valid inert HTML. Tests exercise the production `SecProviderClient`, exact archive construction,
artifact-specific adapters, Pull Workflow, acquisition repository, SQLite-backed query service,
restart, integrity, and network-blocked inspection. No live request is made by ordinary tests.
