from __future__ import annotations

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
SOURCE_DIR = BASE_DIR / "src"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from semester_pilot.application.import_workflow import CalendarImportWorkflowService
from semester_pilot.application.dashboard import DashboardService
from semester_pilot.application.assignment_management import AssignmentManagementService
from semester_pilot.application.synchronization import CalendarSyncService
from semester_pilot.application.subtask_management import SubtaskManagementService
from semester_pilot.infrastructure.calendar_import import create_open_university_import_service
from semester_pilot.infrastructure.assignment_management import SQLiteManagedAssignmentRepository
from semester_pilot.infrastructure.dashboard import SQLiteDashboardRepository
from semester_pilot.infrastructure.database import SQLiteDatabase
from semester_pilot.infrastructure.migrations import SQLiteMigrator
from semester_pilot.infrastructure.synchronization import SQLiteCalendarSyncUnitOfWork
from semester_pilot.infrastructure.subtask_management import SQLiteSubtaskRepository
from semester_pilot.ui import (
    AssignmentView,
    AssignmentViewModel,
    DashboardView,
    DashboardViewModel,
    FirstRunView,
    FirstRunViewModel,
)
from semester_pilot.ui.theme import DEFAULT_THEME_ASSETS
from semester_pilot.ui.view_models.first_run_models import FirstRunStep

HOST, PORT = "127.0.0.1", 5050
MAX_REQUEST_BYTES = 10 * 1024 * 1024


class FirstRunHandler(BaseHTTPRequestHandler):
    """HTTP adapter composed with one injected first-run ViewModel."""

    view_model: FirstRunViewModel
    view: FirstRunView
    dashboard_view_model: DashboardViewModel
    dashboard_view: DashboardView
    assignment_view_model: AssignmentViewModel
    assignment_view: AssignmentView

    def log_message(self, *_: object) -> None:
        pass

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            self._send_html(self._render_current())
            return
        if path == "/dashboard":
            self._send_html(self.dashboard_view.render(self.dashboard_view_model.build()))
            return
        if path == "/assignments":
            parameters = {key: tuple(values) for key, values in parse_qs(urlparse(self.path).query).items()}
            self._send_html(self.assignment_view.render_list(self.assignment_view_model.build_list(parameters)))
            return
        detail_match = re.fullmatch(r"/assignments/(\d+)", path)
        if detail_match:
            self._send_html(
                self.assignment_view.render_detail(self.assignment_view_model.build_detail(int(detail_match.group(1))))
            )
            return
        if path in {"/static/prototype.css", "/static/prototype.js"}:
            asset = BASE_DIR / path.lstrip("/")
            content_type = "text/css; charset=utf-8" if asset.suffix == ".css" else "text/javascript; charset=utf-8"
            self._send(asset.read_bytes(), content_type)
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        accepted = False
        if path == "/workflow/preview":
            payload = self._json_payload()
            filename = payload.get("filename")
            content = payload.get("content")
            accepted = self.view_model.select_file(
                filename if isinstance(filename, str) else "",
                content if isinstance(content, str) else None,
            )
        elif path == "/workflow/confirm":
            accepted = self.view_model.confirm()
        elif path == "/workflow/reset":
            accepted = self.view_model.reset()
        elif path == "/workflow/dashboard":
            accepted = self.view_model.continue_to_dashboard()
        elif match := re.fullmatch(r"/assignments/(\d+)/save", path):
            payload = self._json_payload()
            values = {key: value for key, value in payload.items() if isinstance(value, str)}
            accepted, state = self.assignment_view_model.save(int(match.group(1)), values)
            self._send_html(self.assignment_view.render_detail(state), 200 if accepted else 409)
            return
        elif match := re.fullmatch(r"/assignments/(\d+)/subtasks/save", path):
            payload = self._json_payload()
            values = {key: value for key, value in payload.items() if isinstance(value, str)}
            accepted, state = self.assignment_view_model.save_subtask(int(match.group(1)), values)
            self._send_html(self.assignment_view.render_detail(state), 200 if accepted else 409)
            return
        elif match := re.fullmatch(r"/assignments/(\d+)/subtasks/action", path):
            payload = self._json_payload()
            values = {key: value for key, value in payload.items() if isinstance(value, str)}
            accepted, state = self.assignment_view_model.subtask_action(int(match.group(1)), values)
            self._send_html(self.assignment_view.render_detail(state), 200 if accepted else 409)
            return
        else:
            self.send_error(404)
            return
        self._send_html(self._render_current(), 200 if accepted else 409)

    def _render_current(self) -> str:
        if self.view_model.state.step is FirstRunStep.DASHBOARD:
            return self.dashboard_view.render(self.dashboard_view_model.build())
        return self.view.render(self.view_model.state)

    def _json_payload(self) -> dict[str, object]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return {}
        if length <= 0 or length > MAX_REQUEST_BYTES:
            return {}
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _send_html(self, content: str, status: int = 200) -> None:
        self._send(content.encode("utf-8"), "text/html; charset=utf-8", status)

    def _send(self, data: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'")
        self.end_headers()
        self.wfile.write(data)


def compose_application(
    database_path: Path | None = None,
) -> tuple[
    FirstRunViewModel,
    FirstRunView,
    DashboardViewModel,
    DashboardView,
    AssignmentViewModel,
    AssignmentView,
]:
    database = SQLiteDatabase(database_path or BASE_DIR / "tasks.db")
    SQLiteMigrator(database).migrate()
    synchronization = CalendarSyncService(lambda: SQLiteCalendarSyncUnitOfWork(database))
    workflow = CalendarImportWorkflowService(
        create_open_university_import_service(),
        synchronization,
        institution="Open University of Israel",
    )
    dashboard = DashboardService(SQLiteDashboardRepository(database))
    assignments = AssignmentManagementService(SQLiteManagedAssignmentRepository(database))
    subtasks = SubtaskManagementService(SQLiteSubtaskRepository(database))
    return (
        FirstRunViewModel(workflow),
        FirstRunView(DEFAULT_THEME_ASSETS),
        DashboardViewModel(dashboard),
        DashboardView(DEFAULT_THEME_ASSETS),
        AssignmentViewModel(assignments, subtasks),
        AssignmentView(DEFAULT_THEME_ASSETS),
    )


def run_prototype() -> None:
    (
        FirstRunHandler.view_model,
        FirstRunHandler.view,
        FirstRunHandler.dashboard_view_model,
        FirstRunHandler.dashboard_view,
        FirstRunHandler.assignment_view_model,
        FirstRunHandler.assignment_view,
    ) = compose_application()
    print(f"SemesterPilot first-run workflow: http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), FirstRunHandler).serve_forever()


if __name__ == "__main__":
    run_prototype()
