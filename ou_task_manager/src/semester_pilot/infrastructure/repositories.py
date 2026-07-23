from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime

from semester_pilot.domain.entities import Assignment, Course
from semester_pilot.domain.enums import AssignmentStatus, PriorityLevel
from semester_pilot.infrastructure.database import SQLiteDatabase


def _serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _now() -> datetime:
    return datetime.now().astimezone()


class SQLiteCourseRepository:
    """SQLite implementation of the course persistence contract."""

    def __init__(self, database: SQLiteDatabase, connection: sqlite3.Connection | None = None) -> None:
        self._database = database
        self._shared_connection = connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        if self._shared_connection is not None:
            yield self._shared_connection
            return
        with self._database.connection() as connection:
            yield connection

    def create(self, course: Course) -> Course:
        now = _now()
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO courses(
                    code, name, external_key, semester, institution, color,
                    archived_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    course.code,
                    course.name,
                    course.external_key,
                    course.semester or "",
                    course.institution or "",
                    course.color,
                    _serialize_datetime(course.archived_at),
                    _serialize_datetime(now),
                    _serialize_datetime(now),
                ),
            )
        return replace(course, id=cursor.lastrowid, created_at=now, updated_at=now)

    def get(self, course_id: int) -> Course | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
        return self._to_entity(row) if row else None

    def list_active(self) -> list[Course]:
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM courses WHERE archived_at IS NULL ORDER BY name, code").fetchall()
        return [self._to_entity(row) for row in rows]

    def update(self, course: Course) -> Course:
        if course.id is None:
            raise ValueError("Cannot update a course without an id")
        now = _now()
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE courses
                SET code = ?, name = ?, external_key = ?, semester = ?,
                    institution = ?, color = ?, archived_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    course.code,
                    course.name,
                    course.external_key,
                    course.semester or "",
                    course.institution or "",
                    course.color,
                    _serialize_datetime(course.archived_at),
                    _serialize_datetime(now),
                    course.id,
                ),
            )
            if cursor.rowcount == 0:
                raise LookupError(f"Course {course.id} does not exist")
        return replace(course, updated_at=now)

    def archive(self, course_id: int) -> Course | None:
        course = self.get(course_id)
        if course is None:
            return None
        return self.update(replace(course, archived_at=_now()))

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
            archived_at=_parse_datetime(row["archived_at"]),
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )


class SQLiteAssignmentRepository:
    """SQLite implementation of the assignment persistence contract."""

    def __init__(self, database: SQLiteDatabase, connection: sqlite3.Connection | None = None) -> None:
        self._database = database
        self._shared_connection = connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        if self._shared_connection is not None:
            yield self._shared_connection
            return
        with self._database.connection() as connection:
            yield connection

    def create(self, assignment: Assignment) -> Assignment:
        now = _now()
        completed = assignment.status in {AssignmentStatus.WORK_COMPLETED, AssignmentStatus.SUBMITTED}
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO assignments(
                    course_id, number, title, description, due_date, due_at,
                    recommended_start_at, status, priority, estimated_minutes,
                    actual_minutes, notes, source_event_id, source_fingerprint,
                    progress_percentage, completed, completed_at, submitted_at, archived_at,
                    created_at, updated_at, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._values(assignment, now, completed),
            )
        return replace(assignment, id=cursor.lastrowid, created_at=now, updated_at=now)

    def get(self, assignment_id: int) -> Assignment | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,)).fetchone()
        return self._to_entity(row) if row else None

    def list_active(self, course_id: int | None = None) -> list[Assignment]:
        query = "SELECT * FROM assignments WHERE archived_at IS NULL"
        parameters: tuple[int, ...] = ()
        if course_id is not None:
            query += " AND course_id = ?"
            parameters = (course_id,)
        query += " ORDER BY due_at, id"
        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._to_entity(row) for row in rows]

    def update(self, assignment: Assignment) -> Assignment:
        if assignment.id is None:
            raise ValueError("Cannot update an assignment without an id")
        now = _now()
        completed = assignment.status in {AssignmentStatus.WORK_COMPLETED, AssignmentStatus.SUBMITTED}
        values = self._values(assignment, now, completed)
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE assignments SET
                    course_id = ?, number = ?, title = ?, description = ?,
                    due_date = ?, due_at = ?, recommended_start_at = ?,
                    status = ?, priority = ?, estimated_minutes = ?,
                    actual_minutes = ?, notes = ?, source_event_id = ?,
                    source_fingerprint = ?, progress_percentage = ?, completed = ?, completed_at = ?,
                    submitted_at = ?, archived_at = ?, created_at = ?, updated_at = ?, version = ?
                WHERE id = ?
                """,
                (*values, assignment.id),
            )
            if cursor.rowcount == 0:
                raise LookupError(f"Assignment {assignment.id} does not exist")
        return replace(assignment, updated_at=now)

    def archive(self, assignment_id: int) -> Assignment | None:
        assignment = self.get(assignment_id)
        if assignment is None:
            return None
        return self.update(replace(assignment, archived_at=_now()))

    @staticmethod
    def _values(assignment: Assignment, updated_at: datetime, completed: bool) -> tuple[object, ...]:
        created_at = assignment.created_at or updated_at
        completed_at = assignment.completed_at
        if completed and completed_at is None:
            completed_at = updated_at
        return (
            assignment.course_id,
            assignment.number,
            assignment.title,
            assignment.description,
            assignment.due_at.date().isoformat(),
            _serialize_datetime(assignment.due_at),
            _serialize_datetime(assignment.recommended_start_at),
            assignment.status.value,
            assignment.priority.value,
            assignment.estimated_minutes,
            assignment.actual_minutes,
            assignment.notes,
            assignment.source_event_id,
            assignment.source_fingerprint,
            assignment.progress_percentage,
            int(completed),
            _serialize_datetime(completed_at),
            _serialize_datetime(assignment.submitted_at),
            _serialize_datetime(assignment.archived_at),
            _serialize_datetime(created_at),
            _serialize_datetime(updated_at),
            assignment.version,
        )

    @staticmethod
    def _to_entity(row: sqlite3.Row) -> Assignment:
        return Assignment(
            id=int(row["id"]),
            course_id=int(row["course_id"]),
            number=str(row["number"]),
            title=str(row["title"]),
            description=str(row["description"]),
            due_at=datetime.fromisoformat(str(row["due_at"])),
            recommended_start_at=_parse_datetime(row["recommended_start_at"]),
            status=AssignmentStatus(str(row["status"])),
            priority=PriorityLevel(str(row["priority"])),
            estimated_minutes=row["estimated_minutes"],
            actual_minutes=int(row["actual_minutes"]),
            progress_percentage=int(row["progress_percentage"]),
            notes=str(row["notes"]),
            source_event_id=row["source_event_id"],
            source_fingerprint=row["source_fingerprint"],
            completed_at=_parse_datetime(row["completed_at"]),
            submitted_at=_parse_datetime(row["submitted_at"]),
            archived_at=_parse_datetime(row["archived_at"]),
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
            version=int(row["version"]),
        )
