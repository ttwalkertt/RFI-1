# Runtime data boundary

This directory is available for local acquisition repository state. Its contents are ignored by
Git except for this boundary document. Tests and the demonstration use temporary directories so
routine validation leaves this boundary empty.

The public domain contract accepts the state-root path only. Physical object paths beneath it are
private implementation details and must not be persisted by callers.
