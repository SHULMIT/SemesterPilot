from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from semester_pilot.infrastructure.database import SQLiteDatabase

MigrationOperation = Callable[[sqlite3.Connection], None]


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    apply: MigrationOperation


def _create_legacy_compatible_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            number TEXT NOT NULL,
            due_date TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            UNIQUE(course_id, number, due_date),
            FOREIGN KEY(course_id) REFERENCES courses(id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})")}


def _add_column(connection: sqlite3.Connection, table: str, definition: str) -> None:
    name = definition.split(maxsplit=1)[0]
    if name not in _columns(connection, table):
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")


def _add_domain_fields(connection: sqlite3.Connection) -> None:
    course_columns = (
        "external_key TEXT",
        "semester TEXT",
        "institution TEXT",
        "color TEXT",
        "archived_at TEXT",
        "created_at TEXT",
        "updated_at TEXT",
    )
    for definition in course_columns:
        _add_column(connection, "courses", definition)

    assignment_columns = (
        "title TEXT NOT NULL DEFAULT ''",
        "description TEXT NOT NULL DEFAULT ''",
        "due_at TEXT",
        "recommended_start_at TEXT",
        "status TEXT NOT NULL DEFAULT 'NOT_STARTED'",
        "priority TEXT NOT NULL DEFAULT 'NORMAL'",
        "estimated_minutes INTEGER",
        "actual_minutes INTEGER NOT NULL DEFAULT 0",
        "source_event_id INTEGER",
        "source_fingerprint TEXT",
        "completed_at TEXT",
        "submitted_at TEXT",
        "archived_at TEXT",
        "created_at TEXT",
        "updated_at TEXT",
    )
    for definition in assignment_columns:
        _add_column(connection, "assignments", definition)

    connection.execute(
        "UPDATE courses SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP), "
        "updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)"
    )
    connection.execute(
        """
        UPDATE assignments
        SET title = CASE WHEN title = '' THEN 'Assignment ' || number ELSE title END,
            due_at = COALESCE(due_at, due_date || 'T23:59:59'),
            status = CASE WHEN completed = 1 THEN 'WORK_COMPLETED' ELSE status END,
            completed_at = CASE
                WHEN completed = 1 THEN COALESCE(completed_at, CURRENT_TIMESTAMP)
                ELSE completed_at
            END,
            created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
            updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_courses_archived_at ON courses(archived_at)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_assignments_course_id ON assignments(course_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_assignments_due_at ON assignments(due_at)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_assignments_status ON assignments(status)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_assignments_archived_at ON assignments(archived_at)")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_assignments_source_fingerprint ON assignments(source_fingerprint)"
    )


def _add_calendar_synchronization_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE courses_v3 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL DEFAULT 'legacy',
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            external_key TEXT,
            semester TEXT NOT NULL DEFAULT '',
            institution TEXT NOT NULL DEFAULT '',
            color TEXT,
            archived_at TEXT,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(source_id, institution, code, semester)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO courses_v3(
            id, source_id, code, name, external_key, semester, institution,
            color, archived_at, created_at, updated_at
        )
        SELECT id, 'legacy', code, name, external_key, COALESCE(semester, ''),
               COALESCE(institution, ''), color, archived_at, created_at, updated_at
        FROM courses
        """
    )
    connection.execute(
        """
        CREATE TABLE assignments_v3 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            number TEXT NOT NULL,
            due_date TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            due_at TEXT,
            recommended_start_at TEXT,
            status TEXT NOT NULL DEFAULT 'NOT_STARTED',
            priority TEXT NOT NULL DEFAULT 'NORMAL',
            estimated_minutes INTEGER,
            actual_minutes INTEGER NOT NULL DEFAULT 0,
            source_event_id INTEGER,
            source_fingerprint TEXT,
            completed_at TEXT,
            submitted_at TEXT,
            archived_at TEXT,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(course_id, number),
            FOREIGN KEY(course_id) REFERENCES courses_v3(id)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO assignments_v3(
            id, course_id, number, due_date, completed, notes, title,
            description, due_at, recommended_start_at, status, priority,
            estimated_minutes, actual_minutes, source_event_id,
            source_fingerprint, completed_at, submitted_at, archived_at,
            created_at, updated_at
        )
        SELECT id, course_id, number, due_date, completed, notes, title,
               description, due_at, recommended_start_at, status, priority,
               estimated_minutes, actual_minutes, source_event_id,
               source_fingerprint, completed_at, submitted_at, archived_at,
               created_at, updated_at
        FROM assignments
        """
    )
    connection.execute("DROP TABLE assignments")
    connection.execute("DROP TABLE courses")
    connection.execute("ALTER TABLE courses_v3 RENAME TO courses")
    connection.execute("ALTER TABLE assignments_v3 RENAME TO assignments")

    connection.execute(
        """
        CREATE TABLE academic_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            institution TEXT NOT NULL,
            semester TEXT NOT NULL,
            external_uid TEXT,
            recurrence_id TEXT,
            stable_match_key TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            event_type TEXT NOT NULL,
            course_id INTEGER,
            assignment_id INTEGER,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            starts_at TEXT NOT NULL,
            ends_at TEXT,
            is_all_day INTEGER NOT NULL DEFAULT 0,
            location TEXT NOT NULL DEFAULT '',
            sequence INTEGER,
            source_last_modified_at TEXT,
            is_missing INTEGER NOT NULL DEFAULT 0,
            source_archived_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(course_id) REFERENCES courses(id),
            FOREIGN KEY(assignment_id) REFERENCES assignments(id)
        )
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX uq_academic_events_uid_instance
        ON academic_events(
            source_id, institution, semester, external_uid,
            COALESCE(recurrence_id, '')
        )
        WHERE external_uid IS NOT NULL
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX uq_academic_events_stable_without_uid
        ON academic_events(source_id, institution, semester, stable_match_key)
        WHERE external_uid IS NULL
        """
    )
    connection.execute("CREATE INDEX idx_academic_events_scope ON academic_events(source_id, institution, semester)")
    connection.execute("CREATE INDEX idx_academic_events_content_hash ON academic_events(content_hash)")
    connection.execute("CREATE INDEX idx_academic_events_course_id ON academic_events(course_id)")
    connection.execute("CREATE INDEX idx_academic_events_assignment_id ON academic_events(assignment_id)")
    connection.execute("CREATE INDEX idx_academic_events_missing ON academic_events(is_missing)")
    connection.execute(
        """
        CREATE TABLE synchronization_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            institution TEXT NOT NULL,
            semester TEXT NOT NULL,
            synchronized_at TEXT NOT NULL,
            added_count INTEGER NOT NULL,
            updated_count INTEGER NOT NULL,
            unchanged_count INTEGER NOT NULL,
            missing_count INTEGER NOT NULL,
            ambiguous_count INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX idx_sync_history_scope ON synchronization_history(source_id, institution, semester)"
    )
    connection.execute("CREATE INDEX idx_courses_archived_at ON courses(archived_at)")
    connection.execute("CREATE INDEX idx_assignments_course_id ON assignments(course_id)")
    connection.execute("CREATE INDEX idx_assignments_due_at ON assignments(due_at)")
    connection.execute("CREATE INDEX idx_assignments_status ON assignments(status)")
    connection.execute("CREATE INDEX idx_assignments_archived_at ON assignments(archived_at)")
    connection.execute("CREATE INDEX idx_assignments_source_fingerprint ON assignments(source_fingerprint)")


def _add_assignment_management_fields(connection: sqlite3.Connection) -> None:
    connection.execute(
        "ALTER TABLE assignments ADD COLUMN progress_percentage INTEGER NOT NULL DEFAULT 0 "
        "CHECK(progress_percentage BETWEEN 0 AND 100)"
    )
    connection.execute("ALTER TABLE assignments ADD COLUMN version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1)")
    connection.execute(
        """
        UPDATE assignments
        SET progress_percentage = CASE
            WHEN status IN ('WORK_COMPLETED', 'SUBMITTED') OR completed = 1 THEN 100
            ELSE 0
        END
        """
    )


def _add_subtasks(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE subtasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0, 1)),
            estimated_minutes INTEGER CHECK(estimated_minutes IS NULL OR estimated_minutes > 0),
            position INTEGER NOT NULL CHECK(position >= 0),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1),
            FOREIGN KEY(assignment_id) REFERENCES assignments(id) ON DELETE RESTRICT,
            UNIQUE(assignment_id, position)
        )
        """
    )
    connection.execute("CREATE INDEX idx_subtasks_assignment ON subtasks(assignment_id)")
    connection.execute("CREATE INDEX idx_subtasks_order ON subtasks(assignment_id, position, id)")


