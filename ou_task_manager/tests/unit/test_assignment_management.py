from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from semester_pilot.application.assignment_management import (
    AssignmentFilter,
    AssignmentManagementService,
    AssignmentQuery,
    AssignmentRecord,
    AssignmentSort,
    AssignmentValidationError,
    EditAssignmentCommand,
    PersonalAssignmentUpdate,
)
from semester_pilot.domain.enums import AssignmentStatus, PriorityLevel

NOW = datetime(2027, 8, 4, 10)


def _record(
    assignment_id: int,
    due: datetime,
    *,
    status: AssignmentStatus = AssignmentStatus.NOT_STARTED,
    priority: PriorityLevel = PriorityLevel.NORMAL,
    course: str = "10645",
    notes: str = "",
    missing: bool = False,
) -> AssignmentRecord:
    return AssignmentRecord(
        assignment_id,
        1,
        course,
        "מבוא למחשבים" if course == "10645" else "אלגברה",
        f"ממ״ן {assignment_id}",
        "תיאור מיובא",
        due,
        status,
        priority,
        notes,
        None,
        0,
        None,
        NOW,
        1,
        missing,
        f"uid-{assignment_id}",
        None,
        "ASSIGNMENT_DEADLINE",
        "מקוון",
    )


class _Repository:
    def __init__(self, records: list[AssignmentRecord]) -> None:
        self.records = {record.id: record for record in records}
        self.last_update: PersonalAssignmentUpdate | None = None

    def list_current(self) -> tuple[AssignmentRecord, ...]:
        return tuple(self.records.values())

    def get(self, assignment_id: int) -> AssignmentRecord | None:
        return self.records.get(assignment_id)

    def update_personal_fields(
        self, assignment_id: int, expected_version: int, values: PersonalAssignmentUpdate
    ) -> AssignmentRecord:
        current = self.records[assignment_id]
        assert expected_version == current.version
        self.last_update = values
        updated = replace(
            current,
            status=values.status,
            priority=values.priority,
            notes=values.notes,
            estimated_minutes=values.estimated_minutes,
            progress_percentage=values.progress_percentage,
            completed_at=values.completed_at,
            version=current.version + 1,
        )
        self.records[assignment_id] = updated
        return updated


def _service() -> tuple[AssignmentManagementService, _Repository]:
    repository = _Repository(
        [
            _record(1, datetime(2027, 8, 3), notes="סיכום חשוב"),
            _record(2, datetime(2027, 8, 4), priority=PriorityLevel.URGENT),
            _record(3, datetime(2027, 8, 8), status=AssignmentStatus.WORK_COMPLETED, course="20109"),
            _record(4, datetime(2027, 8, 15), missing=True),
        ]
    )
    return AssignmentManagementService(repository, lambda: NOW), repository


def test_search_filters_and_sorting_are_composable_and_deterministic() -> None:
    service, _ = _service()

    assert [item.id for item in service.list(AssignmentQuery(search="  סיכום   חשוב "))] == [1]
    assert [item.id for item in service.list(AssignmentQuery(search="20109"))] == [3]
    assert [item.id for item in service.list(AssignmentQuery(filters=frozenset({AssignmentFilter.OVERDUE})))] == [1]
    assert [item.id for item in service.list(AssignmentQuery(filters=frozenset({AssignmentFilter.DUE_TODAY})))] == [2]
    assert [item.id for item in service.list(AssignmentQuery(filters=frozenset({AssignmentFilter.MISSING})))] == [4]
    query = AssignmentQuery(
        filters=frozenset({AssignmentFilter.INCOMPLETE, AssignmentFilter.DUE_THIS_WEEK}),
        priority=PriorityLevel.URGENT,
    )
    assert [item.id for item in service.list(query)] == [2]
    assert [item.id for item in service.list(AssignmentQuery(sort=AssignmentSort.PRIORITY))] == [2, 1, 3, 4]


def test_completion_and_reopen_follow_progress_rules() -> None:
    service, repository = _service()
    completed = service.update(EditAssignmentCommand(2, 1, "HIGH", " note ", 90, 20, True))
    assert completed.status is AssignmentStatus.WORK_COMPLETED
    assert completed.progress_percentage == 100
    assert completed.completed_at == NOW
    assert completed.notes == "note"

    reopened = service.update(EditAssignmentCommand(2, 2, "LOW", "", None, 40, False))
    assert reopened.status is AssignmentStatus.IN_PROGRESS
    assert reopened.progress_percentage == 40
    assert reopened.completed_at is None
    assert repository.last_update is not None


@pytest.mark.parametrize(
    ("command", "field"),
    [
        (EditAssignmentCommand(1, 1, "invalid", "", None, 0, False), "priority"),
        (EditAssignmentCommand(1, 1, "NORMAL", "", None, 101, False), "progress_percentage"),
        (EditAssignmentCommand(1, 1, "NORMAL", "", -1, 0, False), "estimated_minutes"),
        (EditAssignmentCommand(1, 1, "NORMAL", "x" * 10_001, None, 0, False), "notes"),
    ],
)
def test_invalid_personal_fields_are_rejected(command: EditAssignmentCommand, field: str) -> None:
    service, _ = _service()
    with pytest.raises(AssignmentValidationError) as caught:
        service.update(command)
    assert field in caught.value.field_errors
