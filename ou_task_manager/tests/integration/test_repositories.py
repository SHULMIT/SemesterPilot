from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from semester_pilot.application.repositories import AssignmentRepository, CourseRepository
from semester_pilot.domain import Assignment, AssignmentStatus, Course, PriorityLevel
from semester_pilot.infrastructure.database import SQLiteDatabase
from semester_pilot.infrastructure.migrations import SQLiteMigrator
from semester_pilot.infrastructure.repositories import SQLiteAssignmentRepository, SQLiteCourseRepository


def _repositories(path: Path) -> tuple[CourseRepository, AssignmentRepository]:
    database = SQLiteDatabase(path)
    SQLiteMigrator(database).migrate()
    return SQLiteCourseRepository(database), SQLiteAssignmentRepository(database)


def test_course_crud_archive_and_restart_persistence(tmp_path: Path) -> None:
    path = tmp_path / "courses.db"
    courses, _ = _repositories(path)

    created = courses.create(Course(code="101", name="Original", semester="2027A"))
    assert created.id is not None
    course_id = created.id
    courses.update(replace(created, name="Updated"))

    reopened_courses, _ = _repositories(path)
    persisted = reopened_courses.get(course_id)
    assert persisted is not None
    assert persisted.name == "Updated"
    assert persisted.semester == "2027A"

    archived = reopened_courses.archive(course_id)
    assert archived is not None
    assert archived.is_archived
    assert reopened_courses.list_active() == []
    assert reopened_courses.get(course_id) is not None


def test_assignment_crud_archive_and_restart_persistence(tmp_path: Path) -> None:
    path = tmp_path / "assignments.db"
    courses, assignments = _repositories(path)
    course = courses.create(Course(code="101", name="Test course"))
    assert course.id is not None
    created = assignments.create(
        Assignment(
            course_id=course.id,
            number="01",
            title="First assignment",
            description="Read and answer",
            due_at=datetime(2027, 1, 10, 23, 59),
            estimated_minutes=180,
            notes="Initial note",
        )
    )
    assert created.id is not None
    assignment_id = created.id

    assignments.update(
        replace(
            created,
            status=AssignmentStatus.SUBMITTED,
            priority=PriorityLevel.HIGH,
            actual_minutes=150,
            notes="Submitted",
            submitted_at=datetime(2027, 1, 8, 12, 0),
        )
    )

    _, reopened_assignments = _repositories(path)
    persisted = reopened_assignments.get(assignment_id)
    assert persisted is not None
    assert persisted.status is AssignmentStatus.SUBMITTED
    assert persisted.priority is PriorityLevel.HIGH
    assert persisted.notes == "Submitted"
    assert persisted.actual_minutes == 150
    assert reopened_assignments.list_active(course.id) == [persisted]

    archived = reopened_assignments.archive(assignment_id)
    assert archived is not None
    assert archived.is_archived
    assert reopened_assignments.list_active() == []
    assert reopened_assignments.get(assignment_id) is not None


def test_repositories_share_one_atomic_transaction(tmp_path: Path) -> None:
    path = tmp_path / "shared-transaction.db"
    database = SQLiteDatabase(path)
    SQLiteMigrator(database).migrate()

    with database.transaction() as connection:
        courses = SQLiteCourseRepository(database, connection)
        assignments = SQLiteAssignmentRepository(database, connection)
        course = courses.create(Course(code="101", name="Committed course"))
        assert course.id is not None
        assignments.create(
            Assignment(
                course_id=course.id,
                number="01",
                title="Committed assignment",
                due_at=datetime(2027, 1, 10),
            )
        )

    reopened_courses, reopened_assignments = _repositories(path)
    assert len(reopened_courses.list_active()) == 1
    assert len(reopened_assignments.list_active()) == 1

    with pytest.raises(RuntimeError, match="abort"):
        with database.transaction() as connection:
            courses = SQLiteCourseRepository(database, connection)
            assignments = SQLiteAssignmentRepository(database, connection)
            course = courses.create(Course(code="202", name="Rolled back course"))
            assert course.id is not None
            assignments.create(
                Assignment(
                    course_id=course.id,
                    number="02",
                    title="Rolled back assignment",
                    due_at=datetime(2027, 2, 10),
                )
            )
            raise RuntimeError("abort")

    assert [course.code for course in reopened_courses.list_active()] == ["101"]
    assert len(reopened_assignments.list_active()) == 1
