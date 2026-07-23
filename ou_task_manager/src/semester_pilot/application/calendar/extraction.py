from __future__ import annotations

import re
from collections.abc import Sequence

from semester_pilot.application.calendar.models import (
    AssignmentCandidate,
    CourseCandidate,
    NormalizedCalendarEvent,
)


DEFAULT_COURSE_PATTERNS: tuple[str, ...] = (
    r"(?:^|\s)קורס\s+(.+?)\s*\((\d{4,})\)(?:\s+בסמסטר\s+([^\s]+))?",
    r"^(.+?)\s*\((\d{4,})\)(?:\s+בסמסטר\s+([^\s]+))?",
)

DEFAULT_ASSIGNMENT_PATTERNS: tuple[str, ...] = (r"(?:מטלה|ממ[\"']?ן)\s*[:#-]?\s*(\d+)",)


class CourseExtractor:
    """Extracts course identity using an injected institution/language profile."""

    def __init__(self, patterns: Sequence[str] = DEFAULT_COURSE_PATTERNS) -> None:
        self._patterns = tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)

    def extract(self, event: NormalizedCalendarEvent) -> CourseCandidate | None:
        text = " ".join(part for part in (event.description, event.location, event.title) if part)
        for pattern in self._patterns:
            match = pattern.search(text)
            if match:
                name, code, semester = match.group(1), match.group(2), match.group(3)
                return CourseCandidate(code=code, name=name.strip(" -,:"), semester=semester)
        return None


class AssignmentExtractor:
    """Extracts assignment identity without classifying or persisting an event."""

    def __init__(self, patterns: Sequence[str] = DEFAULT_ASSIGNMENT_PATTERNS) -> None:
        self._patterns = tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)

    def extract(self, event: NormalizedCalendarEvent, course: CourseCandidate | None) -> AssignmentCandidate | None:
        text = " ".join(part for part in (event.description, event.title) if part)
        for pattern in self._patterns:
            match = pattern.search(text)
            if match:
                number = match.group(1).zfill(2)
                return AssignmentCandidate(
                    number=number,
                    title=event.title or f"Assignment {number}",
                    due_at=event.starts_at,
                    course=course,
                    event_index=event.source_index,
                )
        return None
