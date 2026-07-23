from __future__ import annotations

from semester_pilot.application.calendar.classification import EventClassifier
from semester_pilot.application.calendar.extraction import AssignmentExtractor, CourseExtractor
from semester_pilot.application.calendar.fingerprints import FingerprintGenerator
from semester_pilot.application.calendar.matching import EventMatcher
from semester_pilot.application.calendar.models import (
    CourseCandidate,
    DuplicateCandidate,
    ImportedEvent,
    ImportWarning,
    ImportPreview,
    SnapshotSafety,
    WarningSeverity,
)
from semester_pilot.application.calendar.normalization import CalendarNormalizer
from semester_pilot.application.calendar.ports import CalendarParser
from semester_pilot.domain.enums import EventType


class CalendarImportService:
    """Builds a persistence-free import preview from calendar source text."""

    def __init__(
        self,
        parser: CalendarParser,
        normalizer: CalendarNormalizer,
        classifier: EventClassifier,
        course_extractor: CourseExtractor,
        assignment_extractor: AssignmentExtractor,
        fingerprint_generator: FingerprintGenerator,
        event_matcher: EventMatcher,
        source_id: str,
    ) -> None:
        self._parser = parser
        self._normalizer = normalizer
        self._classifier = classifier
        self._course_extractor = course_extractor
        self._assignment_extractor = assignment_extractor
        self._fingerprint_generator = fingerprint_generator
        self._event_matcher = event_matcher
        self._source_id = source_id.strip()
        if not self._source_id:
            raise ValueError("Calendar source_id must not be empty")

    def preview(self, text: str) -> ImportPreview:
        normalized = self._normalizer.normalize(self._parser.parse(text))
        imported: list[ImportedEvent] = []
        for event in normalized.events:
            event_type = self._classifier.classify(event)
            course = self._course_extractor.extract(event)
            assignment = self._assignment_extractor.extract(event, course)
            identity = self._fingerprint_generator.generate(self._source_id, event, event_type, course, assignment)
            imported.append(ImportedEvent(event, event_type, course, assignment, identity))

        duplicates = self._find_duplicates(imported)
        courses = self._unique_courses(imported)
        assignments = tuple(item.assignment for item in imported if item.assignment is not None)
        unknown_indexes = tuple(item.event.source_index for item in imported if item.event_type is EventType.UNKNOWN)
        safety = self._evaluate_safety(normalized.warnings, normalized.skipped_event_count, duplicates)
        return ImportPreview(
            source_id=self._source_id,
            events=tuple(imported),
            courses=courses,
            assignments=assignments,
            potential_duplicates=duplicates,
            unknown_event_indexes=unknown_indexes,
            warnings=normalized.warnings,
            safety=safety,
        )

    def _find_duplicates(self, events: list[ImportedEvent]) -> tuple[DuplicateCandidate, ...]:
        duplicates: list[DuplicateCandidate] = []
        for position, item in enumerate(events):
            for prior in events[:position]:
                strategy = self._event_matcher.match(prior.identity, item.identity)
                if strategy is not None:
                    duplicates.append(
                        DuplicateCandidate(
                            prior.event.source_index,
                            item.event.source_index,
                            strategy,
                        )
                    )
                    break
        return tuple(duplicates)

    @staticmethod
    def _evaluate_safety(
        warnings: tuple[ImportWarning, ...],
        skipped_event_count: int,
        duplicates: tuple[DuplicateCandidate, ...],
    ) -> SnapshotSafety:
        has_errors = any(warning.severity is WarningSeverity.ERROR for warning in warnings)
        is_complete = skipped_event_count == 0 and not has_errors
        reasons: list[str] = []
        if not is_complete:
            reasons.append("incomplete-snapshot")
        if duplicates:
            reasons.append("unresolved-duplicates")
        return SnapshotSafety(
            is_complete=is_complete,
            can_synchronize=not reasons,
            blocking_reasons=tuple(reasons),
        )

    @staticmethod
    def _unique_courses(events: list[ImportedEvent]) -> tuple[CourseCandidate, ...]:
        unique: dict[tuple[str, str | None], CourseCandidate] = {}
        for item in events:
            if item.course:
                unique.setdefault((item.course.code, item.course.semester), item.course)
        return tuple(unique.values())
