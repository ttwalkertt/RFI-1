# Fixtures

`streams/task025-topology.json` records the deterministic TASK-025 external, fan-out, and
multi-level stream configuration used by the verification proof. Linux message bytes remain in
`linux-block/`; non-mail SEC artifacts are created deterministically by the focused proof so the
same generic membership engine can be verified without provider access.

Checked-in deterministic fixtures used by tests belong here. `fixtures/acquisition/` contains
synthetic TASK-002 substrate inputs plus TASK-003 catalog/feed scenarios and exact content bytes.
The TASK-003 adapters read these files through production discovery and retrieval contracts; no
fixture directly seeds repository state. This is not a downloaded evidence corpus.

Machine-local or downloaded fixtures belong under `fixtures/local/` and are ignored.
