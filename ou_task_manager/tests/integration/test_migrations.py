from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from semester_pilot.infrastructure.database import SQLiteDatabase
from semester_pilot.infrastructure.migrations import Migration, SQLiteMigrator


def test_fresh_database_reaches_latest_version(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "fresh.db")

    version = SQLiteMigrator(database).migrate()

    assert version == 5
    with database.connect() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 5
        applied = connection.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(assignments)")}
        tables = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert [row["version"] for row in applied] == [1, 2, 3, 4, 5]
    assert {"due_at", "status", "priority", "archived_at", "progress_percentage", "version"} <= columns
    assert {"academic_events", "synchronization_history", "subtasks"} <= tables


def test_legacy_database_is_upgraded_without_losing_data(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL
        );
        CREATE TABLE assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            number TEXT NOT NULL,
            due_date TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            UNIQUE(course_id, number, due_date),
            FOREIGN KEY(course_id) REFERENCES courses(id)
        );
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO courses(code, name) VALUES ('101', 'Legacy course');
        INSERT INTO assignments(course_id, number, due_date, completed, notes)
        VALUES (1, '01', '2027-01-10', 1, 'Keep me');
        """
    )
    connection.close()
    database = SQLiteDatabase(path)

    SQLiteMigrator(database).migrate()
    SQLiteMigrator(database).migrate()

    with database.connect() as upgraded:
        row = upgraded.execute("SELECT * FROM assignments WHERE id = 1").fetchone()
        course = upgraded.execute("SELECT * FROM courses WHERE id = 1").fetchone()
    assert course["name"] == "Legacy course"
    assert row["notes"] == "Keep me"
    assert row["status"] == "WORK_COMPLETED"
    assert row["title"] == "Assignment 01"
    assert row["due_at"].startswith("2027-01-10")


def test_failed_migration_rolls_back_schema_and_version(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "rollback.db")

    def fail_after_write(connection: sqlite3.Connection) -> None:
        connection.execute("CREATE TABLE should_be_rolled_back (id INTEGER)")
        raise RuntimeError("migration failed")

    migrator = SQLiteMigrator(database, (Migration(1, "failure", fail_after_write),))

    with pytest.raises(RuntimeError, match="migration failed"):
        migrator.migrate()

    with database.connect() as connection:
        table = connection.execute("SELECT name FROM sqlite_master WHERE name = 'should_be_rolled_back'").fetchone()
        applied = connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    assert table is None
    assert applied == 0


def test_connections_enforce_foreign_keys(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "foreign-keys.db")
    SQLiteMigrator(database).migrate()

    with database.connect() as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute("INSERT INTO assignments(course_id, number, due_date) VALUES (999, '01', '2027-01-10')")
