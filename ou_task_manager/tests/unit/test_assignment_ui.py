from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from semester_pilot.application.assignment_management import (
    AssignmentListResult,
    AssignmentRecord,
    AssignmentValidationError,
)
from semester_pilot.domain.enums import AssignmentStatus, PriorityLevel
from semester_pilot.ui.screens.assignment_view import AssignmentView
from semester_pilot.ui.view_models.assignment_view_model import AssignmentViewModel


def _record() -> AssignmentRecord:
    return AssignmentRecord(
        7,
        1,
        "10645",
        "מבוא למחשבים",
        "ממ״ן 11",
        "מידע מהלוח",
        datetime(2027, 8, 10, 23, 59),
        AssignmentStatus.NOT_STARTED,
        PriorityLevel.NORMAL,
        "",
        None,
        0,
        None,
        datetime(2027, 8, 1),
        3,
        True,
        "uid-11",
        None,
        "ASSIGNMENT_DEADLINE",
        "מקוון",
    )


class _Service:
    def __init__(self, record: AssignmentRecord, failure: Exception | None = None) -> None:
        self.record = record
        self.failure = failure

    def list_page(self, _query) -> AssignmentListResult:
        return AssignmentListResult((self.record,), ((self.record.course_code, self.record.course_name),), frozenset())

    def get(self, _assignment_id: int) -> AssignmentRecord:
        return self.record

    def update(self, command):
        if self.failure:
            raise self.failure
        self.record = replace(
            self.record,
            notes=command.notes,
            priority=PriorityLevel(command.priority),
            progress_percentage=command.progress_percentage,
            version=self.record.version + 1,
        )
        return self.record


def test_assignment_list_and_detail_are_rtl_accessible_and_keep_source_read_only() -> None:
    view_model = AssignmentViewModel(_Service(_record()))
    view = AssignmentView()
    listing = view.render_list(view_model.build_list({}))
    detail = view.render_detail(view_model.build_detail(7))

    assert '<html lang="he" dir="rtl">' in listing
    assert 'href="/assignments/7"' in listing
    assert 'role="progressbar"' in listing
    assert "<form data-assignment-form" in detail
    assert "<dl>" in detail
    assert 'name="notes"' in detail and 'name="progress_percentage"' in detail
    assert 'name="due_at"' not in detail
    assignment_form = detail.split("<form data-assignment-form", 1)[1].split("</form>", 1)[0]
    assert 'name="title"' not in assignment_form
    assert 'role="status" aria-live="polite"' in detail


def test_validation_failure_preserves_submitted_form_values() -> None:
    service = _Service(_record(), AssignmentValidationError({"notes": "שגיאה"}))
    accepted, state = AssignmentViewModel(service).save(
        7,
        {
            "version": "3",
            "priority": "HIGH",
            "notes": "הטקסט שהוזן",
            "estimated_minutes": "90",
            "progress_percentage": "42",
            "is_completed": "false",
        },
    )

    assert accepted is True
    assert state.notes == "הטקסט שהוזן"
    assert state.progress_percentage == "42"
    assert dict(state.field_errors) == {"notes": "שגיאה"}


def test_successful_save_returns_fresh_version_and_success_state() -> None:
    accepted, state = AssignmentViewModel(_Service(_record())).save(
        7,
        {
            "version": "3",
            "priority": "HIGH",
            "notes": "חדש",
            "estimated_minutes": "",
            "progress_percentage": "50",
            "is_completed": "false",
        },
    )
    assert accepted is True
    assert state.version == 4
    assert state.success_message
