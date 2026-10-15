"""Synchronous HTTP client with safety guarantees.

The client wraps ``httpx.Client`` and adds:

- Timeout enforcement (connect, read, write, pool).
- Bounded retries with exponential backoff on transient failures.
- A host-scoped token-bucket rate limiter.
- Response size limits enforced before the body is fully read.
- Content-type enforcement.
- Redirect revalidation through the URL safety validator.
- Optional credential injection through request headers.
- Structured logging that never logs credentials.

Design decisions
----------------
- The client is synchronous. Adapters that need to run on a worker
  thread are scheduled by the orchestration layer, not by the client.
- The client is safe to share across threads. The underlying
  ``httpx.Client`` is thread-safe; the rate limiter is protected by a
  lock.
- The client revalidates the URL and the resolved destination for every
  request. This is deliberately redundant with the source-level
  validation performed before a source is stored: a URL that passed
  validation when it was saved can later resolve to a different address.
- Credentials are injected as headers. They are never written to logs,
  never included in exception messages, and never echoed in
  diagnostics.
- The client never retries non-idempotent methods. Retries are limited
  to GET and HEAD requests with transient status codes (429, 502, 503,
  504) or transport-level failures.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from academic_platform.infrastructure.http.config import HttpClientConfig
from academic_platform.infrastructure.http.errors import (
    HttpClientConfigurationError,
    HttpClientNetworkError,
    HttpClientRateLimitError,
    HttpClientResponseError,
    HttpClientSizeLimitError,
    HttpClientTimeoutError,
)
from academic_platform.infrastructure.http.rate_limit import RateLimiter
from academic_platform.infrastructure.http.response import HttpResponse
from academic_platform.infrastructure.search_providers.url_validator import (
    validate_url,
)

_logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = frozenset({429, 502, 503, 504})
_RETRYABLE_METHODS = frozenset({"GET", "HEAD"})


class HttpClient:
    """A synchronous HTTP client for search provider adapters."""

    def __init__(
        self,
        config: HttpClientConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = config
        try:
            self._client = httpx.Client(
                timeout=httpx.Timeout(
                    connect=config.connect_timeout_seconds,
                    read=config.read_timeout_seconds,
                    write=config.write_timeout_seconds,
                    pool=config.pool_timeout_seconds,
                ),
                follow_redirects=False,
                verify=config.verify_tls,
                transport=transport,
                headers=self._base_headers(config),
            )
        except Exception as exc:  # noqa: BLE001 - boundary
            raise HttpClientConfigurationError(
                f"Unable to construct HTTP client: {exc}"
            ) from exc
        self._rate_limiter = RateLimiter(
            rate_per_second=config.rate_limit_per_second,
            burst=config.rate_limit_burst,
        )
        self._closed = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._closed:
            return
        try:
            self._client.close()
        finally:
            self._closed = True

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def config(self) -> HttpClientConfig:
        return self._config

    # ------------------------------------------------------------------
    # Request API
    # ------------------------------------------------------------------
    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        json: Any | None = None,
        data: Any | None = None,
    ) -> HttpResponse:
        """Issue a request and return a normalized response.

        Parameters
        ----------
        method:
            HTTP method. Case-insensitive.
        url:
            Absolute URL. Relative URLs are not accepted; adapters
            combine the base URL and the endpoint themselves.
        params, headers, json, data:
            Request parameters. ``params`` and ``headers`` are merged with
            the client's defaults; ``json`` and ``data`` are mutually
            exclusive.
        """
        if json is not None and data is not None:
            raise HttpClientConfigurationError(
                "json and data are mutually exclusive"
            )
        upper_method = method.upper()
        self._validate_destination(url)

        attempt = 0
        backoff = self._config.backoff_initial_seconds
        last_error: Exception | None = None
        while attempt <= self._config.max_retries:
            attempt += 1
            if not self._rate_limiter.acquire(
                timeout_seconds=max(1.0, self._config.read_timeout_seconds)
            ):
                retry_after = self._rate_limiter.retry_after_seconds()
                raise HttpClientRateLimitError(
                    f"Local rate limit exhausted for {self._config.host}",
                    retry_after_seconds=retry_after,
                )
            try:
                response = self._single_request(
                    upper_method,
                    url,
                    params=params,
                    headers=headers,
                    json=json,
                    data=data,
                )
            except httpx.TimeoutException as exc:
                last_error = HttpClientTimeoutError(
                    f"Request timed out: {exc.__class__.__name__}"
                )
                if upper_method not in _RETRYABLE_METHODS or attempt > self._config.max_retries:
                    raise last_error from exc
            except httpx.TransportError as exc:
                last_error = HttpClientNetworkError(
                    f"Network error: {exc.__class__.__name__}"
                )
                if upper_method not in _RETRYABLE_METHODS or attempt > self._config.max_retries:
                    raise last_error from exc
            else:
                if (
                    response.status_code in _RETRYABLE_STATUS_CODES
                    and upper_method in _RETRYABLE_METHODS
                    and attempt <= self._config.max_retries
                ):
                    last_error = HttpClientResponseError(
                        f"Transient status {response.status_code}"
                    )
                else:
                    return response

            if attempt > self._config.max_retries:
                break
            sleep_for = min(backoff, self._config.backoff_max_seconds)
            _logger.debug(
                "Retrying HTTP request (attempt %d, sleeping %.2fs)",
                attempt,
                sleep_for,
            )
            time.sleep(sleep_for)
            backoff = min(backoff * 2, self._config.backoff_max_seconds)

        if last_error is not None:
            raise last_error
        raise HttpClientNetworkError("Request failed without a specific error")

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        """Issue a GET request."""
        return self.request("GET", url, params=params, headers=headers)

    def post(
        self,
        url: str,
        *,
        json: Any | None = None,
        data: Any | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        """Issue a POST request."""
        return self.request(
            "POST", url, params=params, headers=headers, json=json, data=data
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _base_headers(self, config: HttpClientConfig) -> dict[str, str]:
        headers = {
            "User-Agent": config.user_agent,
            "Accept": config.accept,
        }
        for name, value in config.default_headers:
            headers[name] = value
        if config.bearer_token:
            headers["Authorization"] = f"Bearer {config.bearer_token}"
        if config.api_key:
            headers[config.api_key_header] = config.api_key
        return headers

    def _validate_destination(self, url: str) -> None:
        if not self._config.validate_destination:
            return
        result = validate_url(
            url,
            allow_http=self._config.allow_http,
            allow_loopback=self._config.allow_loopback,
            resolve_host=True,
        )
        if not result.ok:
            raise HttpClientConfigurationError(
                f"Destination rejected: {result.message} ({url})"
            )

    def _single_request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None,
        headers: dict[str, str] | None,
        json: Any | None,
        data: Any | None,
    ) -> HttpResponse:
        started = time.monotonic()
        with self._client.stream(
            method,
            url,
            params=params,
            headers=headers,
            json=json,
            data=data,
        ) as response:
            self._enforce_redirect_limit(response)
            self._enforce_content_type(response)
            body = self._read_bounded(response)
            headers_tuple = tuple(
                (name, value) for name, value in response.headers.multi_items()
            )
            elapsed_ms = int((time.monotonic() - started) * 1000)
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise HttpClientResponseError(
                        f"Redirect without Location header from {url}"
                    )
                absolute = str(httpx.URL(url).join(httpx.URL(location)))
                self._validate_destination(absolute)
                raise HttpClientResponseError(
                    f"Redirects are not followed automatically; destination: {absolute}"
                )
            if response.status_code >= 400:
                # Status codes in the retryable set are handled by the
                # caller; other error codes are raised here.
                if response.status_code not in _RETRYABLE_STATUS_CODES:
                    raise HttpClientResponseError(
                        f"Unexpected status {response.status_code} from {url}"
                    )
            return HttpResponse(
                status_code=response.status_code,
                headers=headers_tuple,
                content=body,
                url=str(response.url),
                elapsed_ms=elapsed_ms,
            )

    def _enforce_redirect_limit(self, response: httpx.Response) -> None:
        # httpx with follow_redirects=False does not follow redirects, so
        # the limit is enforced by rejecting redirect responses outright.
        # The check below is retained so that adapters that enable manual
        # redirect handling elsewhere still observe the limit.
        if response.history and len(response.history) > self._config.max_redirects:
            raise HttpClientResponseError(
                "Too many redirects; aborting request"
            )

    def _enforce_content_type(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            return
        content_type = response.headers.get("content-type", "")
        normalized = content_type.split(";", 1)[0].strip().lower()
        if not normalized:
            # Some providers omit the content type; treat as acceptable
            # and let the adapter validate the body shape.
            return
        if normalized not in self._config.allowed_content_types:
            raise HttpClientResponseError(
                f"Unsupported content type {normalized!r}"
            )

    def _read_bounded(self, response: httpx.Response) -> bytes:
        max_bytes = self._config.max_response_bytes
        buffer = bytearray()
        for chunk in response.iter_bytes():
            if not chunk:
                continue
            buffer.extend(chunk)
            if len(buffer) > max_bytes:
                raise HttpClientSizeLimitError(
                    f"Response body exceeded {max_bytes} bytes"
                )
        return bytes(buffer)