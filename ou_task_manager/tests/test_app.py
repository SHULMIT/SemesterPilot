from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import app
from semester_pilot.infrastructure.database import SQLiteDatabase
from semester_pilot.infrastructure.repositories import SQLiteAssignmentRepository


def test_init_db_creates_expected_schema(isolated_app: Path) -> None:
    with sqlite3.connect(isolated_app) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"courses", "assignments", "settings"} <= tables


def test_seed_data_is_idempotent(isolated_app: Path) -> None:
    app.seed_data()
    app.seed_data()

    with app.db() as connection:
        assert connection.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 3
        assert connection.execute("SELECT COUNT(*) FROM assignments").fetchone()[0] == 15
        assert connection.execute("SELECT COUNT(*) FROM assignments WHERE due_at IS NULL").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM assignments WHERE title = ''").fetchone()[0] == 0

    repository = SQLiteAssignmentRepository(SQLiteDatabase(isolated_app))
    assert len(repository.list_active()) == 15


def test_assignment_notes_completion_and_settings_persist(isolated_app: Path) -> None:
    with app.db() as connection:
        course_id = app.upsert_course(connection, "101", "Test course")
        app.add_assignment(connection, course_id, "01", "2099-01-02")
        assignment_id = connection.execute("SELECT id FROM assignments").fetchone()[0]
        connection.execute(
            "UPDATE assignments SET completed = 1, notes = ? WHERE id = ?",
            ("A note", assignment_id),
        )

    app.set_setting("email_to", "student@example.com")
    task = app.tasks()[0]
    assert task["completed"] == 1
    assert task["notes"] == "A note"
    assert app.setting("email_to") == "student@example.com"


def test_page_escapes_user_content(isolated_app: Path) -> None:
    with app.db() as connection:
        course_id = app.upsert_course(connection, "101", "<script>alert(1)</script>")
        app.add_assignment(connection, course_id, "01", "2099-01-02")
        connection.execute("UPDATE assignments SET notes = '<b>unsafe</b>'")

    rendered = app.page("<message>")
    assert "<script>alert(1)</script>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert 'value="&lt;b&gt;unsafe&lt;/b&gt;"' in rendered
    assert "&lt;message&gt;" in rendered


def test_default_calendar_import_is_repeatable(
    isolated_app: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = Path(app.__file__).with_name("open_university_calendar.ics")
    if not source.exists():
        pytest.skip("The private legacy calendar is not available")
    destination = tmp_path / source.name
    destination.write_bytes(source.read_bytes())
    monkeypatch.setattr(app, "BASE_DIR", tmp_path)

    parsed_count = app.import_default_ics()
    app.import_default_ics()

    assert parsed_count > 0
    with app.db() as connection:
        stored_count = connection.execute("SELECT COUNT(*) FROM assignments").fetchone()[0]
    assert stored_count <= parsed_count


def test_send_weekly_email_requires_configuration(isolated_app: Path) -> None:
    success, message = app.send_weekly_email()
    assert success is False
    assert message


def test_send_weekly_email_uses_smtp_without_network(isolated_app: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app.set_setting("email_to", "student@example.com")
    monkeypatch.setattr(
        app,
        "load_env",
        lambda: {"GMAIL_USER": "sender@example.com", "GMAIL_APP_PASSWORD": "secret"},
    )
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    monkeypatch.setattr(app.smtplib, "SMTP_SSL", MagicMock(return_value=smtp))

    success, _ = app.send_weekly_email()

    assert success is True
    smtp.login.assert_called_once_with("sender@example.com", "secret")
    smtp.send_message.assert_called_once()
    assert app.setting("last_email_sent")
