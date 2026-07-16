"""Strict local runtime configuration for explicitly live acquisition commands."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Mapping

from rfi.acquisition.contracts import ContractError

RUNTIME_CONFIG_PATH = Path(".rfi/runtime.env")
SUPPORTED_RUNTIME_VALUES = frozenset({"RFI_SEC_USER_AGENT", "SEC_API_IO_API_KEY"})
MAXIMUM_CONFIG_BYTES = 16 * 1024


def _read_private_file(path: Path) -> str:
    """Read a small regular file without following symlinks or accepting broad access."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ContractError("local runtime configuration could not be opened safely") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ContractError("local runtime configuration must be a regular file")
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise ContractError("local runtime configuration permissions must be 0600 or stricter")
        content = os.read(descriptor, MAXIMUM_CONFIG_BYTES + 1)
        if len(content) > MAXIMUM_CONFIG_BYTES:
            raise ContractError("local runtime configuration exceeds the size limit")
    finally:
        os.close(descriptor)
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ContractError("local runtime configuration must be UTF-8") from error


def _parse(content: str) -> dict[str, str]:
    """Parse literal KEY=value lines without interpolation, expansion, or logging."""
    values: dict[str, str] = {}
    for number, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in line:
            raise ContractError(f"invalid local runtime configuration line {number}")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key not in SUPPORTED_RUNTIME_VALUES:
            raise ContractError(f"unsupported local runtime configuration key on line {number}")
        if key in values:
            raise ContractError(f"duplicate local runtime configuration key on line {number}")
        if not value:
            raise ContractError(f"empty local runtime configuration value on line {number}")
        values[key] = value
    return values


def load_runtime_configuration(
    root: Path,
    environment: Mapping[str, str] | None = None,
    allow_local: bool = True,
) -> dict[str, str]:
    """Return supported runtime values, with the process environment taking precedence."""
    source = os.environ if environment is None else environment
    local: dict[str, str] = {}
    path = root / RUNTIME_CONFIG_PATH
    if allow_local and path.exists():
        local = _parse(_read_private_file(path))
    values = dict(local)
    for key in SUPPORTED_RUNTIME_VALUES:
        if key in source:
            values[key] = source[key]
    return values
