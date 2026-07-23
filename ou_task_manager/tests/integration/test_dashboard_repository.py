from __future__ import annotations

from datetime import datetime
from pathlib import Path

from semester_pilot.application.dashboard import DashboardService
from semester_pilot.application.import_workflow import CalendarImportWorkflowService
from semester_pilot.application.synchronization import CalendarSyncService
from semester_pilot.infrastructure.calendar_import import create_open_university_import_service
from semester_pilot.infrastructure.dashboard import SQLiteDashboardRepository
from semester_pilot.infrastructure.database import SQLiteDatabase
from semester_pilot.infrastructure.migrations import SQLiteMigrator
from semester_pilot.infrastructure.synchronization import SQLiteCalendarSyncUnitOfWork

FIXTURES = Path(__file__).parents[1] / "fixtures" / "calendars"


def test_sqlite_dashboard_uses_latest_import_scope_and_real_persisted_data(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "dashboard.db")
    SQLiteMigrator(database).migrate()
    sync = CalendarSyncService(lambda: SQLiteCalendarSyncUnitOfWork(database))
    workflow = CalendarImportWorkflowService(create_open_university_import_service(), sync, "Open University of Israel")
    text = (FIXTURES / "normal.ics").read_text(encoding="utf-8")
    workflow.confirm(workflow.prepare("normal.ics", text))

    overview = DashboardService(SQLiteDashboardRepository(database), clock=lambda: datetime(2027, 8, 15, 9)).load()

    assert overview.current_semester is not None
    assert overview.current_semester.endswith("2027")
    assert overview.active_course_count == 1
    assert len(overview.upcoming_assignments) == 1
    assert overview.upcoming_assignments[0].course_code == "12345"
    assert overview.todays_agenda
    assert overview.recent_import is not None
    assert overview.recent_import.added_count == 4
    assert overview.recent_import.scope.source_id == "open-university-hebrew-calendar"
