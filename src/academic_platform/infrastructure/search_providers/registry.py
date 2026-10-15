"""Provider registry.

The registry maps a provider key to its adapter class and, optionally, to
a pre-constructed instance. It is the single place the application looks
up a provider by key.

Design decisions
----------------
- The registry stores classes, not instances, so that adapters are
  constructed with the current configuration at the time of use.
- A provider may also be registered as an instance. This is used by the
  null adapter and by tests that need a fixed adapter.
- Registering a key that already exists replaces the previous entry.
  This is intentional: tests override entries for the duration of a test.
- The registry is a plain class, not a global. The module exposes a
  ``default_registry()`` helper that returns a process-wide registry.
  Tests construct their own registries and never mutate the default one
  unless they explicitly intend to.
- ``default_registry()`` is self-healing. Concrete providers are
  re-registered on every call so that a test which mutated the registry
  cannot break subsequent tests. Registration functions are idempotent,
  so re-invoking them is free.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from academic_platform.infrastructure.search_providers.adapter import (
    ProviderDescriptor,
    SearchProviderAdapter,
)
from academic_platform.infrastructure.search_providers.errors import (
    ProviderConfigurationError,
)
from academic_platform.infrastructure.search_providers.null_adapter import (
    NullSearchProviderAdapter,
)


AdapterFactory = Callable[[dict[str, Any]], SearchProviderAdapter]


# The set of built-in provider keys and the import path of the module
# that registers each one. The registry uses this table to restore
# providers that a test may have removed. Adding a new adapter requires
# extending this tuple.
_BUILTIN_PROVIDERS: tuple[tuple[str, str, str], ...] = (
    (
        "crossref",
        "academic_platform.infrastructure.search_providers.crossref.registration",
        "register_crossref",
    ),
    (
        "openalex",
        "academic_platform.infrastructure.search_providers.openalex.registration",
        "register_openalex",
    ),
    (
        "semantic_scholar",
        "academic_platform.infrastructure.search_providers.semantic_scholar.registration",
        "register_semantic_scholar",
    ),
    (
        "pubmed",
        "academic_platform.infrastructure.search_providers.pubmed.registration",
        "register_pubmed",
    ),
    (
        "europe_pmc",
        "academic_platform.infrastructure.search_providers.europe_pmc.registration",
        "register_europe_pmc",
    ),
    (
        "arxiv",
        "academic_platform.infrastructure.search_providers.arxiv.registration",
        "register_arxiv",
    ),
)


@dataclass(frozen=True, slots=True)
class RegisteredProvider:
    """A single entry in the registry."""

    key: str
    adapter_class: type[SearchProviderAdapter] | None
    adapter_factory: AdapterFactory | None
    instance: SearchProviderAdapter | None
    descriptor: ProviderDescriptor | None


class ProviderRegistry:
    """A mutable registry of search provider adapters."""

    def __init__(self) -> None:
        self._entries: dict[str, RegisteredProvider] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def register_class(
        self,
        key: str,
        adapter_class: type[SearchProviderAdapter],
    ) -> None:
        """Register an adapter class under a stable key.

        The class is constructed with no arguments when the registry is
        asked for an instance. Adapters that require configuration should
        be registered with ``register_factory`` instead.
        """
        self._entries[key] = RegisteredProvider(
            key=key,
            adapter_class=adapter_class,
            adapter_factory=None,
            instance=None,
            descriptor=None,
        )

    def register_factory(self, key: str, factory: AdapterFactory) -> None:
        """Register a factory that constructs an adapter from a config dict."""
        self._entries[key] = RegisteredProvider(
            key=key,
            adapter_class=None,
            adapter_factory=factory,
            instance=None,
            descriptor=None,
        )

    def register_instance(
        self,
        key: str,
        adapter: SearchProviderAdapter,
    ) -> None:
        """Register a pre-constructed adapter instance."""
        self._entries[key] = RegisteredProvider(
            key=key,
            adapter_class=None,
            adapter_factory=None,
            instance=adapter,
            descriptor=adapter.descriptor,
        )

    def unregister(self, key: str) -> None:
        """Remove a provider. No-op when the key is absent."""
        self._entries.pop(key, None)

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------
    def get(self, key: str, *, config: dict[str, Any] | None = None) -> SearchProviderAdapter:
        """Return an adapter for the given key.

        Parameters
        ----------
        key:
            The provider key.
        config:
            Optional configuration passed to a registered factory. Ignored
            when the entry is a class or an instance.

        Raises
        ------
        ProviderConfigurationError
            If the key is not registered or if the entry cannot be
            constructed with the supplied configuration.
        """
        entry = self._entries.get(key)
        if entry is None:
            raise ProviderConfigurationError(f"No provider registered for key {key!r}")
        if entry.instance is not None:
            return entry.instance
        if entry.adapter_factory is not None:
            try:
                return entry.adapter_factory(dict(config or {}))
            except Exception as exc:  # noqa: BLE001 - boundary
                raise ProviderConfigurationError(
                    f"Failed to construct provider {key!r}: {exc}"
                ) from exc
        if entry.adapter_class is not None:
            try:
                return entry.adapter_class()
            except Exception as exc:  # noqa: BLE001 - boundary
                raise ProviderConfigurationError(
                    f"Failed to construct provider {key!r}: {exc}"
                ) from exc
        raise ProviderConfigurationError(
            f"Provider {key!r} has no constructor registered"
        )

    def registered_keys(self) -> tuple[str, ...]:
        """Return the sorted keys of every registered provider."""
        return tuple(sorted(self._entries.keys()))

    def descriptors(self) -> tuple[ProviderDescriptor, ...]:
        """Return the descriptor of every registered provider.

        Providers registered as a class or factory are constructed with
        no configuration to obtain their descriptor. Construction
        failures are reported as a descriptor with an explanatory note.
        """
        results: list[ProviderDescriptor] = []
        for key in self.registered_keys():
            try:
                adapter = self.get(key)
                results.append(adapter.descriptor)
            except ProviderConfigurationError as exc:
                results.append(
                    ProviderDescriptor(
                        key=key,
                        display_name=key,
                        base_url="",
                        documentation_url="",
                        provider_kind="unknown",
                        notes=str(exc),
                    )
                )
        return tuple(results)

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key in self._entries

    def __len__(self) -> int:
        return len(self._entries)


_DEFAULT_REGISTRY: ProviderRegistry | None = None


def _builtin_keys() -> frozenset[str]:
    """Return the set of built-in provider keys plus the null fallback."""
    return frozenset({"null"} | {key for key, _, _ in _BUILTIN_PROVIDERS})


def _restore_builtin_providers(registry: ProviderRegistry) -> None:
    """Ensure every built-in provider is registered on ``registry``.

    Registration is idempotent, so a provider that is already present is
    re-registered without effect. Import or registration failures are
    tolerated: the null adapter remains available and the search page
    reports the absence of a provider.
    """
    import importlib
    import logging

    logger = logging.getLogger(__name__)

    if "null" not in registry:
        registry.register_instance("null", NullSearchProviderAdapter())

    for key, module_path, function_name in _BUILTIN_PROVIDERS:
        if key in registry:
            continue
        try:
            module = importlib.import_module(module_path)
        except Exception:  # noqa: BLE001 - boundary
            logger.exception(
                "Failed to import the registration module for %r", key
            )
            continue
        register_function = getattr(module, function_name, None)
        if register_function is None:
            logger.warning(
                "Registration module %s does not expose %s",
                module_path,
                function_name,
            )
            continue
        try:
            register_function(registry)
        except Exception:  # noqa: BLE001 - boundary
            logger.exception("Failed to register the %r adapter", key)


def default_registry() -> ProviderRegistry:
    """Return the process-wide provider registry.

    The registry is constructed on first use and reused on subsequent
    calls. The null adapter is always registered under the key ``"null"``
    so that the orchestration layer has a fallback.

    The function is self-healing: on every call, any built-in provider
    that is missing from the registry is re-registered. This makes the
    default registry resilient to tests that mutate it. Registration is
    idempotent, so re-invoking the registration functions is free.
    """
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = ProviderRegistry()
    _restore_builtin_providers(_DEFAULT_REGISTRY)
    return _DEFAULT_REGISTRY


def reset_default_registry() -> None:
    """Discard the process-wide registry.

    Intended for tests that need a clean slate. Not used by production
    code. Callers that use this function must re-populate the registry
    by calling ``default_registry()`` again, which will restore the
    built-in providers.
    """
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = None