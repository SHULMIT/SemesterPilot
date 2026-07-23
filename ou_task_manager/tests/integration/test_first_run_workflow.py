from __future__ import annotations

from pathlib import Path

import pytest

from semester_pilot.application.import_workflow import (
    CalendarImportWorkflowService,
    CalendarWorkflowError,
    WorkflowErrorCode,
)
from semester_pilot.application.synchronization import CalendarSyncService
from semester_pilot.infrastructure.calendar_import import create_open_university_import_service
from semester_pilot.infrastructure.database import SQLiteDatabase
from semester_pilot.infrastructure.migrations import SQLiteMigrator
from semester_pilot.infrastructure.synchronization import SQLiteCalendarSyncUnitOfWork

FIXTURES = Path(__file__).parents[1] / "fixtures" / "calendars"


def _workflow(tmp_path: Path) -> tuple[SQLiteDatabase, CalendarImportWorkflowService]:
    database = SQLiteDatabase(tmp_path / "first-run.db")
    SQLiteMigrator(database).migrate()
    sync = CalendarSyncService(lambda: SQLiteCalendarSyncUnitOfWork(database))
    return database, CalendarImportWorkflowService(
        create_open_university_import_service(), sync, "Open University of Israel"
    )


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _count(database: SQLiteDatabase, table: str) -> int:
    with database.connect() as connection:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def test_first_run_preview_is_real_and_read_only_until_confirmation(tmp_path: Path) -> None:
    database, workflow = _workflow(tmp_path)

    prepared = workflow.prepare("semester.ics", _fixture("normal.ics"))

    assert prepared.summary.added == 4
    assert prepared.summary.updated == 0
    assert prepared.summary.unchanged == 0
    assert prepared.summary.is_safe
    assert _count(database, "academic_events") == 0
    assert _count(database, "synchronization_history") == 0

    completion = workflow.confirm(prepared)

    assert completion.total_processed == 4
    assert completion.summary.added == 4
    assert completion.elapsed_seconds >= 0
    assert _count(database, "academic_events") == 4
    assert _count(database, "synchronization_history") == 1


@pytest.mark.parametrize(
    ("filename", "content", "code"),
    [
        ("", "anything", WorkflowErrorCode.INVALID_FILE),
        ("calendar.txt", "BEGIN:VCALENDAR", WorkflowErrorCode.UNSUPPORTED_FORMAT),
        ("calendar.ics", None, WorkflowErrorCode.UNREADABLE_FILE),
        ("calendar.ics", "", WorkflowErrorCode.EMPTY_CALENDAR),
        ("calendar.ics", "not a calendar", WorkflowErrorCode.UNSUPPORTED_FORMAT),
        ("calendar.ics", "BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR", WorkflowErrorCode.EMPTY_CALENDAR),
    ],
)
def test_file_validation_is_friendly(
    tmp_path: Path, filename: str, content: str | None, code: WorkflowErrorCode
) -> None:
    _, workflow = _workflow(tmp_path)

    with pytest.raises(CalendarWorkflowError) as captured:
        workflow.prepare(filename, content)

    assert captured.value.code is code
    assert captured.value.user_message


class _ExplodingPreviewer:
    def preview(self, _text: str):
        raise ValueError("parser details that must not reach the UI")


def test_parser_failure_is_wrapped_in_a_friendly_error(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "parser.db")
    SQLiteMigrator(database).migrate()
    sync = CalendarSyncService(lambda: SQLiteCalendarSyncUnitOfWork(database))
    workflow = CalendarImportWorkflowService(_ExplodingPreviewer(), sync, "Open University")

    with pytest.raises(CalendarWorkflowError) as captured:
        workflow.prepare("calendar.ics", "BEGIN:VCALENDAR\nEND:VCALENDAR")

    assert captured.value.code is WorkflowErrorCode.PARSER_ERROR
    assert "parser details" not in captured.value.user_message


def test_unsafe_snapshot_can_be_previewed_but_not_confirmed(tmp_path: Path) -> None:
    database, workflow = _workflow(tmp_path)

    prepared = workflow.prepare("duplicate.ics", _fixture("duplicate.ics"))

    assert not prepared.summary.is_safe
    assert prepared.summary.skipped_reasons == ("unresolved-duplicates",)
    with pytest.raises(CalendarWorkflowError) as captured:
        workflow.confirm(prepared)
    assert captured.value.code is WorkflowErrorCode.UNSAFE_SNAPSHOT
    assert _count(database, "academic_events") == 0
    assert _count(database, "synchronization_history") == 0


def test_second_preview_reports_unchanged_events_from_existing_data(tmp_path: Path) -> None:
    _, workflow = _workflow(tmp_path)
    first = workflow.prepare("semester.ics", _fixture("normal.ics"))
    workflow.confirm(first)

    second = workflow.prepare("semester.ics", _fixture("normal.ics"))

    assert second.summary.added == 0
    assert second.summary.unchanged == 4


def test_multi_semester_calendar_imports_only_the_dominant_semester(tmp_path: Path) -> None:
    database, workflow = _workflow(tmp_path)
    mixed = _fixture("normal.ics").replace("א2027", "ב2026", 1)

    prepared = workflow.prepare("mixed-semesters.ics", mixed)

    assert prepared.scope.semester == "א2027"
    assert len(prepared.preview.events) == 2
    assert {course.semester for course in prepared.preview.courses} == {"א2027"}
    assert any(warning.code == "other-semesters-excluded" for warning in prepared.preview.warnings)
    assert prepared.summary.is_safe

    completion = workflow.confirm(prepared)
    assert completion.total_processed == 2
    with database.connect() as connection:
        semesters = {row[0] for row in connection.execute("SELECT semester FROM courses")}
    assert semesters == {"א2027"}


def test_real_preview_reports_updates_missing_and_ambiguous_matches(tmp_path: Path) -> None:
    _, workflow = _workflow(tmp_path)
    initial = workflow.prepare("initial.ics", _fixture("missing_event.ics"))
    workflow.confirm(initial)

    changed = workflow.prepare("changed.ics", _fixture("changed_deadline.ics"))
    assert changed.summary.updated == 1

    complete = workflow.prepare("complete.ics", _fixture("normal.ics"))
    workflow.confirm(complete)
    reduced = workflow.prepare("reduced.ics", _fixture("missing_event.ics"))
    assert reduced.summary.missing == 3

    renamed_without_uid = "\n".join(
        line for line in _fixture("renamed_assignment.ics").splitlines() if not line.startswith("UID:")
    )
    ambiguous = workflow.prepare("ambiguous.ics", renamed_without_uid)
    assert ambiguous.summary.ambiguous == 1
