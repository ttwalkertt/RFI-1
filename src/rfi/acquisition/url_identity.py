"""Shared conservative URL identity for discovery graph and retained anchors."""

from __future__ import annotations

import posixpath
import urllib.parse


def normalize_discovery_url(url: str) -> str:
    """Normalize graph identity without replacing exact requested/resolved provenance."""
    parsed = urllib.parse.urlsplit(url)
    scheme = parsed.scheme.casefold()
    host = (parsed.hostname or "").casefold()
    if scheme not in {"http", "https"} or not host:
        raise ValueError("discovery URL must be an absolute HTTP(S) URL")
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("discovery URL has an invalid port") from error
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    authority = host if port is None or default_port else f"{host}:{port}"
    path = parsed.path or "/"
    trailing_slash = path.endswith("/")
    path = posixpath.normpath(path)
    if not path.startswith("/"):
        path = "/" + path
    if trailing_slash and path != "/":
        path += "/"
    return urllib.parse.urlunsplit((scheme, authority, path, parsed.query, ""))
