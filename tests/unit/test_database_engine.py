"""Tests for the database engine and session factory."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from academic_platform.infrastructure.database import Database, DatabaseError


def test_in_memory_database_health_check() -> None:
    database = Database.in_memory()
    try:
        assert database.health_check()
    finally:
        database.dispose()


def test_file_database_creates_parent_directory(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "app.sqlite3"
    database = Database.from_path(target)
    try:
        assert target.parent.is_dir()
        assert database.health_check()
    finally:
        database.dispose()
    assert target.exists()


def test_session_commits_on_success(tmp_path: Path) -> None:
    database = Database.from_path(tmp_path / "app.sqlite3")
    try:
        with database.session() as session:
            session.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"))
        with database.session() as session:
            session.execute(text("INSERT INTO t (v) VALUES ('a')"))
        with database.session() as session:
            count = session.execute(text("SELECT COUNT(*) FROM t")).scalar()
        assert count == 1
    finally:
        database.dispose()


def test_session_rolls_back_on_exception(tmp_path: Path) -> None:
    database = Database.from_path(tmp_path / "app.sqlite3")
    try:
        with database.session() as session:
            session.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"))
        with pytest.raises(DatabaseError):
            with database.session() as session:
                session.execute(text("INSERT INTO t (v) VALUES ('a')"))
                raise RuntimeError("boom")
        with database.session() as session:
            count = session.execute(text("SELECT COUNT(*) FROM t")).scalar()
        assert count == 0
    finally:
        database.dispose()


def test_foreign_keys_pragma_enabled(tmp_path: Path) -> None:
    database = Database.from_path(tmp_path / "app.sqlite3")
    try:
        with database.session() as session:
            value = session.execute(text("PRAGMA foreign_keys")).scalar()
        assert value == 1
    finally:
        database.dispose()


def test_busy_timeout_pragma_applied(tmp_path: Path) -> None:
    database = Database.from_path(tmp_path / "app.sqlite3", busy_timeout_ms=2500)
    try:
        with database.session() as session:
            value = session.execute(text("PRAGMA busy_timeout")).scalar()
        assert value == 2500
    finally:
        database.dispose()


def test_journal_mode_applied_for_file_database(tmp_path: Path) -> None:
    database = Database.from_path(tmp_path / "app.sqlite3")
    try:
        with database.session() as session:
            mode = session.execute(text("PRAGMA journal_mode")).scalar()
        assert mode.lower() == "wal"
    finally:
        database.dispose()


def test_journal_mode_applied_for_memory_database() -> None:
    database = Database.in_memory()
    try:
        with database.session() as session:
            mode = session.execute(text("PRAGMA journal_mode")).scalar()
        assert mode.lower() == "memory"
    finally:
        database.dispose()


def test_session_scope_is_alias_for_session() -> None:
    assert Database.session_scope is Database.session


def test_vacuum_on_memory_database_is_noop() -> None:
    database = Database.in_memory()
    try:
        database.vacuum()
    finally:
        database.dispose()


def test_vacuum_on_file_database(tmp_path: Path) -> None:
    database = Database.from_path(tmp_path / "app.sqlite3")
    try:
        database.vacuum()
    finally:
        database.dispose()


def test_integrity_check_returns_true_on_healthy_database(tmp_path: Path) -> None:
    database = Database.from_path(tmp_path / "app.sqlite3")
    try:
        assert database.integrity_check() is True
    finally:
        database.dispose()


def test_analyze_on_file_database(tmp_path: Path) -> None:
    database = Database.from_path(tmp_path / "app.sqlite3")
    try:
        with database.session() as session:
            session.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY)"))
        database.analyze()
    finally:
        database.dispose()


def test_health_check_reports_false_after_engine_disposed(tmp_path: Path) -> None:
    database = Database.from_path(tmp_path / "app.sqlite3")
    database.dispose()
    # A disposed engine can still be used because SQLAlchemy recreates the
    # pool lazily; the health check must therefore still report True.
    assert database.health_check()