from __future__ import annotations

import pytest

from semester_pilot.application.subtask_management import StaleSubtaskError
from semester_pilot.infrastructure.database import SQLiteDatabase
from semester_pilot.infrastructure.migrations import SQLiteMigrator
from semester_pilot.infrastructure.subtask_management import SQLiteSubtaskRepository


def _setup(tmp_path):
    database = SQLiteDatabase(tmp_path / "synthetic.db")
    SQLiteMigrator(database).migrate()
    with database.connection() as connection:
        course = connection.execute("INSERT INTO courses(code,name) VALUES('SYN-1','Synthetic course')").lastrowid
        assignment = connection.execute(
            "INSERT INTO assignments(course_id,number,due_date) VALUES(?,'1','2027-01-01')", (course,)
        ).lastrowid
    assert assignment is not None
    return database, int(assignment)


def test_persistence_ordering_concurrency_and_parent_progress_isolation(tmp_path) -> None:
    database, assignment_id = _setup(tmp_path)
    repository = SQLiteSubtaskRepository(database)
    first = repository.create(assignment_id, "First", "", 10)
    second = repository.create(assignment_id, "Second", "", None)
    repository.move(second.id, second.version, -1)
    assert [x.title for x in repository.list_for_assignment(assignment_id)] == ["Second", "First"]
    completed = repository.set_completed(first.id, first.version + 1, True)
    with pytest.raises(StaleSubtaskError):
        repository.update(first.id, first.version, "stale", "", None)
    with database.connect() as connection:
        progress = connection.execute(
            "SELECT progress_percentage FROM assignments WHERE id=?", (assignment_id,)
        ).fetchone()[0]
    assert completed.completed is True
    assert progress == 0
    repository.delete(
        second.id,
        second.version + 1,
    )
    assert [(x.position, x.title) for x in repository.list_for_assignment(assignment_id)] == [(0, "First")]
