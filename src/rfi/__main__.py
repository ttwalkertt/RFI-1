"""Allow ``python -m rfi`` to use the stable application CLI."""

from rfi.cli import main

raise SystemExit(main())
