from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from semester_pilot.domain.enums import AssignmentStatus, PriorityLevel


class AssignmentFilter(StrEnum):
    INCOMPLETE = "incomplete"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    DUE_TODAY = "due_today"
    DUE_THIS_WEEK = "due_this_week"
    MISSING = "missing"


class AssignmentSort(StrEnum):
    DUE_SOON = "due_soon"
    DUE_LATEST = "due_latest"
    PRIORITY = "priority"
    COURSE = "course"
    COMPLETION = "completion"
    RECENTLY_UPDATED = "recently_updated"


@dataclass(frozen=True, slots=True)
class AssignmentQuery:
    search: str = ""
    filters: frozenset[AssignmentFilter] = frozenset()
    course_code: str | None = None
    priority: PriorityLevel | None = None
    sort: AssignmentSort = AssignmentSort.DUE_SOON


@dataclass(frozen=True, slots=True)
class AssignmentListResult:
    assignments: tuple[AssignmentRecord, ...]
    courses: tuple[tuple[str, str], ...]
    overdue_ids: frozenset[int]


@dataclass(frozen=True, slots=True)
class AssignmentRecord:
    id: int
    course_id: int
    course_code: str
    course_name: str
    title: str
    description: str
    due_at: datetime
    status: AssignmentStatus
    priority: PriorityLevel
    notes: str
    estimated_minutes: int | None
    progress_percentage: int
    completed_at: datetime | None
    updated_at: datetime
    version: int
    is_missing_from_source: bool
    external_uid: str | None
    recurrence_id: str | None
    imported_event_type: str | None
    imported_location: str | None


@dataclass(frozen=True, slots=True)
class PersonalAssignmentUpdate:
    status: AssignmentStatus
    priority: PriorityLevel
    notes: str
    estimated_minutes: int | None
    progress_percentage: int
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class EditAssignmentCommand:
    assignment_id: int
    expected_version: int
    priority: str
    notes: str
    estimated_minutes: int | None
    progress_percentage: int
    is_completed: bool


class AssignmentValidationError(ValueError):
    def __init__(self, field_errors: dict[str, str]) -> None:
        super().__init__("Assignment validation failed")
        self.field_errors = field_errors


class AssignmentNotFoundError(LookupError):
    pass


class StaleAssignmentError(RuntimeError):
    pass
