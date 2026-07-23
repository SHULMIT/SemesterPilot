from __future__ import annotations

import json
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.request import Request, urlopen

from prototype import FirstRunHandler, compose_application
from semester_pilot.infrastructure.database import SQLiteDatabase
from semester_pilot.infrastructure.migrations import SQLiteMigrator


def test_subtask_http_create_workflow_renders_real_persisted_data(tmp_path) -> None:
    path = tmp_path / "http-synthetic.db"
    database = SQLiteDatabase(path)
    SQLiteMigrator(database).migrate()
    with database.connection() as connection:
        course_id = connection.execute(
            "INSERT INTO courses(code,name) VALUES('SYN-HTTP','Synthetic HTTP course')"
        ).lastrowid
        assignment_id = connection.execute(
            "INSERT INTO assignments(course_id,number,due_date,title,due_at,created_at,updated_at) "
            "VALUES(?,'1','2027-01-01','Synthetic assignment','2027-01-01T12:00:00',?,?)",
            (course_id, "2026-12-01T10:00:00", "2026-12-01T10:00:00"),
        ).lastrowid
    assert assignment_id is not None
    parts = compose_application(path)
    (
        FirstRunHandler.view_model,
        FirstRunHandler.view,
        FirstRunHandler.dashboard_view_model,
        FirstRunHandler.dashboard_view,
        FirstRunHandler.assignment_view_model,
        FirstRunHandler.assignment_view,
    ) = parts
    server = ThreadingHTTPServer(("127.0.0.1", 0), FirstRunHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        payload = json.dumps({"title": "Synthetic first step", "notes": "", "estimated_minutes": "15"}).encode()
        response = urlopen(
            Request(
                f"{base}/assignments/{assignment_id}/subtasks/save",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            ),
            timeout=5,
        )
        html = response.read().decode()
        assert response.status == 200
        assert "Synthetic first step" in html
        assert 'data-subtask-action="complete"' in html
        assert "data-delete-dialog" in html
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
