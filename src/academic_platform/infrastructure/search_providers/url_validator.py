"""URL safety validator for search source configuration.

Every user-supplied URL is validated before it is stored in the database
and again before a request is issued. The validator implements the
network safeguards required by the product specification:

- Only supported schemes are permitted. ``https`` is the default; ``http``
  is permitted only when the caller explicitly allows it for a specific
  source (a local development exception).
- URLs with embedded credentials (``user:pass@host``) are rejected.
- Requests to loopback, private, link-local, and cloud metadata
  addresses are rejected unless the caller explicitly allows loopback for
  a local source.
- The resolved address is revalidated to reduce DNS rebinding risk.

Design decisions
----------------
- The validator returns a structured result rather than raising on
  every failure. Callers decide whether a failure is fatal or advisory.
- The validator never performs a network request. It uses the operating
  system resolver through ``socket.getaddrinfo``; the resolution is
  synchronous and is performed only when the caller asks for it.
- The list of blocked address ranges is defined explicitly rather than
  derived, so that adding a new range is a deliberate act.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlsplit

_SUPPORTED_SCHEMES = ("https", "http")
_METADATA_ADDRESSES = (
    ipaddress.ip_network("169.254.169.254/32"),  # AWS, Azure, GCP
    ipaddress.ip_network("100.100.100.200/32"),  # Alibaba Cloud
    ipaddress.ip_network("fd00:ec2::254/128"),  # AWS IPv6 metadata
)


class UrlRejection(str, Enum):
    """Reason a URL was rejected."""

    EMPTY = "empty"
    MISSING_SCHEME = "missing_scheme"
    UNSUPPORTED_SCHEME = "unsupported_scheme"
    EMBEDDED_CREDENTIALS = "embedded_credentials"
    MISSING_HOST = "missing_host"
    INVALID_HOST = "invalid_host"
    LOOPBACK_NOT_ALLOWED = "loopback_not_allowed"
    PRIVATE_ADDRESS = "private_address"
    LINK_LOCAL_ADDRESS = "link_local_address"
    METADATA_ADDRESS = "metadata_address"
    RESOLUTION_FAILED = "resolution_failed"
    UNRESOLVED_HOST = "unresolved_host"


@dataclass(frozen=True, slots=True)
class UrlValidationResult:
    """Result of validating a URL."""

    url: str
    ok: bool
    rejection: UrlRejection | None = None
    message: str = ""
    host: str = ""
    scheme: str = ""
    resolved_addresses: tuple[str, ...] = ()

    @property
    def is_loopback(self) -> bool:
        """Return True when the URL resolves to a loopback address."""
        return any(
            ipaddress.ip_address(address).is_loopback
            for address in self.resolved_addresses
        )


def _is_ip_literal(
    host: str,
) -> tuple[bool, ipaddress.IPv4Address | ipaddress.IPv6Address | None]:
    try:
        return True, ipaddress.ip_address(host)
    except ValueError:
        return False, None


def _classify_ip(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> UrlRejection | None:
    for metadata_network in _METADATA_ADDRESSES:
        if address in metadata_network:
            return UrlRejection.METADATA_ADDRESS
    # Order matters: link-local is a subset of what ``is_private`` reports
    # for IPv4 (169.254.0.0/16), and loopback is a subset too. The most
    # specific rejection is returned first.
    if address.is_link_local:
        return UrlRejection.LINK_LOCAL_ADDRESS
    if address.is_loopback:
        return UrlRejection.LOOPBACK_NOT_ALLOWED
    if address.is_private:
        return UrlRejection.PRIVATE_ADDRESS
    return None


def _resolve_host(
    host: str, port: int | None
) -> tuple[list[str], UrlRejection | None]:
    try:
        results = socket.getaddrinfo(
            host,
            port or 0,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror:
        return [], UrlRejection.RESOLUTION_FAILED
    addresses: list[str] = []
    for family, _socktype, _proto, _canonname, sockaddr in results:
        if family == socket.AF_INET:
            addresses.append(sockaddr[0])
        elif family == socket.AF_INET6:
            addresses.append(sockaddr[0])
    if not addresses:
        return [], UrlRejection.UNRESOLVED_HOST
    return addresses, None


def validate_url(
    url: str,
    *,
    allow_http: bool = False,
    allow_loopback: bool = False,
    resolve_host: bool = True,
) -> UrlValidationResult:
    """Validate a URL against the application's network safeguards.

    Parameters
    ----------
    url:
        The URL to validate.
    allow_http:
        When True, ``http`` is permitted in addition to ``https``. Used
        only for a specific source, never as a global policy.
    allow_loopback:
        When True, loopback addresses are permitted. Used only for a
        local source that the user explicitly configured.
    resolve_host:
        When True, the host is resolved and the resulting addresses are
        revalidated. When False, only the syntactic checks are performed.

    Returns
    -------
    UrlValidationResult
        The outcome. ``ok`` is True when the URL passes every check.
    """
    if not url or not url.strip():
        return UrlValidationResult(
            url=url,
            ok=False,
            rejection=UrlRejection.EMPTY,
            message="URL is empty",
        )
    stripped = url.strip()
    parts = urlsplit(stripped)
    if not parts.scheme:
        return UrlValidationResult(
            url=stripped,
            ok=False,
            rejection=UrlRejection.MISSING_SCHEME,
            message="URL must include a scheme (https://)",
        )
    scheme = parts.scheme.lower()
    if scheme not in _SUPPORTED_SCHEMES:
        return UrlValidationResult(
            url=stripped,
            ok=False,
            rejection=UrlRejection.UNSUPPORTED_SCHEME,
            message=f"Scheme {scheme!r} is not supported",
            scheme=scheme,
        )
    if scheme == "http" and not allow_http:
        return UrlValidationResult(
            url=stripped,
            ok=False,
            rejection=UrlRejection.UNSUPPORTED_SCHEME,
            message=(
                "HTTP is not permitted. Use HTTPS, or explicitly allow HTTP "
                "for this specific source."
            ),
            scheme=scheme,
        )
    if parts.username or parts.password:
        return UrlValidationResult(
            url=stripped,
            ok=False,
            rejection=UrlRejection.EMBEDDED_CREDENTIALS,
            message="Credentials embedded in URLs are not permitted",
            scheme=scheme,
        )
    host = parts.hostname or ""
    if not host:
        return UrlValidationResult(
            url=stripped,
            ok=False,
            rejection=UrlRejection.MISSING_HOST,
            message="URL must include a host",
            scheme=scheme,
        )

    is_ip, ip = _is_ip_literal(host)
    if is_ip and ip is not None:
        rejection = _classify_ip(ip)
        if rejection is UrlRejection.LOOPBACK_NOT_ALLOWED and allow_loopback:
            rejection = None
        if rejection is not None:
            return UrlValidationResult(
                url=stripped,
                ok=False,
                rejection=rejection,
                message=_rejection_message(rejection),
                scheme=scheme,
                host=host,
                resolved_addresses=(str(ip),),
            )
        return UrlValidationResult(
            url=stripped,
            ok=True,
            scheme=scheme,
            host=host,
            resolved_addresses=(str(ip),),
        )

    if not resolve_host:
        return UrlValidationResult(
            url=stripped,
            ok=True,
            scheme=scheme,
            host=host,
        )

    port = parts.port
    addresses, resolution_error = _resolve_host(host, port)
    if resolution_error is not None:
        return UrlValidationResult(
            url=stripped,
            ok=False,
            rejection=resolution_error,
            message=_rejection_message(resolution_error),
            scheme=scheme,
            host=host,
        )

    for address_str in addresses:
        try:
            address = ipaddress.ip_address(address_str)
        except ValueError:
            continue
        rejection = _classify_ip(address)
        if rejection is UrlRejection.LOOPBACK_NOT_ALLOWED and allow_loopback:
            continue
        if rejection is not None:
            return UrlValidationResult(
                url=stripped,
                ok=False,
                rejection=rejection,
                message=_rejection_message(rejection),
                scheme=scheme,
                host=host,
                resolved_addresses=tuple(addresses),
            )
    return UrlValidationResult(
        url=stripped,
        ok=True,
        scheme=scheme,
        host=host,
        resolved_addresses=tuple(addresses),
    )


def _rejection_message(rejection: UrlRejection) -> str:
    mapping = {
        UrlRejection.EMPTY: "URL is empty",
        UrlRejection.MISSING_SCHEME: "URL must include a scheme (https://)",
        UrlRejection.UNSUPPORTED_SCHEME: "Scheme is not supported",
        UrlRejection.EMBEDDED_CREDENTIALS: (
            "Credentials embedded in URLs are not permitted"
        ),
        UrlRejection.MISSING_HOST: "URL must include a host",
        UrlRejection.INVALID_HOST: "URL host is not valid",
        UrlRejection.LOOPBACK_NOT_ALLOWED: (
            "Loopback addresses are not permitted for this source"
        ),
        UrlRejection.PRIVATE_ADDRESS: (
            "Private addresses are not permitted"
        ),
        UrlRejection.LINK_LOCAL_ADDRESS: (
            "Link-local addresses are not permitted"
        ),
        UrlRejection.METADATA_ADDRESS: (
            "Cloud metadata addresses are not permitted"
        ),
        UrlRejection.RESOLUTION_FAILED: (
            "The host could not be resolved"
        ),
        UrlRejection.UNRESOLVED_HOST: (
            "The host did not resolve to any address"
        ),
    }
    return mapping.get(rejection, "URL is not valid")