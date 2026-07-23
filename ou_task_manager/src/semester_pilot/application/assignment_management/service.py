from __future__ import annotations

import builtins
import unicodedata
from collections.abc import Callable
from datetime import date, datetime, timedelta

from semester_pilot.application.assignment_management.models import (
    AssignmentFilter,
    AssignmentNotFoundError,
    AssignmentListResult,
    AssignmentQuery,
    AssignmentRecord,
    AssignmentSort,
    AssignmentValidationError,
    EditAssignmentCommand,
    PersonalAssignmentUpdate,
)
from semester_pilot.application.assignment_management.ports import ManagedAssignmentRepository
from semester_pilot.domain.enums import AssignmentStatus, PriorityLevel

_COMPLETED = {AssignmentStatus.WORK_COMPLETED, AssignmentStatus.SUBMITTED}
_PRIORITY_RANK = {
    PriorityLevel.URGENT: 0,
    PriorityLevel.HIGH: 1,
    PriorityLevel.NORMAL: 2,
    PriorityLevel.LOW: 3,
}


class AssignmentManagementService:
    """Queries assignments and updates only student-owned fields."""

    def __init__(
        self,
        repository: ManagedAssignmentRepository,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now().astimezone())

    def list(self, query: AssignmentQuery = AssignmentQuery()) -> tuple[AssignmentRecord, ...]:
        return self.list_page(query).assignments

    def list_page(self, query: AssignmentQuery = AssignmentQuery()) -> AssignmentListResult:
        today = self._clock().date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        search = self._normalize(query.search)
        records = self._repository.list_current()
        filtered = [
            record
            for record in records
            if self._matches_search(record, search)
            and (query.course_code is None or record.course_code == query.course_code)
            and (query.priority is None or record.priority is query.priority)
            and all(self._matches_filter(record, item, today, week_start, week_end) for item in query.filters)
        ]
        courses = tuple(sorted({(record.course_code, record.course_name) for record in records}, key=lambda x: x[1]))
        overdue_ids = frozenset(
            record.id
            for record in filtered
            if record.status not in _COMPLETED
            and (record.status is AssignmentStatus.OVERDUE or record.due_at.date() < today)
        )
        return AssignmentListResult(tuple(self._sort(filtered, query.sort)), courses, overdue_ids)

    def get(self, assignment_id: int) -> AssignmentRecord:
        assignment = self._repository.get(assignment_id)
        if assignment is None:
            raise AssignmentNotFoundError(f"Assignment {assignment_id} does not exist")
        return assignment

    def update(self, command: EditAssignmentCommand) -> AssignmentRecord:
        existing = self.get(command.assignment_id)
        errors: dict[str, str] = {}
        try:
            priority = PriorityLevel(command.priority)
        except ValueError:
            priority = PriorityLevel.NORMAL
            errors["priority"] = "יש לבחור עדיפות תקינה."
        if not 0 <= command.progress_percentage <= 100:
            errors["progress_percentage"] = "ההתקדמות חייבת להיות בין 0 ל־100."
        if command.estimated_minutes is not None and not 0 <= command.estimated_minutes <= 100_000:
            errors["estimated_minutes"] = "זמן הלימוד חייב להיות מספר חיובי וסביר."
        notes = command.notes.strip()
        if len(notes) > 10_000:
            errors["notes"] = "ההערות יכולות להכיל עד 10,000 תווים."
        if command.expected_version < 1:
            errors["version"] = "גרסת העריכה אינה תקינה. יש לרענן את העמוד."
        if errors:
            raise AssignmentValidationError(errors)

        now = self._clock()
        if command.is_completed:
            status = AssignmentStatus.WORK_COMPLETED
            progress = 100
            completed_at = existing.completed_at or now
        else:
            if existing.status in _COMPLETED:
                if command.progress_percentage == 100:
                    raise AssignmentValidationError(
                        {"progress_percentage": "בפתיחה מחדש יש לבחור התקדמות נמוכה מ־100."}
                    )
                status = (
                    AssignmentStatus.IN_PROGRESS if command.progress_percentage > 0 else AssignmentStatus.NOT_STARTED
                )
            elif existing.status is AssignmentStatus.OVERDUE:
                status = AssignmentStatus.OVERDUE
            else:
                status = (
                    AssignmentStatus.IN_PROGRESS if command.progress_percentage > 0 else AssignmentStatus.NOT_STARTED
                )
            progress = command.progress_percentage
            completed_at = None
        return self._repository.update_personal_fields(
            command.assignment_id,
            command.expected_version,
            PersonalAssignmentUpdate(
                status=status,
                priority=priority,
                notes=notes,
                estimated_minutes=command.estimated_minutes,
                progress_percentage=progress,
                completed_at=completed_at,
            ),
        )

    @classmethod
    def _matches_search(cls, record: AssignmentRecord, search: str) -> bool:
        if not search:
            return True
        haystack = cls._normalize(" ".join((record.title, record.course_name, record.course_code, record.notes)))
        return search in haystack

    @staticmethod
    def _matches_filter(
        record: AssignmentRecord,
        item: AssignmentFilter,
        today: date,
        week_start: date,
        week_end: date,
    ) -> bool:
        completed = record.status in _COMPLETED
        if item is AssignmentFilter.INCOMPLETE:
            return not completed
        if item is AssignmentFilter.COMPLETED:
            return completed
        if item is AssignmentFilter.OVERDUE:
            return not completed and (record.status is AssignmentStatus.OVERDUE or record.due_at.date() < today)
        if item is AssignmentFilter.DUE_TODAY:
            return record.due_at.date() == today
        if item is AssignmentFilter.DUE_THIS_WEEK:
            return week_start <= record.due_at.date() <= week_end
        return record.is_missing_from_source

    @staticmethod
    def _sort(records: builtins.list[AssignmentRecord], sort: AssignmentSort) -> builtins.list[AssignmentRecord]:
        records = sorted(records, key=lambda record: record.id)
        if sort is AssignmentSort.DUE_SOON:
            return sorted(records, key=lambda record: record.due_at)
        if sort is AssignmentSort.DUE_LATEST:
            return sorted(records, key=lambda record: record.due_at, reverse=True)
        if sort is AssignmentSort.PRIORITY:
            return sorted(records, key=lambda record: _PRIORITY_RANK[record.priority])
        if sort is AssignmentSort.COURSE:
            return sorted(records, key=lambda record: (record.course_name.casefold(), record.course_code))
        if sort is AssignmentSort.COMPLETION:
            return sorted(records, key=lambda record: (record.status in _COMPLETED, record.status.value))
        return sorted(records, key=lambda record: record.updated_at, reverse=True)

    @staticmethod
    def _normalize(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value).casefold()
        without_marks = "".join(character for character in normalized if unicodedata.category(character) != "Mn")
        return " ".join(without_marks.split())
