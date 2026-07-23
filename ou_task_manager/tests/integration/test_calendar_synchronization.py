from __future__ import annotations

from pathlib import Path

import pytest

from semester_pilot.application.synchronization import CalendarSyncService, SyncScope
from semester_pilot.application.synchronization.models import SynchronizationHistory
from semester_pilot.application.synchronization.ports import SynchronizationHistoryRepository
from semester_pilot.infrastructure.calendar_import import create_open_university_import_service
from semester_pilot.infrastructure.database import SQLiteDatabase
from semester_pilot.infrastructure.migrations import SQLiteMigrator
from semester_pilot.infrastructure.synchronization import SQLiteCalendarSyncUnitOfWork
from semester_pilot.infrastructure.subtask_management import SQLiteSubtaskRepository

FIXTURES = Path(__file__).parents[1] / "fixtures" / "calendars"
SOURCE = "open-university-hebrew-calendar"
SCOPE = SyncScope(SOURCE, "Open University", "2027")


class _FailingHistoryRepository:
    def __init__(self, delegate: SynchronizationHistoryRepository) -> None:
        self._delegate = delegate

    def create(self, history: SynchronizationHistory) -> SynchronizationHistory:
        self._delegate.create(history)
        raise RuntimeError("injected history failure")


class _FailingHistoryUnitOfWork(SQLiteCalendarSyncUnitOfWork):
    def __enter__(self) -> _FailingHistoryUnitOfWork:
        super().__enter__()
        self.history = _FailingHistoryRepository(self.history)
        return self


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _preview(name: str, source_id: str = SOURCE):
    return create_open_university_import_service(source_id).preview(_text(name))


def _setup(tmp_path: Path) -> tuple[SQLiteDatabase, CalendarSyncService]:
    database = SQLiteDatabase(tmp_path / "sync.db")
    SQLiteMigrator(database).migrate()
    service = CalendarSyncService(lambda: SQLiteCalendarSyncUnitOfWork(database))
    return database, service


def _count(database: SQLiteDatabase, table: str) -> int:
    with database.connect() as connection:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def test_initial_sync_and_identical_reimport_are_idempotent(tmp_path: Path) -> None:
    database, service = _setup(tmp_path)

    first = service.synchronize(_preview("normal.ics"), SCOPE)
    with database.connect() as connection:
        initial_timestamps = connection.execute("SELECT updated_at FROM academic_events ORDER BY id").fetchall()
        initial_assignment_timestamp = connection.execute("SELECT updated_at FROM assignments").fetchone()[0]
    second = service.synchronize(_preview("normal.ics"), SCOPE)

    assert len(first.added) == 4
    assert len(second.unchanged) == 4
    assert not second.added and not second.updated and not second.missing
    assert _count(database, "academic_events") == 4
    assert _count(database, "assignments") == 1
    assert _count(database, "synchronization_history") == 2
    with database.connect() as connection:
        second_timestamps = connection.execute("SELECT updated_at FROM academic_events ORDER BY id").fetchall()
        second_assignment_timestamp = connection.execute("SELECT updated_at FROM assignments").fetchone()[0]
    assert second_timestamps == initial_timestamps
    assert second_assignment_timestamp == initial_assignment_timestamp


@pytest.mark.parametrize("fixture", ["changed_deadline.ics", "renamed_assignment.ics"])
def test_source_changes_update_existing_assignment_without_duplication(tmp_path: Path, fixture: str) -> None:
    database, service = _setup(tmp_path)
    service.synchronize(_preview("missing_event.ics"), SCOPE)

    result = service.synchronize(_preview(fixture), SCOPE)

    assert len(result.updated) == 1
    assert _count(database, "academic_events") == 1
    assert _count(database, "assignments") == 1


def test_calendar_updates_preserve_student_owned_assignment_fields(tmp_path: Path) -> None:
    database, service = _setup(tmp_path)
    service.synchronize(_preview("missing_event.ics"), SCOPE)
    with database.connection() as connection:
        connection.execute(
            """
            UPDATE assignments SET notes = 'personal', status = 'IN_PROGRESS',
                priority = 'URGENT', estimated_minutes = 90, actual_minutes = 25
            """
        )

    service.synchronize(_preview("changed_deadline.ics"), SCOPE)

    with database.connect() as connection:
        assignment = connection.execute("SELECT * FROM assignments").fetchone()
    assert assignment["notes"] == "personal"
    assert assignment["status"] == "IN_PROGRESS"
    assert assignment["priority"] == "URGENT"
    assert assignment["estimated_minutes"] == 90
    assert assignment["actual_minutes"] == 25


def test_calendar_synchronization_preserves_user_owned_subtasks(tmp_path: Path) -> None:
    database, service = _setup(tmp_path)
    service.synchronize(_preview("missing_event.ics"), SCOPE)
    with database.connect() as connection:
        assignment_id = int(connection.execute("SELECT id FROM assignments").fetchone()[0])
    repository = SQLiteSubtaskRepository(database)
    created = repository.create(assignment_id, "Synthetic private step", "Synthetic notes", 25)

    service.synchronize(_preview("changed_deadline.ics"), SCOPE)

    preserved = repository.get(created.id)
    assert preserved is not None
    assert (preserved.title, preserved.notes, preserved.estimated_minutes, preserved.version) == (
        "Synthetic private step",
        "Synthetic notes",
        25,
        1,
    )


