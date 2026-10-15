"""Shared navigation destination registry.

This module is the single source of truth for the set of primary
destinations, their display labels, their purpose text, their menu shortcut,
and their icon glyph. Every consumer (navigation bar, main window menu,
placeholder page, command palette in later phases) reads from this module.

The registry contains only data and no imports from the rest of the UI, which
prevents circular imports.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Destination:
    """Metadata describing a single primary destination."""

    identifier: str
    label: str
    purpose: str
    shortcut: str
    glyph: str


DESTINATIONS: tuple[Destination, ...] = (
    Destination(
        identifier="dashboard",
        label="Dashboard",
        purpose="Recent activity, quick actions, and current research status.",
        shortcut="Ctrl+1",
        glyph="\u2302",
    ),
    Destination(
        identifier="discover",
        label="Discover",
        purpose="Search enabled academic sources and review normalized results.",
        shortcut="Ctrl+2",
        glyph="\u2315",
    ),
    Destination(
        identifier="research_assistant",
        label="Research Assistant",
        purpose="Develop a topic into a defensible research plan.",
        shortcut="Ctrl+3",
        glyph="\u2699",
    ),
    Destination(
        identifier="research_projects",
        label="Research Projects",
        purpose="Organize research objectives, questions, and tasks.",
        shortcut="Ctrl+4",
        glyph="\u2637",
    ),
    Destination(
        identifier="library",
        label="My Library",
        purpose="Import, read, annotate, and search your research documents.",
        shortcut="Ctrl+5",
        glyph="\u2261",
    ),
    Destination(
        identifier="collections",
        label="Collections",
        purpose="Group related papers and materials for analysis.",
        shortcut="Ctrl+6",
        glyph="\u25A4",
    ),
    Destination(
        identifier="evidence",
        label="Evidence & Analysis",
        purpose="Extract, verify, compare, and synthesize structured evidence.",
        shortcut="Ctrl+7",
        glyph="\u222B",
    ),
    Destination(
        identifier="guides",
        label="Research Guides",
        purpose="Generate source-linked research guides and learning paths.",
        shortcut="Ctrl+8",
        glyph="\u2630",
    ),
    Destination(
        identifier="knowledge_map",
        label="Knowledge Map",
        purpose="Explore relationships among topics, authors, and works.",
        shortcut="Ctrl+9",
        glyph="\u25CE",
    ),
    Destination(
        identifier="achievements",
        label="Achievements",
        purpose="Track meaningful research progress milestones.",
        shortcut="Ctrl+0",
        glyph="\u2605",
    ),
    Destination(
        identifier="api_integrations",
        label="API & Integrations",
        purpose="Configure the documented integration surface.",
        shortcut="Ctrl+Shift+A",
        glyph="\u21C4",
    ),
    Destination(
        identifier="settings",
        label="Settings",
        purpose="Manage application, search, AI provider, and privacy settings.",
        shortcut="Ctrl+,",
        glyph="\u2692",
    ),
)


DESTINATIONS_BY_ID: dict[str, Destination] = {
    destination.identifier: destination for destination in DESTINATIONS
}


def get_destination(identifier: str) -> Destination:
    """Return the destination with the given identifier.

    Raises
    ------
    KeyError
        If no destination matches the identifier. Callers that may receive
        arbitrary identifiers from user input should check membership first.
    """
    try:
        return DESTINATIONS_BY_ID[identifier]
    except KeyError as exc:
        raise KeyError(f"Unknown destination identifier: {identifier!r}") from exc


def is_known_destination(identifier: str) -> bool:
    """Return True if the identifier corresponds to a registered destination."""
    return identifier in DESTINATIONS_BY_ID