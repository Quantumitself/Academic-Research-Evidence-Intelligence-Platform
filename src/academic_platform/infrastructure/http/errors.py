"""Typed exceptions for the HTTP client subsystem.

Concrete adapters catch these exceptions and translate them into the
provider-layer error hierarchy (``ProviderRequestError``,
``ProviderUnavailableError``, and so on). The HTTP client itself never
raises provider-layer exceptions; the two layers remain independent.
"""

from __future__ import annotations


class HttpClientError(RuntimeError):
    """Base class for HTTP client failures."""


class HttpClientConfigurationError(HttpClientError):
    """Raised when a client is misconfigured or cannot be initialized."""


class HttpClientTimeoutError(HttpClientError):
    """Raised when a request exceeds its configured timeout."""


class HttpClientNetworkError(HttpClientError):
    """Raised when a request cannot be completed due to a network failure."""


class HttpClientResponseError(HttpClientError):
    """Raised when a response is not acceptable.

    Covers non-2xx status codes, unexpected content types, and bodies
    that violate the configured size limit.
    """


class HttpClientSizeLimitError(HttpClientResponseError):
    """Raised when a response body exceeds the configured size limit."""


class HttpClientRateLimitError(HttpClientError):
    """Raised when the client's local rate limiter refuses to issue a request."""

    def __init__(self, message: str, *, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds