from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from semester_pilot.application.calendar.models import EventIdentity
from semester_pilot.domain.enums import EventType


@dataclass(frozen=True, slots=True)
class SyncScope:
    source_id: str
    institution: str
    semester: str

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("Synchronization source_id must not be empty")
        if not self.institution.strip():
            raise ValueError("Synchronization institution must not be empty")
        if not self.semester.strip():
            raise ValueError("Synchronization semester must not be empty")


@dataclass(frozen=True, slots=True)
class PersistedAcademicEvent:
    id: int | None
    scope: SyncScope
    external_uid: str | None
    recurrence_id: str | None
    stable_match_key: str
    content_hash: str
    event_type: EventType
    course_id: int | None
    assignment_id: int | None
    title: str
    description: str
    starts_at: datetime
    ends_at: datetime | None
    is_all_day: bool
    location: str
    sequence: int | None
    source_last_modified_at: datetime | None
    is_missing: bool = False
    source_archived_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def identity(self) -> EventIdentity:
        return EventIdentity(
            source_id=self.scope.source_id,
            uid=self.external_uid,
            recurrence_id=self.recurrence_id,
            stable_key=self.stable_match_key,
            content_hash=self.content_hash,
        )


class MatchConfidence(StrEnum):
    HIGH = "high"
    EXACT = "exact"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class SyncItem:
    event_index: int | None
    persisted_event_id: int | None


@dataclass(frozen=True, slots=True)
class AmbiguousMatch:
    event_index: int
    match_type: str
    confidence: MatchConfidence
    reason: str
    candidate_identifiers: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class SynchronizationResult:
    added: tuple[SyncItem, ...] = ()
    updated: tuple[SyncItem, ...] = ()
    unchanged: tuple[SyncItem, ...] = ()
    missing: tuple[SyncItem, ...] = ()
    ambiguous: tuple[AmbiguousMatch, ...] = ()
    skipped_unsafe_event_indexes: tuple[int, ...] = ()
    skipped_reasons: tuple[str, ...] = ()
    history_id: int | None = None

    @property
    def was_skipped(self) -> bool:
        return bool(self.skipped_reasons)


@dataclass(frozen=True, slots=True)
class SynchronizationHistory:
    id: int | None
    scope: SyncScope
    added_count: int
    updated_count: int
    unchanged_count: int
    missing_count: int
    ambiguous_count: int
    synchronized_at: datetime | None = None
