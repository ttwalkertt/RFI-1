#!/usr/bin/env python3
"""Run the bounded TASK-045 cross-source repair against an explicit state copy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rfi.mailing_lists import MailingListRepository
from rfi.storage import RepositoryDatabase


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-copy", required=True, type=Path)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--historical-run-id", required=True)
    arguments = parser.parse_args()
    state = arguments.state_copy.resolve()
    RepositoryDatabase.open(state)
    result = MailingListRepository(state).repair_cross_source_conflicts(
        arguments.source_id, historical_run_id=arguments.historical_run_id
    )
    result["validation"] = RepositoryDatabase.open(state).validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