DEFAULT_MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "legacy-compatible baseline", _create_legacy_compatible_schema),
    Migration(2, "course and assignment domain fields", _add_domain_fields),
    Migration(3, "calendar synchronization schema", _add_calendar_synchronization_schema),
    Migration(4, "assignment management fields", _add_assignment_management_fields),
    Migration(5, "user-owned assignment subtasks", _add_subtasks),
)


class SQLiteMigrator:
    """Applies ordered SQLite migrations exactly once and transactionally."""

    def __init__(
        self,
        database: SQLiteDatabase,
        migrations: Sequence[Migration] = DEFAULT_MIGRATIONS,
    ) -> None:
        self._database = database
        self._migrations = tuple(sorted(migrations, key=lambda migration: migration.version))
        versions = [migration.version for migration in self._migrations]
        if len(versions) != len(set(versions)):
            raise ValueError("Migration versions must be unique")

    def migrate(self) -> int:
        with self._database.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

        for migration in self._migrations:
            with self._database.connection() as connection:
                applied = connection.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = ?", (migration.version,)
                ).fetchone()
                if applied:
                    continue
                connection.execute("BEGIN IMMEDIATE")
                migration.apply(connection)
                connection.execute(
                    "INSERT INTO schema_migrations(version, name) VALUES (?, ?)",
                    (migration.version, migration.name),
                )
                connection.execute(f"PRAGMA user_version = {migration.version}")

        return self.current_version()

    def current_version(self) -> int:
        with self._database.connection() as connection:
            row = connection.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
        return int(row[0])
