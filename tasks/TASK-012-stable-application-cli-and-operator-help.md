# TASK-012 — Stable Application CLI and Operator Help

## Status

Ready

## Purpose

Replace task-specific invocation commands with a stable RFI-1 application entry point so the admin console can be run repeatedly for focused operator feedback without requiring knowledge of implementation-history scripts.

This task is operational cleanup, not a redesign of the console, concept catalog, or firm catalog.

## Required Outcome

Provide a supported command-line entry point for routine local use.

The command should make the available operations discoverable through built-in help and should provide clear paths for:

- initializing local application state;
- explicitly seeding starter data;
- launching the admin console;
- selecting or displaying the state location;
- selecting the server host and port;
- stopping cleanly.

A normal operator should not need to invoke `scripts/task009_*`, `scripts/task010_*`, or `scripts/task011_*` to use the application.

## Command Design

Codex should choose a concise command hierarchy consistent with the repository’s packaging and CLI conventions.

The resulting interface should support interactions equivalent to:

```text
rfi --help
rfi admin --help
rfi init
rfi seed
rfi admin
```

The exact names may differ if a better structure fits the existing project, but the commands must be stable, understandable, and documented.

Both the installed command and an appropriate module invocation should reach the same implementation path where practical.

## Behavioral Requirements

### Help

Help output should:

- identify RFI-1 and the purpose of each command;
- describe initialization, seeding, and application startup;
- show important options and defaults;
- include concise examples;
- distinguish run-once operations from normal startup.

### Initialization and Seeding

Initialization and seeding must remain explicit.

Launching the admin console must not silently insert demonstration or starter records.

Repeated initialization or seeding should behave safely and explain what changed, what already existed, or why the operation could not proceed.

### Admin Console Startup

The supported application command should launch the integrated admin console containing the concept and target-firm interfaces.

Startup output should clearly show:

- the local URL;
- the state location;
- how to stop the server;
- actionable errors when state is missing, incompatible, or inaccessible.

Preserve the existing public service and persistence boundaries.

### Compatibility

Task-specific scripts may remain for historical proofs or review tooling, but normal documentation and operator instructions should point to the stable application CLI.

Avoid duplicating application logic inside the new entry point. Reuse the existing initialization, seed, service, persistence, and server paths.

## Documentation

Update operator and development documentation with a short first-run workflow and a normal repeat-use workflow.

Example intent:

```text
First run:
1. initialize;
2. seed explicitly if desired;
3. launch the admin console.

Later runs:
1. launch the admin console.
```

Document how to discover additional options through `--help`.

## Validation

Demonstrate:

1. top-level help;
2. command-specific help;
3. initialization of a fresh state location;
4. explicit starter-data seeding;
5. safe repeated initialization and seeding;
6. integrated admin-console startup;
7. concept and target-firm data available through the launched application;
8. startup without implicit seeding;
9. clear failure behavior for invalid state or options;
10. parity between supported installed and module entry paths where provided.

Run the repository’s focused and full validation.

## Review Evidence

Include:

- command help output;
- first-run walkthrough;
- repeat-use walkthrough;
- fresh-state and already-initialized behavior;
- explicit-seeding proof;
- admin-console startup proof;
- validation results;
- changed-file inventory;
- known limitations.

## Non-Goals

This task does not require:

- redesigning the admin console;
- changing concept or firm schemas;
- adding authentication;
- deployment packaging;
- a background service or daemon;
- automatic browser launch;
- replacing deterministic task proof tools;
- adding new acquisition or intelligence capabilities.

## Completion Standard

TASK-012 is complete when RFI-1 has a documented, discoverable, stable application CLI that supports explicit initialization and seeding, launches the integrated admin console, and removes task-specific scripts from the routine operator workflow.
