from __future__ import annotations

import sqlite3
from datetime import datetime

from semester_pilot.application.assignment_management.models import (
    AssignmentNotFoundError,
    AssignmentRecord,
    PersonalAssignmentUpdate,
    StaleAssignmentError,
)
from semester_pilot.application.synchronization.models import SyncScope
from semester_pilot.domain.enums import AssignmentStatus, PriorityLevel
from semester_pilot.infrastructure.database import SQLiteDatabase


class SQLiteManagedAssignmentRepository:
    """Reads assignments and updates only explicitly student-owned columns."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def list_current(self) -> tuple[AssignmentRecord, ...]:
        with self._database.connect() as connection:
            scope = self._latest_scope(connection)
            rows = connection.execute(
                self._select_sql(scope) + " ORDER BY a.due_at, a.id",
                self._scope_parameters(scope),
            ).fetchall()
        return tuple(self._map(row) for row in rows)

    def get(self, assignment_id: int) -> AssignmentRecord | None:
        with self._database.connect() as connection:
            scope = self._latest_scope(connection)
            row = connection.execute(
                self._select_sql(scope) + " AND a.id = ?",
                (*self._scope_parameters(scope), assignment_id),
            ).fetchone()
        return self._map(row) if row else None

    def update_personal_fields(
        self,
        assignment_id: int,
        expected_version: int,
        update: PersonalAssignmentUpdate,
    ) -> AssignmentRecord:
        now = datetime.now().astimezone().isoformat()
        completed = update.status in {AssignmentStatus.WORK_COMPLETED, AssignmentStatus.SUBMITTED}
        with self._database.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE assignments SET
                    status = ?, priority = ?, notes = ?, estimated_minutes = ?,
                    progress_percentage = ?, completed = ?, completed_at = ?,
                    updated_at = ?, version = version + 1
                WHERE id = ? AND version = ?
                """,
                (
                    update.status.value,
                    update.priority.value,
                    update.notes,
                    update.estimated_minutes,
                    update.progress_percentage,
                    int(completed),
                    update.completed_at.isoformat() if update.completed_at else None,
                    now,
                    assignment_id,
                    expected_version,
                ),
            )
            if cursor.rowcount == 0:
                exists = connection.execute("SELECT 1 FROM assignments WHERE id = ?", (assignment_id,)).fetchone()
                if exists:
                    raise StaleAssignmentError("המטלה השתנתה מאז שפתחת אותה. רעננו את העמוד לפני שמירה נוספת.")
                raise AssignmentNotFoundError(f"Assignment {assignment_id} does not exist")
        updated = self.get(assignment_id)
        if updated is None:
            raise AssignmentNotFoundError(f"Assignment {assignment_id} does not exist")
        return updated

    @staticmethod
    def _latest_scope(connection: sqlite3.Connection) -> SyncScope | None:
        row = connection.execute(
            "SELECT source_id, institution, semester FROM synchronization_history "
            "ORDER BY synchronized_at DESC, id DESC LIMIT 1"
        ).fetchone()
        return SyncScope(str(row["source_id"]), str(row["institution"]), str(row["semester"])) if row else None

    @staticmethod
    def _scope_parameters(scope: SyncScope | None) -> tuple[str, ...]:
        return (scope.source_id, scope.institution, scope.semester) if scope else ()

    @staticmethod
    def _select_sql(scope: SyncScope | None) -> str:
        scope_clause = " AND c.source_id = ? AND c.institution = ? AND c.semester = ?" if scope else ""
        return f"""
            SELECT a.*, c.code AS course_code, c.name AS course_name,
                   e.is_missing, e.external_uid, e.recurrence_id,
                   e.event_type AS imported_event_type, e.location AS imported_location
            FROM assignments a
            JOIN courses c ON c.id = a.course_id
            LEFT JOIN academic_events e ON e.id = (
                SELECT e2.id FROM academic_events e2
                WHERE e2.assignment_id = a.id
                ORDER BY e2.is_missing ASC, e2.id DESC LIMIT 1
            )
            WHERE a.archived_at IS NULL AND c.archived_at IS NULL{scope_clause}
        """

    @staticmethod
    def _map(row: sqlite3.Row) -> AssignmentRecord:
        return AssignmentRecord(
            id=int(row["id"]),
            course_id=int(row["course_id"]),
            course_code=str(row["course_code"]),
            course_name=str(row["course_name"]),
            title=str(row["title"]),
            description=str(row["description"]),
            due_at=datetime.fromisoformat(str(row["due_at"])),
            status=AssignmentStatus(str(row["status"])),
            priority=PriorityLevel(str(row["priority"])),
            notes=str(row["notes"]),
            estimated_minutes=int(row["estimated_minutes"]) if row["estimated_minutes"] is not None else None,
            progress_percentage=int(row["progress_percentage"]),
            completed_at=datetime.fromisoformat(str(row["completed_at"])) if row["completed_at"] else None,
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
            version=int(row["version"]),
            is_missing_from_source=bool(row["is_missing"]) if row["is_missing"] is not None else False,
            external_uid=str(row["external_uid"]) if row["external_uid"] is not None else None,
            recurrence_id=str(row["recurrence_id"]) if row["recurrence_id"] is not None else None,
            imported_event_type=(str(row["imported_event_type"]) if row["imported_event_type"] is not None else None),
            imported_location=str(row["imported_location"]) if row["imported_location"] is not None else None,
        )
