"""Shared HTTP client infrastructure.

This subpackage owns the HTTP client used by every search provider
adapter and, later, by the AI provider adapters. It provides:

- ``HttpClientConfig`` — immutable configuration for a client instance.
- ``HttpClient`` — a synchronous HTTP client with retries, rate limits,
  response size limits, content-type enforcement, and redirect
  revalidation.
- ``HttpResponse`` — a normalized response object.
- ``RateLimiter`` — a simple token-bucket rate limiter scoped to a
  single host.
- ``HttpClientFactory`` — constructs clients from a search source's
  configuration.
- Typed exceptions in ``errors``.

The subpackage never imports Qt. It may import from ``httpx`` and from
the URL safety validator.
"""

from academic_platform.infrastructure.http.client import HttpClient
from academic_platform.infrastructure.http.config import HttpClientConfig
from academic_platform.infrastructure.http.errors import (
    HttpClientConfigurationError,
    HttpClientError,
    HttpClientNetworkError,
    HttpClientRateLimitError,
    HttpClientResponseError,
    HttpClientSizeLimitError,
    HttpClientTimeoutError,
)
from academic_platform.infrastructure.http.factory import HttpClientFactory
from academic_platform.infrastructure.http.rate_limit import RateLimiter
from academic_platform.infrastructure.http.response import HttpResponse

__all__ = [
    "HttpClient",
    "HttpClientConfig",
    "HttpClientConfigurationError",
    "HttpClientError",
    "HttpClientFactory",
    "HttpClientNetworkError",
    "HttpClientRateLimitError",
    "HttpClientResponseError",
    "HttpClientSizeLimitError",
    "HttpClientTimeoutError",
    "HttpResponse",
    "RateLimiter",
]