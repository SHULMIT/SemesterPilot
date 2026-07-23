from __future__ import annotations

from dataclasses import dataclass

from semester_pilot.ui.navigation import NavigationItem


@dataclass(frozen=True, slots=True)
class AssignmentListItemState:
    id: int
    title: str
    course_code: str
    course_name: str
    due_label: str
    status_label: str
    status_tone: str
    priority_label: str
    priority_tone: str
    progress: int
    is_overdue: bool
    is_missing: bool


@dataclass(frozen=True, slots=True)
class AssignmentListState:
    navigation: tuple[NavigationItem, ...]
    assignments: tuple[AssignmentListItemState, ...]
    courses: tuple[tuple[str, str], ...]
    search: str
    selected_filters: tuple[str, ...]
    selected_course: str
    selected_priority: str
    selected_sort: str


@dataclass(frozen=True, slots=True)
class SubtaskItemState:
    id: int
    title: str
    notes: str
    completed: bool
    estimated_minutes: str
    position: int
    version: int


@dataclass(frozen=True, slots=True)
class AssignmentDetailState:
    id: int
    title: str
    course_label: str
    due_label: str
    description: str
    imported_event_label: str
    source_identity_label: str
    location: str | None
    is_missing: bool
    priority: str
    notes: str
    estimated_minutes: str
    progress_percentage: str
    is_completed: bool
    version: int
    field_errors: tuple[tuple[str, str], ...] = ()
    global_error: str | None = None
    success_message: str | None = None
    is_saving: bool = False
    subtasks: tuple[SubtaskItemState, ...] = ()
    subtask_completed: int = 0
    subtask_total: int = 0
    subtask_percentage: int = 0
    subtask_error: str | None = None
    subtask_draft: tuple[tuple[str, str], ...] = ()
