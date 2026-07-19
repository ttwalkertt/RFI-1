"""SQLite structured-state and hybrid repository operations."""

from rfi.storage.sqlite import (
    DATABASE_NAME,
    SCHEMA_VERSION,
    RepositoryDatabase,
    StorageError,
    state_root_for,
)
from rfi.storage.backup import create_backup, restore_backup

__all__ = [
    "DATABASE_NAME",
    "SCHEMA_VERSION",
    "RepositoryDatabase",
    "StorageError",
    "state_root_for",
    "create_backup",
    "restore_backup",
]
