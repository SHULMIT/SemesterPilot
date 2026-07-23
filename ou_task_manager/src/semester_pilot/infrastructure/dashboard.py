from __future__ import annotations

import sqlite3
from datetime import date, datetime

from semester_pilot.application.dashboard.models import (
    DashboardAssignmentRecord,
    DashboardData,
    DashboardEventRecord,
    RecentImportRecord,
)
from semester_pilot.application.synchronization.models import SyncScope
from semester_pilot.domain.enums import AssignmentStatus, EventType, PriorityLevel
from semester_pilot.infrastructure.database import SQLiteDatabase


class SQLiteDashboardRepository:
    """Loads a dashboard snapshot with a fixed number of scoped queries."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def load(self, range_start: date, range_end: date) -> DashboardData:
        with self._database.connect() as connection:
            recent_row = connection.execute(
                "SELECT * FROM synchronization_history ORDER BY synchronized_at DESC, id DESC LIMIT 1"
            ).fetchone()
            scope = self._scope(recent_row)
            course_count = self._course_count(connection, scope)
            assignments = self._assignments(connection, scope)
            events = self._events(connection, scope, range_start, range_end)
        return DashboardData(
            current_scope=scope,
            active_course_count=course_count,
            assignments=assignments,
            events=events,
            recent_import=self._recent_import(recent_row, scope),
        )

    @staticmethod
    def _scope(row: sqlite3.Row | None) -> SyncScope | None:
        if row is None:
            return None
        return SyncScope(str(row["source_id"]), str(row["institution"]), str(row["semester"]))

    @staticmethod
    def _course_count(connection: sqlite3.Connection, scope: SyncScope | None) -> int:
        if scope is None:
            row = connection.execute("SELECT COUNT(*) FROM courses WHERE archived_at IS NULL").fetchone()
        else:
            row = connection.execute(
                """
                SELECT COUNT(*) FROM courses
                WHERE archived_at IS NULL AND source_id = ? AND institution = ? AND semester = ?
                """,
                (scope.source_id, scope.institution, scope.semester),
            ).fetchone()
        return int(row[0])

    @staticmethod
    def _assignments(connection: sqlite3.Connection, scope: SyncScope | None) -> tuple[DashboardAssignmentRecord, ...]:
        query = """
            SELECT a.id, a.title, a.due_at, a.status, a.priority, c.code, c.name
            FROM assignments a JOIN courses c ON c.id = a.course_id
            WHERE a.archived_at IS NULL AND c.archived_at IS NULL
        """
        parameters: tuple[str, ...] = ()
        if scope:
            query += " AND c.source_id = ? AND c.institution = ? AND c.semester = ?"
            parameters = (scope.source_id, scope.institution, scope.semester)
        query += " ORDER BY a.due_at, a.id"
        rows = connection.execute(query, parameters).fetchall()
        return tuple(
            DashboardAssignmentRecord(
                id=int(row["id"]),
                course_code=str(row["code"]),
                course_name=str(row["name"]),
                title=str(row["title"]),
                due_at=datetime.fromisoformat(str(row["due_at"])),
                status=AssignmentStatus(str(row["status"])),
                priority=PriorityLevel(str(row["priority"])),
            )
            for row in rows
        )

    @staticmethod
    def _events(
        connection: sqlite3.Connection,
        scope: SyncScope | None,
        range_start: date,
        range_end: date,
    ) -> tuple[DashboardEventRecord, ...]:
        query = """
            SELECT e.id, e.title, e.starts_at, e.event_type, c.code, c.name
            FROM academic_events e LEFT JOIN courses c ON c.id = e.course_id
            WHERE e.is_missing = 0 AND date(e.starts_at) BETWEEN ? AND ?
        """
        parameters: tuple[str, ...] = (range_start.isoformat(), range_end.isoformat())
        if scope:
            query += " AND e.source_id = ? AND e.institution = ? AND e.semester = ?"
            parameters += (scope.source_id, scope.institution, scope.semester)
        query += " ORDER BY e.starts_at, e.id"
        rows = connection.execute(query, parameters).fetchall()
        return tuple(
            DashboardEventRecord(
                id=int(row["id"]),
                title=str(row["title"]),
                starts_at=datetime.fromisoformat(str(row["starts_at"])),
                event_type=EventType(str(row["event_type"])),
                course_code=str(row["code"]) if row["code"] is not None else None,
                course_name=str(row["name"]) if row["name"] is not None else None,
            )
            for row in rows
        )

    @staticmethod
    def _recent_import(row: sqlite3.Row | None, scope: SyncScope | None) -> RecentImportRecord | None:
        if row is None or scope is None:
            return None
        return RecentImportRecord(
            scope=scope,
            synchronized_at=datetime.fromisoformat(str(row["synchronized_at"])),
            added_count=int(row["added_count"]),
            updated_count=int(row["updated_count"]),
            unchanged_count=int(row["unchanged_count"]),
            missing_count=int(row["missing_count"]),
            ambiguous_count=int(row["ambiguous_count"]),
        )
