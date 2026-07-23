from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Protocol

from semester_pilot.application.calendar.models import AssignmentCandidate, CourseCandidate
from semester_pilot.application.synchronization.models import (
    PersistedAcademicEvent,
    SyncScope,
    SynchronizationHistory,
)
from semester_pilot.domain.entities import Assignment, Course


class SyncCourseRepository(Protocol):
    def get_or_create_imported(self, candidate: CourseCandidate, scope: SyncScope) -> Course: ...


class SyncAssignmentRepository(Protocol):
    def get_or_create_imported(self, candidate: AssignmentCandidate, course_id: int) -> Assignment: ...

    def update_imported_fields(
        self,
        assignment_id: int,
        *,
        title: str,
        due_at: datetime,
        source_fingerprint: str,
    ) -> Assignment: ...


class AcademicEventRepository(Protocol):
    def list_for_scope(self, scope: SyncScope) -> list[PersistedAcademicEvent]: ...

    def create(self, event: PersistedAcademicEvent) -> PersistedAcademicEvent: ...

    def update_source_fields(self, event_id: int, event: PersistedAcademicEvent) -> PersistedAcademicEvent: ...

    def mark_missing(self, event_id: int) -> PersistedAcademicEvent: ...


class SynchronizationHistoryRepository(Protocol):
    def create(self, history: SynchronizationHistory) -> SynchronizationHistory: ...


class CalendarSyncUnitOfWork(Protocol):
    courses: SyncCourseRepository
    assignments: SyncAssignmentRepository
    events: AcademicEventRepository
    history: SynchronizationHistoryRepository

    def __enter__(self) -> CalendarSyncUnitOfWork: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


CalendarSyncUnitOfWorkFactory = Callable[[], CalendarSyncUnitOfWork]