def test_missing_events_are_reversible_and_unsafe_snapshot_cannot_mark_missing(
    tmp_path: Path,
) -> None:
    database, service = _setup(tmp_path)
    service.synchronize(_preview("normal.ics"), SCOPE)

    missing = service.synchronize(_preview("missing_event.ics"), SCOPE)
    skipped = service.synchronize(_preview("malformed.ics"), SCOPE)
    restored = service.synchronize(_preview("normal.ics"), SCOPE)

    assert len(missing.missing) == 3
    assert skipped.was_skipped
    assert len(restored.updated) >= 3
    with database.connect() as connection:
        missing_count = connection.execute("SELECT COUNT(*) FROM academic_events WHERE is_missing = 1").fetchone()[0]
    assert missing_count == 0
    assert _count(database, "synchronization_history") == 3


def test_metadata_change_updates_source_fields(tmp_path: Path) -> None:
    database, service = _setup(tmp_path)
    original = _text("missing_event.ics")
    service.synchronize(create_open_university_import_service().preview(original), SCOPE)
    changed = original.replace(
        "DTSTART;VALUE=DATE:20270815",
        "DTSTART;VALUE=DATE:20270815\nLOCATION:Building 2\nSEQUENCE:4",
    )

    result = service.synchronize(create_open_university_import_service().preview(changed), SCOPE)

    assert len(result.updated) == 1
    with database.connect() as connection:
        event = connection.execute("SELECT location, sequence FROM academic_events").fetchone()
    assert event["location"] == "Building 2"
    assert event["sequence"] == 4


def test_weak_fallback_is_reported_as_ambiguous_without_merging(tmp_path: Path) -> None:
    database, service = _setup(tmp_path)
    service.synchronize(_preview("missing_event.ics"), SCOPE)
    changed_without_uid = "\n".join(
        line for line in _text("renamed_assignment.ics").splitlines() if not line.startswith("UID:")
    )

    result = service.synchronize(create_open_university_import_service().preview(changed_without_uid), SCOPE)

    assert len(result.ambiguous) == 1
    assert result.ambiguous[0].match_type == "stable_key"
    assert not result.added and not result.updated and not result.missing
    assert _count(database, "academic_events") == 1


def test_source_and_semester_scopes_are_isolated(tmp_path: Path) -> None:
    database, service = _setup(tmp_path)
    service.synchronize(_preview("missing_event.ics"), SCOPE)
    other_semester = SyncScope(SOURCE, "Open University", "2028")
    service.synchronize(_preview("missing_event.ics"), other_semester)
    other_source = "other-university"
    service.synchronize(
        _preview("missing_event.ics", other_source),
        SyncScope(other_source, "Other University", "2027"),
    )

    assert _count(database, "academic_events") == 3
    assert _count(database, "assignments") == 3
    assert _count(database, "courses") == 3


def test_recurrence_instances_with_shared_uid_remain_distinct(tmp_path: Path) -> None:
    database, service = _setup(tmp_path)
    text = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:weekly@example.edu
RECURRENCE-ID;TZID=Asia/Jerusalem:20270801T180000
DTSTART;TZID=Asia/Jerusalem:20270801T180000
SUMMARY:מפגש
END:VEVENT
BEGIN:VEVENT
UID:weekly@example.edu
RECURRENCE-ID;TZID=Asia/Jerusalem:20270808T180000
DTSTART;TZID=Asia/Jerusalem:20270808T180000
SUMMARY:מפגש
END:VEVENT
END:VCALENDAR
"""

    result = service.synchronize(create_open_university_import_service().preview(text), SCOPE)

    assert len(result.added) == 2
    assert _count(database, "academic_events") == 2


def test_exact_fingerprint_matches_uidless_reimport(tmp_path: Path) -> None:
    database, service = _setup(tmp_path)
    text = "\n".join(line for line in _text("missing_event.ics").splitlines() if not line.startswith("UID:"))
    preview = create_open_university_import_service().preview(text)

    first = service.synchronize(preview, SCOPE)
    second = service.synchronize(preview, SCOPE)

    assert len(first.added) == 1
    assert len(second.unchanged) == 1
    assert _count(database, "academic_events") == 1


def test_different_uids_with_similar_content_do_not_merge(tmp_path: Path) -> None:
    database, service = _setup(tmp_path)
    original = _text("unknown.ics")
    service.synchronize(create_open_university_import_service().preview(original), SCOPE)
    changed_uid = original.replace("unknown-02@example.edu", "another-event@example.edu")

    result = service.synchronize(create_open_university_import_service().preview(changed_uid), SCOPE)

    assert len(result.added) == 1
    assert len(result.missing) == 1
    assert _count(database, "academic_events") == 2


def test_unknown_events_are_synchronized_for_later_review(tmp_path: Path) -> None:
    database, service = _setup(tmp_path)

    result = service.synchronize(_preview("unknown.ics"), SCOPE)

    assert len(result.added) == 1
    with database.connect() as connection:
        event_type = connection.execute("SELECT event_type FROM academic_events").fetchone()[0]
    assert event_type == "UNKNOWN"


def test_history_failure_rolls_back_the_entire_synchronization(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "rollback.db")
    SQLiteMigrator(database).migrate()
    service = CalendarSyncService(lambda: _FailingHistoryUnitOfWork(database))

    with pytest.raises(RuntimeError, match="injected history failure"):
        service.synchronize(_preview("normal.ics"), SCOPE)

    assert _count(database, "courses") == 0
    assert _count(database, "assignments") == 0
    assert _count(database, "academic_events") == 0
    assert _count(database, "synchronization_history") == 0
