# Fixtures

Checked-in deterministic fixtures used by tests belong here. `fixtures/acquisition/` contains
synthetic TASK-002 substrate inputs plus TASK-003 catalog/feed scenarios and exact content bytes.
The TASK-003 adapters read these files through production discovery and retrieval contracts; no
fixture directly seeds repository state. This is not a downloaded evidence corpus.

Machine-local or downloaded fixtures belong under `fixtures/local/` and are ignored.
