from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import datetime
from types import TracebackType

from semester_pilot.application.calendar.models import AssignmentCandidate, CourseCandidate
from semester_pilot.application.synchronization.models import (
    PersistedAcademicEvent,
    SyncScope,
    SynchronizationHistory,
)
from semester_pilot.application.synchronization.ports import (
    AcademicEventRepository,
    CalendarSyncUnitOfWork,
    SyncAssignmentRepository,
    SyncCourseRepository,
    SynchronizationHistoryRepository,
)
from semester_pilot.domain.entities import Assignment, Course
from semester_pilot.infrastructure.database import SQLiteDatabase
from semester_pilot.infrastructure.repositories import SQLiteAssignmentRepository


def _serialize(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _now() -> datetime:
    return datetime.now().astimezone()


def _lastrowid(cursor: sqlite3.Cursor) -> int:
    if cursor.lastrowid is None:
        raise RuntimeError("SQLite insert did not return an id")
    return cursor.lastrowid


class SQLiteSyncCourseRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get_or_create_imported(self, candidate: CourseCandidate, scope: SyncScope) -> Course:
        row = self._connection.execute(
            """
            SELECT * FROM courses
            WHERE source_id = ? AND institution = ? AND code = ? AND semester = ?
            """,
            (scope.source_id, scope.institution, candidate.code, scope.semester),
        ).fetchone()
        if row:
            if str(row["name"]) != candidate.name:
                now = _now()
                self._connection.execute(
                    "UPDATE courses SET name = ?, updated_at = ? WHERE id = ?",
                    (candidate.name, _serialize(now), row["id"]),
                )
                row = self._connection.execute("SELECT * FROM courses WHERE id = ?", (row["id"],)).fetchone()
            return self._to_entity(row)
        now = _now()
        cursor = self._connection.execute(
            """
            INSERT INTO courses(
                source_id, code, name, external_key, semester, institution,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scope.source_id,
                candidate.code,
                candidate.name,
                candidate.code,
                scope.semester,
                scope.institution,
                _serialize(now),
                _serialize(now),
            ),
        )
        return Course(
            id=_lastrowid(cursor),
            code=candidate.code,
            name=candidate.name,
            external_key=candidate.code,
            semester=scope.semester,
            institution=scope.institution,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _to_entity(row: sqlite3.Row) -> Course:
        return Course(
            id=int(row["id"]),
            code=str(row["code"]),
            name=str(row["name"]),
            external_key=row["external_key"],
            semester=row["semester"],
            institution=row["institution"],
            color=row["color"],
            archived_at=_parse(row["archived_at"]),
            created_at=_parse(row["created_at"]),
            updated_at=_parse(row["updated_at"]),
        )


class SQLiteSyncAssignmentRepository:
    def __init__(self, database: SQLiteDatabase, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._repository = SQLiteAssignmentRepository(database, connection)

    def get_or_create_imported(self, candidate: AssignmentCandidate, course_id: int) -> Assignment:
        row = self._connection.execute(
            "SELECT * FROM assignments WHERE course_id = ? AND number = ?",
            (course_id, candidate.number),
        ).fetchone()
        if row:
            return SQLiteAssignmentRepository._to_entity(row)
        return self._repository.create(
            Assignment(
                course_id=course_id,
                number=candidate.number,
                title=candidate.title,
                due_at=candidate.due_at,
            )
        )

    def update_imported_fields(
        self,
        assignment_id: int,
        *,
        title: str,
        due_at: datetime,
        source_fingerprint: str,
    ) -> Assignment:
        now = _now()
        cursor = self._connection.execute(
            """
            UPDATE assignments
            SET title = ?, due_date = ?, due_at = ?, source_fingerprint = ?, updated_at = ?,
                version = version + 1
            WHERE id = ?
            """,
            (
                title,
                due_at.date().isoformat(),
                _serialize(due_at),
                source_fingerprint,
                _serialize(now),
                assignment_id,
            ),
        )
        if cursor.rowcount == 0:
            raise LookupError(f"Assignment {assignment_id} does not exist")
        assignment = self._repository.get(assignment_id)
        if assignment is None:
            raise LookupError(f"Assignment {assignment_id} does not exist")
        return assignment


class SQLiteAcademicEventRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def list_for_scope(self, scope: SyncScope) -> list[PersistedAcademicEvent]:
        rows = self._connection.execute(
            """
            SELECT * FROM academic_events
            WHERE source_id = ? AND institution = ? AND semester = ?
            ORDER BY id
            """,
            (scope.source_id, scope.institution, scope.semester),
        ).fetchall()
        return [self._to_model(row) for row in rows]

    def create(self, event: PersistedAcademicEvent) -> PersistedAcademicEvent:
        now = _now()
        cursor = self._connection.execute(
            """
            INSERT INTO academic_events(
                source_id, institution, semester, external_uid, recurrence_id,
                stable_match_key, content_hash, event_type, course_id, assignment_id,
                title, description, starts_at, ends_at, is_all_day, location,
                sequence, source_last_modified_at, is_missing, source_archived_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._values(event, event.created_at or now, now),
        )
        return replace(event, id=_lastrowid(cursor), created_at=now, updated_at=now)

    def update_source_fields(self, event_id: int, event: PersistedAcademicEvent) -> PersistedAcademicEvent:
        now = _now()
        values = self._values(event, event.created_at or now, now)
        cursor = self._connection.execute(
            """
            UPDATE academic_events SET
                source_id = ?, institution = ?, semester = ?, external_uid = ?,
                recurrence_id = ?, stable_match_key = ?, content_hash = ?, event_type = ?,
                course_id = ?, assignment_id = ?, title = ?, description = ?, starts_at = ?,
                ends_at = ?, is_all_day = ?, location = ?, sequence = ?,
                source_last_modified_at = ?, is_missing = ?, source_archived_at = ?,
                created_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (*values, event_id),
        )
        if cursor.rowcount == 0:
            raise LookupError(f"Academic event {event_id} does not exist")
        return replace(event, id=event_id, updated_at=now)

    def mark_missing(self, event_id: int) -> PersistedAcademicEvent:
        now = _now()
        cursor = self._connection.execute(
            """
            UPDATE academic_events
            SET is_missing = 1, source_archived_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (_serialize(now), _serialize(now), event_id),
        )
        if cursor.rowcount == 0:
            raise LookupError(f"Academic event {event_id} does not exist")
        row = self._connection.execute("SELECT * FROM academic_events WHERE id = ?", (event_id,)).fetchone()
        return self._to_model(row)

    @staticmethod
    def _values(event: PersistedAcademicEvent, created_at: datetime, updated_at: datetime) -> tuple[object, ...]:
        return (
            event.scope.source_id,
            event.scope.institution,
            event.scope.semester,
            event.external_uid,
            event.recurrence_id,
            event.stable_match_key,
            event.content_hash,
            event.event_type.value,
            event.course_id,
            event.assignment_id,
            event.title,
            event.description,
            _serialize(event.starts_at),
            _serialize(event.ends_at),
            int(event.is_all_day),
            event.location,
            event.sequence,
            _serialize(event.source_last_modified_at),
            int(event.is_missing),
            _serialize(event.source_archived_at),
            _serialize(created_at),
            _serialize(updated_at),
        )

    @staticmethod
    def _to_model(row: sqlite3.Row) -> PersistedAcademicEvent:
        from semester_pilot.domain.enums import EventType

        return PersistedAcademicEvent(
            id=int(row["id"]),
            scope=SyncScope(str(row["source_id"]), str(row["institution"]), str(row["semester"])),
            external_uid=row["external_uid"],
            recurrence_id=row["recurrence_id"],
            stable_match_key=str(row["stable_match_key"]),
            content_hash=str(row["content_hash"]),
            event_type=EventType(str(row["event_type"])),
            course_id=row["course_id"],
            assignment_id=row["assignment_id"],
            title=str(row["title"]),
            description=str(row["description"]),
            starts_at=datetime.fromisoformat(str(row["starts_at"])),
            ends_at=_parse(row["ends_at"]),
            is_all_day=bool(row["is_all_day"]),
            location=str(row["location"]),
            sequence=row["sequence"],
            source_last_modified_at=_parse(row["source_last_modified_at"]),
            is_missing=bool(row["is_missing"]),
            source_archived_at=_parse(row["source_archived_at"]),
            created_at=_parse(row["created_at"]),
            updated_at=_parse(row["updated_at"]),
        )


class SQLiteSynchronizationHistoryRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create(self, history: SynchronizationHistory) -> SynchronizationHistory:
        synchronized_at = history.synchronized_at or _now()
        cursor = self._connection.execute(
            """
            INSERT INTO synchronization_history(
                source_id, institution, semester, added_count, updated_count,
                unchanged_count, missing_count, ambiguous_count, synchronized_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                history.scope.source_id,
                history.scope.institution,
                history.scope.semester,
                history.added_count,
                history.updated_count,
                history.unchanged_count,
                history.missing_count,
                history.ambiguous_count,
                _serialize(synchronized_at),
            ),
        )
        return replace(history, id=_lastrowid(cursor), synchronized_at=synchronized_at)


class SQLiteCalendarSyncUnitOfWork:
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database
        self._transaction: AbstractContextManager[sqlite3.Connection] | None = None
        self.courses: SyncCourseRepository
        self.assignments: SyncAssignmentRepository
        self.events: AcademicEventRepository
        self.history: SynchronizationHistoryRepository

    def __enter__(self) -> CalendarSyncUnitOfWork:
        self._transaction = self._database.transaction()
        connection = self._transaction.__enter__()
        self.courses = SQLiteSyncCourseRepository(connection)
        self.assignments = SQLiteSyncAssignmentRepository(self._database, connection)
        self.events = SQLiteAcademicEventRepository(connection)
        self.history = SQLiteSynchronizationHistoryRepository(connection)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if self._transaction is None:
            return None
        return self._transaction.__exit__(exc_type, exc_value, traceback)
