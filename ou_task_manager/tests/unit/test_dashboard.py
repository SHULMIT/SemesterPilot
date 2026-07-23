from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path

from semester_pilot.application.dashboard.models import (
    DashboardAssignmentRecord,
    DashboardData,
    DashboardEventRecord,
    RecentImportRecord,
)
from semester_pilot.application.dashboard.service import DashboardService
from semester_pilot.application.synchronization.models import SyncScope
from semester_pilot.domain.enums import AssignmentStatus, EventType, PriorityLevel
from semester_pilot.ui.screens.dashboard_view import DashboardView
from semester_pilot.ui.view_models.dashboard_view_model import DashboardViewModel

NOW = datetime(2027, 8, 4, 10, 30)
SCOPE = SyncScope("open-university-hebrew-calendar", "Open University", "2027A")
PROJECT_ROOT = Path(__file__).parents[2]


class _FakeRepository:
    def __init__(self, data: DashboardData) -> None:
        self.data = data
        self.calls: list[tuple[object, object]] = []

    def load(self, range_start, range_end) -> DashboardData:
        self.calls.append((range_start, range_end))
        return self.data


def _assignment(
    assignment_id: int,
    due: datetime,
    status: AssignmentStatus = AssignmentStatus.NOT_STARTED,
    priority: PriorityLevel = PriorityLevel.NORMAL,
) -> DashboardAssignmentRecord:
    return DashboardAssignmentRecord(
        assignment_id,
        "10645",
        "תכנון וניתוח מערכות מידע",
        f"ממ״ן {assignment_id:02d}",
        due,
        status,
        priority,
    )


def _event(event_id: int, starts: datetime, event_type: EventType) -> DashboardEventRecord:
    return DashboardEventRecord(event_id, f"אירוע {event_id}", starts, event_type, "10645", "מערכות מידע")


def _populated_data() -> DashboardData:
    return DashboardData(
        current_scope=SCOPE,
        active_course_count=3,
        assignments=(
            _assignment(1, datetime(2027, 8, 1), AssignmentStatus.SUBMITTED),
            _assignment(2, datetime(2027, 8, 4, 23, 59), priority=PriorityLevel.HIGH),
            _assignment(3, datetime(2027, 8, 3), AssignmentStatus.NOT_STARTED),
            _assignment(4, datetime(2027, 8, 7), AssignmentStatus.IN_PROGRESS),
            _assignment(5, datetime(2027, 8, 15), priority=PriorityLevel.URGENT),
        ),
        events=(
            _event(1, datetime(2027, 8, 4, 8), EventType.LESSON),
            _event(2, datetime(2027, 8, 4, 10), EventType.EXAM),
            _event(3, datetime(2027, 8, 4, 23, 59), EventType.ASSIGNMENT_DEADLINE),
            _event(4, datetime(2027, 8, 4, 12), EventType.GENERAL_ACADEMIC),
            _event(5, datetime(2027, 8, 5, 16), EventType.LESSON),
            _event(6, datetime(2027, 8, 6, 9), EventType.EXAM),
        ),
        recent_import=RecentImportRecord(SCOPE, datetime(2027, 8, 3, 18, 20), 4, 1, 8, 2, 0),
    )


def test_empty_dashboard_has_zeroed_aggregates_and_one_repository_call() -> None:
    repository = _FakeRepository(DashboardData(None, 0, (), (), None))

    overview = DashboardService(repository, clock=lambda: NOW).load()

    assert overview.current_semester is None
    assert overview.active_course_count == 0
    assert overview.todays_agenda == ()
    assert overview.upcoming_assignments == ()
    assert overview.weekly.assignments_due == 0
    assert overview.progress.completed == 0
    assert overview.progress.remaining == 0
    assert overview.progress.overdue == 0
    assert overview.progress.completion_percent == 0
    assert repository.calls == [(datetime(2027, 8, 2).date(), datetime(2027, 8, 8).date())]


def test_populated_dashboard_calculates_overdue_progress_and_sorted_upcoming() -> None:
    overview = DashboardService(_FakeRepository(_populated_data()), clock=lambda: NOW).load()

    assert overview.current_semester == "2027A"
    assert overview.active_course_count == 3
    assert overview.progress.completed == 1
    assert overview.progress.remaining == 4
    assert overview.progress.overdue == 1
    assert overview.progress.completion_percent == 20
    assert [assignment.id for assignment in overview.upcoming_assignments] == [2, 4, 5]


def test_today_agenda_includes_only_supported_today_types_in_time_order() -> None:
    overview = DashboardService(_FakeRepository(_populated_data()), clock=lambda: NOW).load()

    assert [item.id for item in overview.todays_agenda] == [1, 2, 3]
    assert {item.event_type for item in overview.todays_agenda} == {
        EventType.LESSON,
        EventType.EXAM,
        EventType.ASSIGNMENT_DEADLINE,
    }


def test_weekly_aggregation_uses_calendar_week() -> None:
    overview = DashboardService(_FakeRepository(_populated_data()), clock=lambda: NOW).load()

    assert overview.weekly.starts_on.isoformat() == "2027-08-02"
    assert overview.weekly.ends_on.isoformat() == "2027-08-08"
    assert overview.weekly.assignments_due == 3
    assert overview.weekly.exams == 2
    assert overview.weekly.lessons == 2


def test_dashboard_view_model_maps_real_overview_to_hebrew_display_state() -> None:
    service = DashboardService(_FakeRepository(_populated_data()), clock=lambda: NOW)

    state = DashboardViewModel(service).build()

    assert state.greeting == "בוקר טוב"
    assert state.semester_label == "2027A"
    assert state.active_course_count == 3
    assert state.agenda[0].type_label == "שיעור"
    assert state.assignments[0].priority_label == "גבוהה"
    assert state.assignments[1].status_label == "בתהליך"
    assert state.completion_percent == 20
    assert state.recent_import is not None
    assert state.recent_import.source_label == "Open University Hebrew Calendar"
    assert "4 חדשים" in state.recent_import.summary


def test_empty_dashboard_view_renders_encouraging_states() -> None:
    state = DashboardViewModel(
        DashboardService(_FakeRepository(DashboardData(None, 0, (), (), None)), clock=lambda: NOW)
    ).build()

    document = DashboardView().render(state)

    assert '<html lang="he" dir="rtl">' in document
    assert "היום שלך פנוי" in document
    assert "אין מטלות קרובות" in document
    assert "עדיין אין ייבוא" in document
    assert 'aria-label="אחוז המטלות שהושלמו"' in document


def test_populated_dashboard_view_renders_all_required_sections() -> None:
    state = DashboardViewModel(DashboardService(_FakeRepository(_populated_data()), clock=lambda: NOW)).build()

    document = DashboardView().render(state)

    for heading in ("סדר היום", "מטלות קרובות", "מבט שבועי", "מצב המטלות", "ייבוא אחרון"):
        assert heading in document
    assert "סמסטר נוכחי" in document
    assert "קורסים פעילים" in document
    assert "הצגת הכול" in document
    assert 'aria-current="page"' in document
    assert 'aria-valuenow="20"' in document


def test_dashboard_presentation_has_no_infrastructure_dependency() -> None:
    paths = (
        PROJECT_ROOT / "src" / "semester_pilot" / "ui" / "screens" / "dashboard_view.py",
        PROJECT_ROOT / "src" / "semester_pilot" / "ui" / "view_models" / "dashboard_view_model.py",
    )
    imported_modules: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported_modules.extend(
            node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None
        )

    assert not any("infrastructure" in module or "sqlite" in module for module in imported_modules)
