from __future__ import annotations

from dataclasses import dataclass

from semester_pilot.ui.navigation import NavigationItem


@dataclass(frozen=True, slots=True)
class DashboardAgendaState:
    title: str
    course_name: str | None
    time_label: str
    type_label: str
    tone: str
    icon: str


@dataclass(frozen=True, slots=True)
class DashboardAssignmentState:
    title: str
    course_code: str
    course_name: str
    due_label: str
    priority_label: str
    priority_tone: str
    status_label: str
    status_tone: str


@dataclass(frozen=True, slots=True)
class DashboardCountState:
    label: str
    value: int
    tone: str
    icon: str


@dataclass(frozen=True, slots=True)
class RecentImportState:
    synchronized_label: str
    source_label: str
    summary: str


@dataclass(frozen=True, slots=True)
class DashboardState:
    greeting: str
    date_label: str
    semester_label: str
    active_course_count: int
    navigation: tuple[NavigationItem, ...]
    agenda: tuple[DashboardAgendaState, ...]
    assignments: tuple[DashboardAssignmentState, ...]
    weekly: tuple[DashboardCountState, ...]
    progress: tuple[DashboardCountState, ...]
    completion_percent: int
    recent_import: RecentImportState | None
