"""Typed exceptions for the search provider subsystem.

Concrete adapters raise only these exceptions outward. HTTP library
exceptions, JSON parsing exceptions, and provider-specific error codes
are caught at the adapter boundary and translated so that callers do not
depend on the transport.
"""

from __future__ import annotations


class ProviderError(RuntimeError):
    """Base class for search provider failures."""


class ProviderConfigurationError(ProviderError):
    """Raised when a provider is misconfigured or cannot be initialized."""


class ProviderRequestError(ProviderError):
    """Raised when a request cannot be issued.

    Covers network failures, timeouts, and invalid request parameters
    detected before the response is received.
    """


class ProviderResponseError(ProviderError):
    """Raised when a response cannot be interpreted.

    Covers malformed JSON, unexpected schemas, and responses that violate
    the provider's documented contract.
    """


class ProviderUnavailableError(ProviderError):
    """Raised when the provider is temporarily unavailable.

    Covers rate limits, service outages, and authentication failures that
    may be resolved by retrying later. Adapters raise this instead of a
    generic request error so that the orchestration layer can decide
    whether to retry or to report the failure to the user.
    """