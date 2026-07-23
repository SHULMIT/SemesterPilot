from __future__ import annotations

from pathlib import Path

import pytest

import app
from semester_pilot.domain import EventType
from semester_pilot.application.calendar.models import MatchStrategy
from semester_pilot.infrastructure.calendar_import import create_open_university_import_service

FIXTURES = Path(__file__).parents[1] / "fixtures" / "calendars"


def _preview(name: str):
    text = (FIXTURES / name).read_text(encoding="utf-8")
    return create_open_university_import_service().preview(text)


def test_normal_anonymized_import_builds_preview() -> None:
    preview = _preview("normal.ics")

    assert len(preview.events) == 4
    assert len(preview.courses) == 1
    assert preview.courses[0].code == "12345"
    assert len(preview.assignments) == 1
    assert preview.assignments[0].number == "01"
    assert {event.event_type for event in preview.events} == {
        EventType.ASSIGNMENT_DEADLINE,
        EventType.LESSON,
        EventType.EXAM_REGISTRATION,
        EventType.UNKNOWN,
    }
    assert preview.unknown_event_indexes == (4,)
    assert preview.warnings == ()
    assert preview.safety.is_complete is True
    assert preview.safety.can_synchronize is True


def test_duplicate_event_is_detected_by_uid() -> None:
    preview = _preview("duplicate.ics")

    assert len(preview.potential_duplicates) == 1
    assert preview.potential_duplicates[0].strategy is MatchStrategy.UID
    assert preview.safety.can_synchronize is False
    assert preview.safety.blocking_reasons == ("unresolved-duplicates",)


def test_duplicate_without_uid_is_detected_by_exact_fingerprint() -> None:
    text = (FIXTURES / "duplicate.ics").read_text(encoding="utf-8")
    text = "\n".join(line for line in text.splitlines() if not line.startswith("UID:"))

    preview = create_open_university_import_service().preview(text)

    assert preview.potential_duplicates[0].strategy is MatchStrategy.CONTENT_HASH


def test_changed_duplicate_without_uid_is_detected_by_fallback() -> None:
    text = (FIXTURES / "duplicate.ics").read_text(encoding="utf-8")
    text = "\n".join(line for line in text.splitlines() if not line.startswith("UID:"))
    text = text.replace("DTSTART;VALUE=DATE:20270815", "DTSTART;VALUE=DATE:20270822", 1)
    text = text.replace('מועד אחרון להגשת ממ"ן', "מטלה 01 — שם חדש", 1)

    preview = create_open_university_import_service().preview(text)

    assert preview.events[0].identity.content_hash != preview.events[1].identity.content_hash
    assert preview.potential_duplicates[0].strategy is MatchStrategy.STABLE_KEY


def test_duplicate_import_produces_stable_identities() -> None:
    first = _preview("normal.ics")
    second = _preview("normal.ics")

    assert [event.identity for event in first.events] == [event.identity for event in second.events]


def test_changed_deadline_keeps_uid_and_fallback_but_changes_fingerprint() -> None:
    original = _preview("missing_event.ics").events[0]
    changed = _preview("changed_deadline.ics").events[0]

    assert original.identity.uid == changed.identity.uid
    assert original.identity.stable_key == changed.identity.stable_key
    assert original.identity.content_hash != changed.identity.content_hash


def test_renamed_assignment_keeps_uid_and_fallback_but_changes_fingerprint() -> None:
    original = _preview("missing_event.ics").events[0]
    renamed = _preview("renamed_assignment.ics").events[0]

    assert renamed.assignment is not None
    assert renamed.assignment.number == "01"
    assert original.identity.uid == renamed.identity.uid
    assert original.identity.stable_key == renamed.identity.stable_key
    assert original.identity.content_hash != renamed.identity.content_hash


def test_missing_event_fixture_exposes_current_identity_set_without_syncing() -> None:
    complete = _preview("normal.ics")
    current = _preview("missing_event.ics")
    complete_uids = {event.identity.uid for event in complete.events}
    current_uids = {event.identity.uid for event in current.events}

    assert current_uids < complete_uids
    assert len(complete_uids - current_uids) == 3


def test_malformed_event_warns_and_valid_event_still_imports() -> None:
    preview = _preview("malformed.ics")

    assert len(preview.events) == 1
    assert preview.events[0].identity.uid == "valid-after-broken@example.edu"
    assert {warning.code for warning in preview.warnings} == {"malformed-property", "invalid-dtstart"}
    assert preview.safety.is_complete is False
    assert preview.safety.can_synchronize is False
    assert preview.safety.blocking_reasons == ("incomplete-snapshot",)


def test_unknown_event_is_retained_for_review() -> None:
    preview = _preview("unknown.ics")

    assert len(preview.events) == 1
    assert preview.events[0].event_type is EventType.UNKNOWN
    assert preview.unknown_event_indexes == (1,)
    assert preview.safety.can_synchronize is True


def test_recurrence_id_prevents_instances_with_shared_uid_from_colliding() -> None:
    text = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:weekly-lesson@example.edu
RECURRENCE-ID;TZID=Asia/Jerusalem:20270801T180000
DTSTART;TZID=Asia/Jerusalem:20270801T180000
SUMMARY:מפגש
END:VEVENT
BEGIN:VEVENT
UID:weekly-lesson@example.edu
RECURRENCE-ID;TZID=Asia/Jerusalem:20270808T180000
DTSTART;TZID=Asia/Jerusalem:20270808T180000
SUMMARY:מפגש
END:VEVENT
END:VCALENDAR
"""

    preview = create_open_university_import_service().preview(text)

    assert len(preview.events) == 2
    assert preview.events[0].event.recurrence_id is not None
    assert preview.events[0].identity.canonical_key != preview.events[1].identity.canonical_key
    assert preview.potential_duplicates == ()
    assert preview.safety.can_synchronize is True


def test_legacy_tuple_adapter_uses_new_parser() -> None:
    text = (FIXTURES / "normal.ics").read_text(encoding="utf-8")

    assert app.parse_ics(text) == [("12345", "מבוא למערכות מידע", "01", "2027-08-15")]


def test_supplied_open_university_calendar_is_supported() -> None:
    source = Path(app.__file__).with_name("open_university_calendar.ics")
    if not source.exists():
        pytest.skip("The private legacy calendar is not available")

    preview = create_open_university_import_service().preview(source.read_text(encoding="utf-8-sig", errors="replace"))

    assert len(preview.events) > 0
    assert len(preview.assignments) > 0
    assert all(assignment.course is not None for assignment in preview.assignments)
