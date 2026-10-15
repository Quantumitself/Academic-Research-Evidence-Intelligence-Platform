"""Tests for the navigation destination registry."""

from __future__ import annotations

from academic_platform.ui.main_window_destinations import (
    DESTINATIONS,
    DESTINATIONS_BY_ID,
    get_destination,
    is_known_destination,
)


def test_destinations_are_unique() -> None:
    identifiers = [destination.identifier for destination in DESTINATIONS]
    assert len(identifiers) == len(set(identifiers))


def test_expected_destination_count() -> None:
    assert len(DESTINATIONS) == 12


def test_every_destination_has_required_metadata() -> None:
    for destination in DESTINATIONS:
        assert destination.identifier
        assert destination.label
        assert destination.purpose
        assert destination.shortcut
        assert destination.glyph


def test_identifiers_are_lowercase_snake_case() -> None:
    for destination in DESTINATIONS:
        assert destination.identifier == destination.identifier.lower()
        assert " " not in destination.identifier


def test_shortcuts_are_unique() -> None:
    shortcuts = [destination.shortcut for destination in DESTINATIONS]
    assert len(shortcuts) == len(set(shortcuts))


def test_index_matches_tuple() -> None:
    assert set(DESTINATIONS_BY_ID) == {d.identifier for d in DESTINATIONS}
    for destination in DESTINATIONS:
        assert DESTINATIONS_BY_ID[destination.identifier] is destination


def test_get_destination_returns_instance() -> None:
    destination = get_destination("dashboard")
    assert destination.identifier == "dashboard"
    assert destination.label == "Dashboard"


def test_get_destination_unknown_raises() -> None:
    import pytest

    with pytest.raises(KeyError):
        get_destination("nonexistent")


def test_is_known_destination() -> None:
    assert is_known_destination("dashboard")
    assert not is_known_destination("nonexistent")