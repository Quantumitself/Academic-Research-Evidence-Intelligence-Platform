"""Immutable configuration for an HTTP client instance.

Every search source produces its own client configuration from its
persisted settings. The configuration is frozen so that it can be shared
safely across threads and so that a client cannot be silently mutated
after construction.

Design decisions
----------------
- Timeouts are split into connect, read, and write components. A single
  timeout value would conflate slow name resolution with a slow response
  body, and the two have different operational significance.
- The retry policy is explicit. Automatic retries are limited to
  idempotent methods and to status codes that indicate transient
  failures.
- The default user agent identifies the application. Search providers
  frequently require a descriptive user agent; a generic default would
  cause avoidable rejections.
- Response size limits and content-type allow-lists default to safe
  values. Adapters that need a narrower or wider policy override them
  explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit

from academic_platform.infrastructure.http.errors import (
    HttpClientConfigurationError,
)

_DEFAULT_USER_AGENT = (
    "AcademicResearchPlatform/0.3 (+https://example.invalid/academic-platform)"
)

_DEFAULT_ACCEPT = "application/json, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5"

_SUPPORTED_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})


@dataclass(frozen=True, slots=True)
class HttpClientConfig:
    """Immutable HTTP client configuration."""

    base_url: str
    connect_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 30.0
    write_timeout_seconds: float = 30.0
    pool_timeout_seconds: float = 5.0
    max_retries: int = 2
    backoff_initial_seconds: float = 0.5
    backoff_max_seconds: float = 8.0
    max_response_bytes: int = 8 * 1024 * 1024
    allowed_content_types: tuple[str, ...] = (
        "application/json",
        "application/xml",
        "text/xml",
        "text/plain",
        "text/html",
    )
    max_redirects: int = 3
    allow_http: bool = False
    allow_loopback: bool = False
    rate_limit_per_second: float = 5.0
    rate_limit_burst: int = 10
    user_agent: str = _DEFAULT_USER_AGENT
    accept: str = _DEFAULT_ACCEPT
    default_headers: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    verify_tls: bool = True
    #: An optional bearer token. When set, the client injects an
    #: ``Authorization: Bearer <token>`` header on every request. The
    #: token is never logged.
    bearer_token: str | None = None
    #: An optional API key. When set, the client injects the header named
    #: by ``api_key_header`` on every request. The key is never logged.
    api_key: str | None = None
    api_key_header: str = "X-API-Key"
    #: When True, the client revalidates every destination through the URL
    #: safety validator before issuing a request. Tests that use a mock
    #: transport disable this flag because the mock transport never touches
    #: the network and the test host is deliberately unresolvable.
    validate_destination: bool = True

    def __post_init__(self) -> None:
        if not self.base_url:
            raise HttpClientConfigurationError("base_url must not be empty")
        if self.connect_timeout_seconds <= 0:
            raise HttpClientConfigurationError("connect_timeout_seconds must be positive")
        if self.read_timeout_seconds <= 0:
            raise HttpClientConfigurationError("read_timeout_seconds must be positive")
        if self.write_timeout_seconds <= 0:
            raise HttpClientConfigurationError("write_timeout_seconds must be positive")
        if self.pool_timeout_seconds <= 0:
            raise HttpClientConfigurationError("pool_timeout_seconds must be positive")
        if self.max_retries < 0:
            raise HttpClientConfigurationError("max_retries must not be negative")
        if self.backoff_initial_seconds <= 0:
            raise HttpClientConfigurationError("backoff_initial_seconds must be positive")
        if self.backoff_max_seconds < self.backoff_initial_seconds:
            raise HttpClientConfigurationError(
                "backoff_max_seconds must be at least backoff_initial_seconds"
            )
        if self.max_response_bytes <= 0:
            raise HttpClientConfigurationError("max_response_bytes must be positive")
        if self.max_redirects < 0:
            raise HttpClientConfigurationError("max_redirects must not be negative")
        if self.rate_limit_per_second <= 0:
            raise HttpClientConfigurationError("rate_limit_per_second must be positive")
        if self.rate_limit_burst < 1:
            raise HttpClientConfigurationError("rate_limit_burst must be at least 1")
        if not self.allowed_content_types:
            raise HttpClientConfigurationError(
                "allowed_content_types must not be empty"
            )
        if not self.user_agent.strip():
            raise HttpClientConfigurationError("user_agent must not be empty")

    @property
    def host(self) -> str:
        """Return the hostname derived from ``base_url``."""
        return urlsplit(self.base_url).hostname or ""

    @property
    def scheme(self) -> str:
        """Return the scheme derived from ``base_url``."""
        return urlsplit(self.base_url).scheme.lower()

    def with_overrides(self, **overrides) -> "HttpClientConfig":
        """Return a copy with the given fields replaced."""
        data = {
            "base_url": self.base_url,
            "connect_timeout_seconds": self.connect_timeout_seconds,
            "read_timeout_seconds": self.read_timeout_seconds,
            "write_timeout_seconds": self.write_timeout_seconds,
            "pool_timeout_seconds": self.pool_timeout_seconds,
            "max_retries": self.max_retries,
            "backoff_initial_seconds": self.backoff_initial_seconds,
            "backoff_max_seconds": self.backoff_max_seconds,
            "max_response_bytes": self.max_response_bytes,
            "allowed_content_types": self.allowed_content_types,
            "max_redirects": self.max_redirects,
            "allow_http": self.allow_http,
            "allow_loopback": self.allow_loopback,
            "rate_limit_per_second": self.rate_limit_per_second,
            "rate_limit_burst": self.rate_limit_burst,
            "user_agent": self.user_agent,
            "accept": self.accept,
            "default_headers": self.default_headers,
            "verify_tls": self.verify_tls,
            "bearer_token": self.bearer_token,
            "api_key": self.api_key,
            "api_key_header": self.api_key_header,
            "validate_destination": self.validate_destination,
        }
        data.update(overrides)
        return HttpClientConfig(**data)