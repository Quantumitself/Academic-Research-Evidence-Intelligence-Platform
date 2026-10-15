"""Factory that constructs HTTP clients from a search source configuration.

The factory bridges the application-layer ``SourceConfig`` and the
infrastructure-layer ``HttpClient``. It is the single place that decides
which HTTP client settings a source produces.

Design decisions
----------------
- The factory never stores credentials. It receives them from the caller
  (which reads them from the operating system keyring) and passes them
  to the client configuration. The client configuration holds them for
  the lifetime of the client and never writes them to disk.
- The factory applies the client's own safe defaults. A source that
  declares a per-source timeout overrides the default read timeout.
  A source that declares a rate limit overrides the default rate.
- The factory never resolves credentials from a reference. Credential
  resolution is the responsibility of the application layer; the factory
  expects to receive the resolved secret or None.
"""

from __future__ import annotations

import logging

from academic_platform.application.search_sources.source_config import SourceConfig
from academic_platform.infrastructure.http.client import HttpClient
from academic_platform.infrastructure.http.config import HttpClientConfig
from academic_platform.infrastructure.http.errors import HttpClientError

_logger = logging.getLogger(__name__)


class HttpClientFactory:
    """Construct HTTP clients from source configurations."""

    def __init__(
        self,
        *,
        allow_http: bool = False,
        allow_loopback: bool = False,
        default_user_agent: str | None = None,
    ) -> None:
        self._allow_http = allow_http
        self._allow_loopback = allow_loopback
        self._default_user_agent = default_user_agent

    def build(self, config: SourceConfig, *, secret: str | None = None) -> HttpClient:
        """Construct an HTTP client for the given source.

        Parameters
        ----------
        config:
            The source configuration.
        secret:
            The resolved credential, if any. The factory uses it to set
            the Authorization or API-key header. It is never persisted
            and never logged.
        """
        base_url = config.base_url
        overrides = {
            "base_url": base_url,
            "read_timeout_seconds": float(config.timeout_seconds),
            "write_timeout_seconds": float(config.timeout_seconds),
            "allow_http": self._allow_http,
            "allow_loopback": self._allow_loopback,
            "rate_limit_per_second": float(
                _rate_from_config(config.rate_limit) or 5.0
            ),
            "rate_limit_burst": int(
                _burst_from_config(config.rate_limit) or 10
            ),
        }
        if self._default_user_agent:
            overrides["user_agent"] = self._default_user_agent
        if secret and config.auth_type == "bearer_token":
            overrides["bearer_token"] = secret
        elif secret and config.auth_type == "api_key":
            overrides["api_key"] = secret
        try:
            base = HttpClientConfig(base_url=base_url)
            merged = base.with_overrides(**overrides)
            return HttpClient(merged)
        except HttpClientError:
            raise
        except Exception as exc:  # noqa: BLE001 - boundary
            raise HttpClientError(
                f"Unable to construct HTTP client for {config.key!r}: {exc}"
            ) from exc


def _rate_from_config(rate_config: dict | None) -> float | None:
    if not isinstance(rate_config, dict):
        return None
    value = rate_config.get("requests_per_second")
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    return None


def _burst_from_config(rate_config: dict | None) -> int | None:
    if not isinstance(rate_config, dict):
        return None
    value = rate_config.get("burst")
    if isinstance(value, int) and value > 0:
        return value
    return None