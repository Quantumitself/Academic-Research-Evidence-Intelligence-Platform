"""Tests for the synthesis report model."""

from __future__ import annotations

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    Collection,
    SynthesisReport,
)


def test_create_and_read() -> None:
    database = Database.in_memory()
    try:
        Base.metadata.create_all(database.engine)
        with database.session() as session:
            collection = Collection(key="c1")
            session.add(collection)
            session.flush()
            report = SynthesisReport(
                collection_id=collection.id,
                report_kind="narrative",
                title="Synthesis",
            )
            session.add(report)
            session.flush()
            identifier = report.id
        with database.session() as session:
            loaded = session.get(SynthesisReport, identifier)
            assert loaded is not None
            assert loaded.report_kind == "narrative"
            assert loaded.included_evidence_ids_json == "[]"
    finally:
        database.dispose()


def test_cascade_delete_via_collection() -> None:
    database = Database.in_memory()
    try:
        Base.metadata.create_all(database.engine)
        with database.session() as session:
            collection = Collection(key="c1")
            session.add(collection)
            session.flush()
            session.add(
                SynthesisReport(
                    collection_id=collection.id,
                    report_kind="narrative",
                )
            )
        with database.session() as session:
            collection = session.get(Collection, 1)
            assert collection is not None
            session.delete(collection)
        with database.session() as session:
            assert session.query(SynthesisReport).count() == 0
    finally:
        database.dispose()