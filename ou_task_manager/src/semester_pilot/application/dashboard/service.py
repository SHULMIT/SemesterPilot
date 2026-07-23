from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from semester_pilot.application.dashboard.models import (
    AgendaItem,
    DashboardOverview,
    ProgressSummary,
    UpcomingAssignment,
    WeeklyOverview,
)
from semester_pilot.application.dashboard.ports import DashboardRepository
from semester_pilot.domain.enums import AssignmentStatus, EventType

_COMPLETED_STATUSES = {AssignmentStatus.WORK_COMPLETED, AssignmentStatus.SUBMITTED}
_AGENDA_TYPES = {EventType.LESSON, EventType.EXAM, EventType.ASSIGNMENT_DEADLINE}


class DashboardService:
    """Builds one dashboard overview from a repository snapshot."""

    def __init__(
        self,
        repository: DashboardRepository,
        clock: Callable[[], datetime] | None = None,
        upcoming_limit: int = 6,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now().astimezone())
        self._upcoming_limit = upcoming_limit

    def load(self) -> DashboardOverview:
        now = self._clock()
        today = now.date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        data = self._repository.load(week_start, week_end)

        active_assignments = tuple(
            assignment for assignment in data.assignments if assignment.status not in _COMPLETED_STATUSES
        )
        completed_count = len(data.assignments) - len(active_assignments)
        overdue_count = sum(
            assignment.status is AssignmentStatus.OVERDUE or assignment.due_at.date() < today
            for assignment in active_assignments
        )
        upcoming = tuple(
            UpcomingAssignment(
                assignment.id,
                assignment.course_code,
                assignment.course_name,
                assignment.title,
                assignment.due_at,
                assignment.status,
                assignment.priority,
            )
            for assignment in sorted(
                (assignment for assignment in active_assignments if assignment.due_at.date() >= today),
                key=lambda assignment: (
                    assignment.due_at.date(),
                    assignment.due_at.time().replace(tzinfo=None),
                    assignment.id,
                ),
            )[: self._upcoming_limit]
        )
        agenda = tuple(
            AgendaItem(event.id, event.title, event.starts_at, event.event_type, event.course_name)
            for event in sorted(data.events, key=lambda event: (event.starts_at.time(), event.id))
            if event.starts_at.date() == today and event.event_type in _AGENDA_TYPES
        )
        in_week = lambda value: week_start <= value.date() <= week_end
        weekly = WeeklyOverview(
            assignments_due=sum(in_week(assignment.due_at) for assignment in active_assignments),
            exams=sum(in_week(event.starts_at) and event.event_type is EventType.EXAM for event in data.events),
            lessons=sum(in_week(event.starts_at) and event.event_type is EventType.LESSON for event in data.events),
            starts_on=week_start,
            ends_on=week_end,
        )
        assignment_count = len(data.assignments)
        completion_percent = round(completed_count / assignment_count * 100) if assignment_count else 0
        return DashboardOverview(
            generated_at=now,
            current_semester=data.current_scope.semester if data.current_scope else None,
            active_course_count=data.active_course_count,
            todays_agenda=agenda,
            upcoming_assignments=upcoming,
            weekly=weekly,
            progress=ProgressSummary(completed_count, len(active_assignments), overdue_count, completion_percent),
            recent_import=data.recent_import,
        )
