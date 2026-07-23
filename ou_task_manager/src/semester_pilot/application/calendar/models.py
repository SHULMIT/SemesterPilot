from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

from semester_pilot.domain.enums import EventType


class WarningSeverity(StrEnum):
    WARNING = "WARNING"
    ERROR = "ERROR"


class MatchStrategy(StrEnum):
    UID = "uid"
    CONTENT_HASH = "content_hash"
    STABLE_KEY = "stable_key"


@dataclass(frozen=True, slots=True)
class ImportWarning:
    """A recoverable problem found while processing calendar input."""

    code: str
    message: str
    event_index: int | None = None
    severity: WarningSeverity = WarningSeverity.WARNING


@dataclass(frozen=True, slots=True)
class CalendarProperty:
    """One source calendar property before semantic normalization."""

    value: str
    parameters: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True, slots=True)
class SourceEvent:
    """A syntactically parsed VEVENT with untouched property values."""

    index: int
    properties: Mapping[str, tuple[CalendarProperty, ...]]

    def first(self, name: str) -> CalendarProperty | None:
        values = self.properties.get(name.upper(), ())
        return values[0] if values else None


@dataclass(frozen=True, slots=True)
class CalendarParseResult:
    events: tuple[SourceEvent, ...]
    warnings: tuple[ImportWarning, ...] = ()


@dataclass(frozen=True, slots=True)
class NormalizedCalendarEvent:
    """A source event after text, identifier, and date normalization."""

    source_index: int
    uid: str | None
    recurrence_id: datetime | None
    title: str
    description: str
    location: str
    starts_at: datetime
    ends_at: datetime | None
    is_all_day: bool
    sequence: int | None = None
    last_modified_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    events: tuple[NormalizedCalendarEvent, ...]
    warnings: tuple[ImportWarning, ...] = ()
    skipped_event_count: int = 0


@dataclass(frozen=True, slots=True)
class ClassificationRule:
    event_type: EventType
    patterns: tuple[str, ...]
    fields: tuple[str, ...] = ("title", "description")


@dataclass(frozen=True, slots=True)
class CourseCandidate:
    code: str
    name: str
    semester: str | None = None


@dataclass(frozen=True, slots=True)
class AssignmentCandidate:
    number: str
    title: str
    due_at: datetime
    course: CourseCandidate | None
    event_index: int


@dataclass(frozen=True, slots=True)
class EventIdentity:
    source_id: str
    uid: str | None
    recurrence_id: str | None
    stable_key: str
    content_hash: str

    @property
    def canonical_key(self) -> str:
        if self.uid:
            recurrence = self.recurrence_id or "master"
            return f"uid:{self.source_id}:{self.uid}:{recurrence}"
        return f"stable:{self.source_id}:{self.stable_key}"


@dataclass(frozen=True, slots=True)
class ImportedEvent:
    event: NormalizedCalendarEvent
    event_type: EventType
    course: CourseCandidate | None
    assignment: AssignmentCandidate | None
    identity: EventIdentity


@dataclass(frozen=True, slots=True)
class DuplicateCandidate:
    first_event_index: int
    duplicate_event_index: int
    strategy: MatchStrategy


@dataclass(frozen=True, slots=True)
class SnapshotSafety:
    is_complete: bool
    can_synchronize: bool
    blocking_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ImportPreview:
    """An in-memory parsing preview; it does not compare with persisted data."""

    source_id: str
    events: tuple[ImportedEvent, ...]
    courses: tuple[CourseCandidate, ...]
    assignments: tuple[AssignmentCandidate, ...]
    potential_duplicates: tuple[DuplicateCandidate, ...]
    unknown_event_indexes: tuple[int, ...]
    warnings: tuple[ImportWarning, ...]
    safety: SnapshotSafety
