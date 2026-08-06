"""Bounded public HTTP transport shared by feed validation and polling."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from rfi.feeds.contracts import FeedError


@dataclass(frozen=True)
class HttpResponse:
    content: bytes
    media_type: str
    final_url: str
    status: int


class FeedHttpTransport:
    """Retrieve bounded HTTP(S) bytes without retaining credentials or payload diagnostics."""

    def __init__(self, timeout_seconds: float = 20.0, maximum_bytes: int = 10_000_000) -> None:
        self.timeout_seconds = timeout_seconds
        self.maximum_bytes = maximum_bytes

    def fetch(self, url: str) -> HttpResponse:
        validate_public_url(url)
        try:
            response = urlopen(
                Request(url, headers={"User-Agent": "RFI-1 Feed Acquisition"}),
                timeout=self.timeout_seconds,
            )
            with response:
                validate_public_url(response.geturl())
                content = response.read(self.maximum_bytes + 1)
                if len(content) > self.maximum_bytes:
                    raise FeedError(f"response exceeds {self.maximum_bytes} bytes")
                return HttpResponse(
                    content,
                    response.headers.get_content_type() or "application/octet-stream",
                    response.geturl(),
                    int(getattr(response, "status", 200)),
                )
        except HTTPError as error:
            raise FeedError(f"HTTP {error.code}") from error
        except (URLError, TimeoutError, OSError) as error:
            reason = error.reason if isinstance(error, URLError) else error
            raise FeedError(f"retrieval failed: {reason}") from error


def validate_public_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise FeedError("URL must be an absolute HTTP or HTTPS URL")
    if parsed.username or parsed.password:
        raise FeedError("URL credentials are not permitted")
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".localhost"):
        raise FeedError("local network URLs are not permitted")
    try:
        address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return
    if not address.is_global:
        raise FeedError("private, loopback, and link-local URLs are not permitted")
