"""Built-in search source catalog.

The catalog describes the sources the application ships with. Each entry
is a ``SourceConfig`` that the bootstrap writes to the database on first
start. Built-in sources cannot be removed; they can be disabled.

The catalog is data, not code. Adding a new built-in source is a matter
of adding an entry; no other module needs to change. The provider keys
match the modules that later phases register with the provider registry.
"""

from __future__ import annotations

from dataclasses import dataclass

from academic_platform.application.search_sources.source_config import SourceConfig


@dataclass(frozen=True, slots=True)
class BuiltinSource:
    """Definition of a built-in source."""

    config: SourceConfig
    order: int = 0


BUILTIN_SOURCES: tuple[BuiltinSource, ...] = (
    BuiltinSource(
        order=10,
        config=SourceConfig(
            key="crossref",
            provider_key="crossref",
            display_name="Crossref",
            source_type="builtin",
            base_url="https://api.crossref.org",
            endpoint="works",
            http_method="GET",
            parameter_map={
                "query": "query",
                "limit": "rows",
                "offset": "offset",
                "year_from": "filter",
                "year_to": "filter",
                "sort": "sort",
            },
            capabilities={
                "pagination": True,
                "abstract_in_results": True,
                "open_access_flag": True,
                "citation_counts": False,
            },
            auth_type="none",
            enabled=True,
            timeout_seconds=30,
            result_limit=50,
        ),
    ),
    BuiltinSource(
        order=20,
        config=SourceConfig(
            key="openalex",
            provider_key="openalex",
            display_name="OpenAlex",
            source_type="builtin",
            base_url="https://api.openalex.org",
            endpoint="works",
            http_method="GET",
            parameter_map={
                "query": "search",
                "limit": "per-page",
                "offset": "page",
                "year_from": "filter",
                "year_to": "filter",
                "open_access": "filter",
                "sort": "sort",
            },
            capabilities={
                "pagination": True,
                "cursor_pagination": True,
                "abstract_in_results": True,
                "open_access_flag": True,
                "citation_counts": True,
            },
            auth_type="none",
            enabled=True,
            timeout_seconds=30,
            result_limit=50,
        ),
    ),
    BuiltinSource(
        order=30,
        config=SourceConfig(
            key="semantic_scholar",
            provider_key="semantic_scholar",
            display_name="Semantic Scholar",
            source_type="builtin",
            base_url="https://api.semanticscholar.org",
            endpoint="graph/v1/paper/search",
            http_method="GET",
            parameter_map={
                "query": "query",
                "limit": "limit",
                "offset": "offset",
                "year_from": "year",
                "year_to": "year",
            },
            capabilities={
                "pagination": True,
                "abstract_in_results": True,
                "open_access_flag": True,
                "citation_counts": True,
                "requires_api_key": False,
            },
            auth_type="none",
            enabled=True,
            timeout_seconds=30,
            result_limit=50,
        ),
    ),
    BuiltinSource(
        order=40,
        config=SourceConfig(
            key="pubmed",
            provider_key="pubmed",
            display_name="PubMed",
            source_type="builtin",
            base_url="https://eutils.ncbi.nlm.nih.gov",
            endpoint="entrez/eutils/esearch.fcgi",
            http_method="GET",
            parameter_map={
                "query": "term",
                "limit": "retmax",
                "offset": "retstart",
            },
            capabilities={
                "pagination": True,
                "abstract_in_results": False,
                "open_access_flag": False,
                "citation_counts": False,
            },
            auth_type="none",
            enabled=True,
            timeout_seconds=30,
            result_limit=50,
        ),
    ),
    BuiltinSource(
        order=50,
        config=SourceConfig(
            key="europe_pmc",
            provider_key="europe_pmc",
            display_name="Europe PMC",
            source_type="builtin",
            base_url="https://www.ebi.ac.uk",
            endpoint="europepmc/webservices/rest/search",
            http_method="GET",
            parameter_map={
                "query": "query",
                "limit": "pageSize",
                "offset": "cursorMark",
            },
            capabilities={
                "pagination": True,
                "cursor_pagination": True,
                "abstract_in_results": True,
                "open_access_flag": True,
                "citation_counts": True,
            },
            auth_type="none",
            enabled=True,
            timeout_seconds=30,
            result_limit=50,
        ),
    ),
    BuiltinSource(
        order=60,
        config=SourceConfig(
            key="arxiv",
            provider_key="arxiv",
            display_name="arXiv",
            source_type="builtin",
            base_url="https://export.arxiv.org",
            endpoint="api/query",
            http_method="GET",
            parameter_map={
                "query": "search_query",
                "limit": "max_results",
                "offset": "start",
            },
            capabilities={
                "pagination": True,
                "abstract_in_results": True,
                "open_access_flag": True,
                "citation_counts": False,
            },
            auth_type="none",
            enabled=True,
            timeout_seconds=30,
            result_limit=50,
        ),
    ),
)


def builtin_source_keys() -> tuple[str, ...]:
    """Return the sorted keys of every built-in source."""
    return tuple(sorted(source.config.key for source in BUILTIN_SOURCES))


def find_builtin(key: str) -> BuiltinSource | None:
    """Return the built-in source with the given key, or ``None``."""
    for source in BUILTIN_SOURCES:
        if source.config.key == key:
            return source
    return None