from __future__ import annotations

from datetime import datetime

import pytest

from semester_pilot.application.calendar.classification import EventClassifier
from semester_pilot.application.calendar.extraction import AssignmentExtractor, CourseExtractor
from semester_pilot.application.calendar.fingerprints import FingerprintGenerator
from semester_pilot.application.calendar.matching import EventMatcher
from semester_pilot.application.calendar.models import (
    ClassificationRule,
    MatchStrategy,
    NormalizedCalendarEvent,
)
from semester_pilot.application.calendar.normalization import CalendarNormalizer
from semester_pilot.application.calendar.rules import OPEN_UNIVERSITY_HEBREW_RULES
from semester_pilot.domain import EventType
from semester_pilot.infrastructure.ics_parser import IcsCalendarParser


def _event(
    *,
    title: str = 'מועד אחרון להגשת ממ"ן',
    description: str = "קורס מבוא למערכות מידע (12345) בסמסטר א2027 מטלה 01",
    starts_at: datetime = datetime(2027, 8, 15),
    uid: str | None = "assignment@example.edu",
) -> NormalizedCalendarEvent:
    return NormalizedCalendarEvent(
        source_index=1,
        uid=uid,
        recurrence_id=None,
        title=title,
        description=description,
        location="",
        starts_at=starts_at,
        ends_at=None,
        is_all_day=True,
    )


def test_parser_unfolds_lines_and_preserves_parameters() -> None:
    result = IcsCalendarParser().parse(
        "BEGIN:VCALENDAR\r\n"
        "BEGIN:VEVENT\r\n"
        "DTSTART;TZID=Asia/Jerusalem:20270801T180000\r\n"
        "SUMMARY:Long summary that is\r\n"
        " folded\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )

    assert len(result.events) == 1
    assert result.events[0].first("SUMMARY").value == "Long summary that isfolded"  # type: ignore[union-attr]
    assert result.events[0].first("DTSTART").parameters["TZID"] == "Asia/Jerusalem"  # type: ignore[union-attr]


def test_normalizer_supports_all_day_utc_tzid_and_floating_dates() -> None:
    text = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART;VALUE=DATE:20270801
SUMMARY:All day
END:VEVENT
BEGIN:VEVENT
DTSTART:20270801T120000Z
SUMMARY:UTC
END:VEVENT
BEGIN:VEVENT
DTSTART;TZID=Europe/Paris:20270801T120000
SUMMARY:Paris
END:VEVENT
BEGIN:VEVENT
DTSTART:20270801T120000
SUMMARY:Floating
END:VEVENT
END:VCALENDAR
"""
    result = CalendarNormalizer().normalize(IcsCalendarParser().parse(text))

    assert len(result.events) == 4
    assert result.events[0].is_all_day is True
    assert str(result.events[1].starts_at.tzinfo) == "UTC"
    assert str(result.events[2].starts_at.tzinfo) == "UTC"
    assert result.events[2].starts_at.hour == 10
    assert str(result.events[3].starts_at.tzinfo) == "UTC"
    assert result.events[3].starts_at.hour == 9


def test_classifier_uses_injected_profiles() -> None:
    english_classifier = EventClassifier((ClassificationRule(EventType.LESSON, (r"\blecture\b",), ("title",)),))

    assert english_classifier.classify(_event(title="Guest lecture")) is EventType.LESSON
    assert english_classifier.classify(_event(title="Student gathering")) is EventType.UNKNOWN
    assert EventClassifier(OPEN_UNIVERSITY_HEBREW_RULES).classify(_event()) is EventType.ASSIGNMENT_DEADLINE


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ('מועד אחרון להגשת ממ"ן', EventType.ASSIGNMENT_DEADLINE),
        ("מפגש בהנחיה מקוונת", EventType.LESSON),
        ("בחינת גמר", EventType.EXAM),
        ("הרשמה לבחינת גמר", EventType.EXAM_REGISTRATION),
        ("התחלת סמסטר", EventType.SEMESTER_START),
        ("סיום סמסטר", EventType.SEMESTER_END),
        ("מועד אחרון להרשמה", EventType.REGISTRATION_DEADLINE),
        ("יום אקדמי", EventType.GENERAL_ACADEMIC),
        ("יריד מועדונים", EventType.UNKNOWN),
    ],
)
def test_open_university_profile_covers_supported_event_types(title: str, expected: EventType) -> None:
    classifier = EventClassifier(OPEN_UNIVERSITY_HEBREW_RULES)

    assert classifier.classify(_event(title=title, description="")) is expected


def test_extractors_have_separate_course_and_assignment_responsibilities() -> None:
    event = _event()
    course = CourseExtractor().extract(event)
    assignment = AssignmentExtractor().extract(event, course)

    assert course is not None
    assert course.code == "12345"
    assert course.name == "מבוא למערכות מידע"
    assert course.semester == "א2027"
    assert assignment is not None
    assert assignment.number == "01"
    assert assignment.course == course


def test_fingerprint_identity_uses_uid_exact_content_and_fallback() -> None:
    generator = FingerprintGenerator()
    course = CourseExtractor().extract(_event())
    assignment = AssignmentExtractor().extract(_event(), course)
    original = generator.generate("source-a", _event(), EventType.ASSIGNMENT_DEADLINE, course, assignment)

    changed_event = _event(title="מטלה 01 — שם חדש", starts_at=datetime(2027, 8, 22))
    changed_assignment = AssignmentExtractor().extract(changed_event, course)
    changed = generator.generate("source-a", changed_event, EventType.ASSIGNMENT_DEADLINE, course, changed_assignment)

    assert original.uid == changed.uid
    assert original.content_hash != changed.content_hash
    assert original.stable_key == changed.stable_key
    assert "מועד" not in original.stable_key


def test_matching_is_source_scoped_and_recurrence_aware() -> None:
    generator = FingerprintGenerator()
    matcher = EventMatcher()
    event = _event()
    course = CourseExtractor().extract(event)
    assignment = AssignmentExtractor().extract(event, course)
    source_a = generator.generate("source-a", event, EventType.ASSIGNMENT_DEADLINE, course, assignment)
    source_b = generator.generate("source-b", event, EventType.ASSIGNMENT_DEADLINE, course, assignment)
    recurrence = event.__class__(
        source_index=event.source_index,
        uid=event.uid,
        recurrence_id=datetime(2027, 8, 16),
        title=event.title,
        description=event.description,
        location=event.location,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        is_all_day=event.is_all_day,
    )
    recurring_identity = generator.generate("source-a", recurrence, EventType.ASSIGNMENT_DEADLINE, course, assignment)

    assert matcher.match(source_a, source_b) is None
    assert matcher.match(source_a, recurring_identity) is None
    assert source_a.canonical_key != recurring_identity.canonical_key
    assert matcher.match(source_a, source_a) is MatchStrategy.UID
