"""Normalized HTTP response value object.

The HTTP client normalizes every response into an ``HttpResponse``
instance so that adapters do not depend on the underlying HTTP library's
response type.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """A normalized HTTP response."""

    status_code: int
    headers: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    content: bytes = b""
    url: str = ""
    elapsed_ms: int | None = None

    @property
    def is_success(self) -> bool:
        """Return True when the status code is in the 2xx range."""
        return 200 <= self.status_code < 300

    @property
    def is_redirect(self) -> bool:
        """Return True when the status code is a redirect."""
        return self.status_code in {301, 302, 303, 307, 308}

    @property
    def is_client_error(self) -> bool:
        """Return True when the status code is in the 4xx range."""
        return 400 <= self.status_code < 500

    @property
    def is_server_error(self) -> bool:
        """Return True when the status code is in the 5xx range."""
        return 500 <= self.status_code < 600

    @property
    def content_type(self) -> str:
        """Return the response content type without parameters.

        The value is lowercased and trimmed of any parameters after the
        semicolon. Missing content type yields an empty string.
        """
        for name, value in self.headers:
            if name.lower() == "content-type":
                return value.split(";", 1)[0].strip().lower()
        return ""

    def header(self, name: str, default: str | None = None) -> str | None:
        """Return the first header value whose name matches (case-insensitive)."""
        needle = name.lower()
        for header_name, header_value in self.headers:
            if header_name.lower() == needle:
                return header_value
        return default

    @property
    def text(self) -> str:
        """Decode the body as UTF-8, replacing undecodable bytes."""
        return self.content.decode("utf-8", errors="replace")

    @property
    def size_bytes(self) -> int:
        """Return the size of the response body in bytes."""
        return len(self.content)