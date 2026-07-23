from __future__ import annotations

from datetime import datetime

import pytest

from semester_pilot.application.assignment_management import PersonalAssignmentUpdate, StaleAssignmentError
from semester_pilot.domain.enums import AssignmentStatus, PriorityLevel
from semester_pilot.infrastructure.assignment_management import SQLiteManagedAssignmentRepository
from semester_pilot.infrastructure.database import SQLiteDatabase
from semester_pilot.infrastructure.migrations import SQLiteMigrator


def _database(tmp_path) -> tuple[SQLiteDatabase, int]:
    database = SQLiteDatabase(tmp_path / "assignments.db")
    SQLiteMigrator(database).migrate()
    now = "2027-08-01T10:00:00+03:00"
    with database.connection() as connection:
        course_id = connection.execute(
            "INSERT INTO courses(source_id, code, name, semester, institution, created_at, updated_at) "
            "VALUES('source', '10645', 'מבוא למחשבים', '2027A', 'University', ?, ?)",
            (now, now),
        ).lastrowid
        assignment_id = connection.execute(
            "INSERT INTO assignments(course_id, number, due_date, title, description, due_at, status, "
            "priority, source_fingerprint, created_at, updated_at) VALUES(?, '11', '2027-08-10', "
            "'ממ״ן 11', 'פרטי מקור', '2027-08-10T23:59:00+03:00', 'NOT_STARTED', 'NORMAL', 'fp', ?, ?)",
            (course_id, now, now),
        ).lastrowid
        connection.execute(
            "INSERT INTO academic_events(source_id, institution, semester, external_uid, stable_match_key, "
            "content_hash, event_type, course_id, assignment_id, title, starts_at, location, created_at, updated_at) "
            "VALUES('source', 'University', '2027A', 'uid-11', 'key', 'hash', 'ASSIGNMENT_DEADLINE', ?, ?, "
            "'ממ״ן 11', '2027-08-10T23:59:00+03:00', 'מקוון', ?, ?)",
            (course_id, assignment_id, now, now),
        )
        connection.execute(
            "INSERT INTO synchronization_history(source_id, institution, semester, synchronized_at, added_count, "
            "updated_count, unchanged_count, missing_count, ambiguous_count) VALUES('source', 'University', "
            "'2027A', ?, 1, 0, 0, 0, 0)",
            (now,),
        )
    assert assignment_id is not None
    return database, int(assignment_id)


def test_personal_update_preserves_imported_fields_and_detects_stale_edits(tmp_path) -> None:
    database, assignment_id = _database(tmp_path)
    repository = SQLiteManagedAssignmentRepository(database)
    before = repository.get(assignment_id)
    assert before is not None

    updated = repository.update_personal_fields(
        assignment_id,
        before.version,
        PersonalAssignmentUpdate(
            AssignmentStatus.IN_PROGRESS,
            PriorityLevel.HIGH,
            "הערה אישית",
            120,
            35,
            None,
        ),
    )

    assert (updated.title, updated.description, updated.due_at, updated.external_uid) == (
        before.title,
        before.description,
        before.due_at,
        before.external_uid,
    )
    assert (updated.notes, updated.progress_percentage, updated.version) == ("הערה אישית", 35, 2)
    with pytest.raises(StaleAssignmentError):
        repository.update_personal_fields(
            assignment_id,
            1,
            PersonalAssignmentUpdate(
                AssignmentStatus.WORK_COMPLETED,
                PriorityLevel.HIGH,
                "",
                None,
                100,
                datetime(2027, 8, 2),
            ),
        )


def test_missing_source_state_is_exposed_without_deleting_assignment(tmp_path) -> None:
    database, assignment_id = _database(tmp_path)
    with database.connection() as connection:
        connection.execute("UPDATE academic_events SET is_missing = 1 WHERE assignment_id = ?", (assignment_id,))
    record = SQLiteManagedAssignmentRepository(database).get(assignment_id)
    assert record is not None
    assert record.is_missing_from_source is True
