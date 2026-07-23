from __future__ import annotations

import sqlite3
from datetime import datetime

from semester_pilot.application.subtask_management import StaleSubtaskError, Subtask, SubtaskNotFoundError
from semester_pilot.infrastructure.database import SQLiteDatabase


class SQLiteSubtaskRepository:
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def list_for_assignment(self, assignment_id: int) -> tuple[Subtask, ...]:
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM subtasks WHERE assignment_id = ? ORDER BY position, id", (assignment_id,)
            ).fetchall()
        return tuple(self._map(row) for row in rows)

    def get(self, subtask_id: int) -> Subtask | None:
        with self._database.connect() as connection:
            row = connection.execute("SELECT * FROM subtasks WHERE id = ?", (subtask_id,)).fetchone()
        return self._map(row) if row else None

    def create(self, assignment_id: int, title: str, notes: str, estimated_minutes: int | None) -> Subtask:
        now = datetime.now().astimezone().isoformat()
        with self._database.connection() as connection:
            position = int(
                connection.execute(
                    "SELECT COALESCE(MAX(position) + 1, 0) FROM subtasks WHERE assignment_id = ?", (assignment_id,)
                ).fetchone()[0]
            )
            cursor = connection.execute(
                "INSERT INTO subtasks(assignment_id,title,notes,completed,estimated_minutes,position,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (assignment_id, title, notes, 0, estimated_minutes, position, now, now),
            )
        if cursor.lastrowid is None:
            raise RuntimeError("SQLite did not return a subtask id")
        return self._required(int(cursor.lastrowid))

    def update(self, subtask_id: int, version: int, title: str, notes: str, estimated_minutes: int | None) -> Subtask:
        self._write(
            "UPDATE subtasks SET title=?,notes=?,estimated_minutes=?,updated_at=?,version=version+1 WHERE id=? AND version=?",
            (title, notes, estimated_minutes, datetime.now().astimezone().isoformat(), subtask_id, version),
            subtask_id,
        )
        return self._required(subtask_id)

    def set_completed(self, subtask_id: int, version: int, completed: bool) -> Subtask:
        self._write(
            "UPDATE subtasks SET completed=?,updated_at=?,version=version+1 WHERE id=? AND version=?",
            (int(completed), datetime.now().astimezone().isoformat(), subtask_id, version),
            subtask_id,
        )
        return self._required(subtask_id)

    def move(self, subtask_id: int, version: int, direction: int) -> tuple[Subtask, ...]:
        now = datetime.now().astimezone().isoformat()
        with self._database.connection() as connection:
            current = connection.execute(
                "SELECT * FROM subtasks WHERE id=? AND version=?", (subtask_id, version)
            ).fetchone()
            if current is None:
                self._raise_missing_or_stale(connection, subtask_id)
            target = connection.execute(
                "SELECT * FROM subtasks WHERE assignment_id=? AND position=?",
                (current["assignment_id"], int(current["position"]) + direction),
            ).fetchone()
            if target is None:
                return self.list_for_assignment(int(current["assignment_id"]))
            temporary = int(
                connection.execute(
                    "SELECT MAX(position) + 1 FROM subtasks WHERE assignment_id=?", (current["assignment_id"],)
                ).fetchone()[0]
            )
            connection.execute("UPDATE subtasks SET position=? WHERE id=?", (temporary, subtask_id))
            connection.execute(
                "UPDATE subtasks SET position=?,updated_at=?,version=version+1 WHERE id=?",
                (current["position"], now, target["id"]),
            )
            connection.execute(
                "UPDATE subtasks SET position=?,updated_at=?,version=version+1 WHERE id=?",
                (target["position"], now, subtask_id),
            )
            assignment_id = int(current["assignment_id"])
        return self.list_for_assignment(assignment_id)

    def delete(self, subtask_id: int, version: int) -> int:
        with self._database.connection() as connection:
            row = connection.execute(
                "SELECT assignment_id,position FROM subtasks WHERE id=? AND version=?", (subtask_id, version)
            ).fetchone()
            if row is None:
                self._raise_missing_or_stale(connection, subtask_id)
            connection.execute("DELETE FROM subtasks WHERE id=?", (subtask_id,))
            connection.execute(
                "UPDATE subtasks SET position=position-1,version=version+1,updated_at=? WHERE assignment_id=? AND position>?",
                (datetime.now().astimezone().isoformat(), row["assignment_id"], row["position"]),
            )
            return int(row["assignment_id"])

    def _write(self, sql: str, values: tuple[object, ...], subtask_id: int) -> None:
        with self._database.connection() as connection:
            cursor = connection.execute(sql, values)
            if cursor.rowcount == 0:
                self._raise_missing_or_stale(connection, subtask_id)

    def _required(self, subtask_id: int) -> Subtask:
        item = self.get(subtask_id)
        if item is None:
            raise SubtaskNotFoundError(f"Subtask {subtask_id} does not exist")
        return item

    @staticmethod
    def _raise_missing_or_stale(connection: sqlite3.Connection, subtask_id: int) -> None:
        if connection.execute("SELECT 1 FROM subtasks WHERE id=?", (subtask_id,)).fetchone():
            raise StaleSubtaskError("תת־המשימה השתנתה. יש לרענן ולנסות שוב.")
        raise SubtaskNotFoundError(f"Subtask {subtask_id} does not exist")

    @staticmethod
    def _map(row: sqlite3.Row) -> Subtask:
        return Subtask(
            int(row["id"]),
            int(row["assignment_id"]),
            str(row["title"]),
            str(row["notes"]),
            bool(row["completed"]),
            int(row["estimated_minutes"]) if row["estimated_minutes"] is not None else None,
            int(row["position"]),
            datetime.fromisoformat(str(row["created_at"])),
            datetime.fromisoformat(str(row["updated_at"])),
            int(row["version"]),
        )
