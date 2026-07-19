# TASK-023 Linux block-layer fixtures

These lossless RFC 5322 messages form one finite Lore/public-inbox-compatible test archive.
They include an ancestor outside the discovery window, a branching reply tree, a missing
connector, a cycle, and malformed external identity. Tests construct alternate bytes for one
Message-ID to prove conflict rejection without changing these canonical fixtures.
