from semester_pilot.application.calendar import (
    AssignmentExtractor,
    CalendarImportService,
    CalendarNormalizer,
    CourseExtractor,
    EventClassifier,
    EventMatcher,
    FingerprintGenerator,
)
from semester_pilot.application.calendar.rules import OPEN_UNIVERSITY_HEBREW_RULES
from semester_pilot.infrastructure.ics_parser import IcsCalendarParser


def create_open_university_import_service(
    source_id: str = "open-university-hebrew-calendar",
) -> CalendarImportService:
    """Compose the initial Hebrew Open University calendar profile."""
    return CalendarImportService(
        parser=IcsCalendarParser(),
        normalizer=CalendarNormalizer(default_timezone="Asia/Jerusalem"),
        classifier=EventClassifier(OPEN_UNIVERSITY_HEBREW_RULES),
        course_extractor=CourseExtractor(),
        assignment_extractor=AssignmentExtractor(),
        fingerprint_generator=FingerprintGenerator(),
        event_matcher=EventMatcher(),
        source_id=source_id,
    )
