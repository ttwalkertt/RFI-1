# RBF reset end-to-end proof

Authoritative executable evidence: `tests/test_task038.py`, especially
`test_reset_import_restores_configuration_only_and_can_start_acquisition` and
`test_cli_export_init_import_operator_workflow`.

The fixture proof performs this sequence:

1. Initializes a populated source state with current schema.
2. Creates the Seagate firm and a complete firm-owned source profile.
3. Configures the Linux Block Layer Lore source, including transport policy.
4. Persists verified SEC source identity.
5. Saves the enabled `linux-block-storage` stream and its selection/expansion policies.
6. Acquires fixture-backed Linux Block Layer messages and executes the stream, ensuring the source
   contains real evidence and derived operational state before export.
7. Exports deterministic `rfi-config` version 1 YAML.
8. Initializes a fresh current-schema target and imports the YAML without copying SQLite or the
   content store.
9. Confirms the fresh target exports semantically identical configuration.
10. Confirms repeat import creates zero rows in every supported configuration category.
11. Starts a fixture-backed Linux Block Layer acquisition preview from restored configuration and
    discovers the requested seed without manual reconstruction.

The CLI proof separately invokes the exact operator workflow:

```text
rfi config --state POPULATED export --output rfi-config.yaml
rfi init --state FRESH
rfi config --state FRESH import --file rfi-config.yaml
```

The focused validation log records both tests passing.
