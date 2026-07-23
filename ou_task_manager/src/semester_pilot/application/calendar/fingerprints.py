from __future__ import annotations

import hashlib
import json
import re
import unicodedata

from semester_pilot.application.calendar.models import (
    AssignmentCandidate,
    CourseCandidate,
    EventIdentity,
    NormalizedCalendarEvent,
)
from semester_pilot.domain.enums import EventType


def _stable_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.sub(r"[^\w\s]", " ", value).split())


class FingerprintGenerator:
    """Builds independent UID, exact-fingerprint, and fallback identity signals."""

    def generate(
        self,
        source_id: str,
        event: NormalizedCalendarEvent,
        event_type: EventType,
        course: CourseCandidate | None,
        assignment: AssignmentCandidate | None,
    ) -> EventIdentity:
        source_id = source_id.strip()
        if not source_id:
            raise ValueError("Calendar source_id must not be empty")
        course_code = course.code if course else ""
        course_semester = course.semester if course and course.semester else ""
        assignment_number = assignment.number if assignment else ""
        exact_values = {
            "event_type": event_type.value,
            "course_code": course_code,
            "course_semester": course_semester,
            "assignment_number": assignment_number,
            "title": _stable_text(event.title),
            "description": _stable_text(event.description),
            "location": _stable_text(event.location),
            "start": event.starts_at.isoformat(),
            "end": event.ends_at.isoformat() if event.ends_at else "",
            "is_all_day": event.is_all_day,
            "sequence": event.sequence,
            "last_modified": event.last_modified_at.isoformat() if event.last_modified_at else "",
            "recurrence_id": event.recurrence_id.isoformat() if event.recurrence_id else "",
        }
        encoded = json.dumps(exact_values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(encoded.encode("utf-8")).hexdigest()

        fallback_parts: tuple[str, ...]
        if assignment and course:
            fallback_parts = (
                event_type.value,
                course.code,
                course_semester,
                assignment.number,
                event.recurrence_id.isoformat() if event.recurrence_id else "",
            )
        else:
            fallback_parts = (
                event_type.value,
                course_code,
                course_semester,
                _stable_text(event.title),
                event.starts_at.isoformat(),
                event.recurrence_id.isoformat() if event.recurrence_id else "",
            )
        stable_key = "|".join(fallback_parts)
        uid = event.uid.strip() if event.uid else None
        return EventIdentity(
            source_id=source_id,
            uid=uid or None,
            recurrence_id=event.recurrence_id.isoformat() if event.recurrence_id else None,
            stable_key=stable_key,
            content_hash=fingerprint,
        )
