#!/usr/bin/env python3
"""Retry one repaired mailing-list workflow against an explicit copied state."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from rfi.mailing_lists import (
    LinuxMailingListWorkflowService,
    LoreArchive,
    MailingListQueryService,
    MailingListRepository,
    MailingListSourceService,
)
from rfi.storage import RepositoryDatabase
from rfi.streams import StreamRepository, StreamService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-copy", required=True, type=Path)
    parser.add_argument("--stream-id", required=True)
    arguments = parser.parse_args()
    state = arguments.state_copy.resolve()
    RepositoryDatabase.open(state)
    repository = MailingListRepository(state)
    workflow = LinuxMailingListWorkflowService(
        repository,
        MailingListSourceService(repository),
        StreamService(StreamRepository(state)),
        MailingListQueryService(repository),
        archive_factory=LoreArchive,
    )
    result = workflow.fetch_up_to_date(arguments.stream_id)
    print(json.dumps({
        "fetch": asdict(result),
        "validation": RepositoryDatabase.open(state).validate(),
    }, indent=2, sort_keys=True))
    return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
