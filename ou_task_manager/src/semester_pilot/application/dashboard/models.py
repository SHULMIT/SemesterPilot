from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from semester_pilot.application.synchronization.models import SyncScope
from semester_pilot.domain.enums import AssignmentStatus, EventType, PriorityLevel


@dataclass(frozen=True, slots=True)
class DashboardAssignmentRecord:
    id: int
    course_code: str
    course_name: str
    title: str
    due_at: datetime
    status: AssignmentStatus
    priority: PriorityLevel


@dataclass(frozen=True, slots=True)
class DashboardEventRecord:
    id: int
    title: str
    starts_at: datetime
    event_type: EventType
    course_code: str | None = None
    course_name: str | None = None


@dataclass(frozen=True, slots=True)
class RecentImportRecord:
    scope: SyncScope
    synchronized_at: datetime
    added_count: int
    updated_count: int
    unchanged_count: int
    missing_count: int
    ambiguous_count: int


@dataclass(frozen=True, slots=True)
class DashboardData:
    current_scope: SyncScope | None
    active_course_count: int
    assignments: tuple[DashboardAssignmentRecord, ...]
    events: tuple[DashboardEventRecord, ...]
    recent_import: RecentImportRecord | None


@dataclass(frozen=True, slots=True)
class AgendaItem:
    id: int
    title: str
    starts_at: datetime
    event_type: EventType
    course_name: str | None


@dataclass(frozen=True, slots=True)
class UpcomingAssignment:
    id: int
    course_code: str
    course_name: str
    title: str
    due_at: datetime
    status: AssignmentStatus
    priority: PriorityLevel


@dataclass(frozen=True, slots=True)
class WeeklyOverview:
    assignments_due: int
    exams: int
    lessons: int
    starts_on: date
    ends_on: date


@dataclass(frozen=True, slots=True)
class ProgressSummary:
    completed: int
    remaining: int
    overdue: int
    completion_percent: int


@dataclass(frozen=True, slots=True)
class DashboardOverview:
    generated_at: datetime
    current_semester: str | None
    active_course_count: int
    todays_agenda: tuple[AgendaItem, ...]
    upcoming_assignments: tuple[UpcomingAssignment, ...]
    weekly: WeeklyOverview
    progress: ProgressSummary
    recent_import: RecentImportRecord | None
