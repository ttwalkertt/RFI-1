# Runtime data boundary

This directory remains available for local fixtures and historical development state. Normal
application state is initialized at the operator-selected path (by default
`.artifacts/runtime/rfi-1`) as `repository.sqlite3` plus `content/`. Runtime contents are ignored by
Git. Tests and demonstrations use temporary directories so routine validation leaves this boundary
empty.

The public domain contract accepts the state-root path only. Physical object paths beneath it are
private implementation details and must not be persisted by callers.
