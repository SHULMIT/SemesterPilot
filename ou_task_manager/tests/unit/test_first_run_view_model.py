from __future__ import annotations

from threading import Event, Thread

from semester_pilot.application.calendar.models import ImportPreview, SnapshotSafety
from semester_pilot.application.import_workflow import (
    CalendarImportCompletion,
    CalendarWorkflowError,
    PreparedCalendarImport,
    WorkflowErrorCode,
)
from semester_pilot.application.synchronization.models import SyncItem, SyncScope, SynchronizationResult
from semester_pilot.ui.screens.first_run_view import FirstRunView
from semester_pilot.ui.view_models.first_run_models import FirstRunStep
from semester_pilot.ui.view_models.first_run_view_model import FirstRunViewModel


def _prepared(*, unsafe: bool = False) -> PreparedCalendarImport:
    preview = ImportPreview(
        source_id="source",
        events=(),
        courses=(),
        assignments=(),
        potential_duplicates=(),
        unknown_event_indexes=(),
        warnings=(),
        safety=SnapshotSafety(not unsafe, not unsafe, ("incomplete-snapshot",) if unsafe else ()),
    )
    result = SynchronizationResult(
        added=(SyncItem(1, None), SyncItem(2, None)),
        updated=(SyncItem(3, 3),),
        unchanged=(SyncItem(4, 4),),
        missing=(SyncItem(None, 5),),
        skipped_reasons=("incomplete-snapshot",) if unsafe else (),
    )
    return PreparedCalendarImport("calendar.ics", preview, SyncScope("source", "institution", "2027"), result)


class _FakeWorkflow:
    def __init__(self, prepared: PreparedCalendarImport | None = None) -> None:
        self.prepared = prepared or _prepared()
        self.prepare_calls = 0
        self.confirm_calls = 0

    def prepare(self, _filename: str, _content: str | None) -> PreparedCalendarImport:
        self.prepare_calls += 1
        return self.prepared

    def confirm(self, _prepared: PreparedCalendarImport) -> CalendarImportCompletion:
        self.confirm_calls += 1
        return CalendarImportCompletion(self.prepared.synchronization_preview, 0.42)


def test_complete_first_run_state_transition() -> None:
    workflow = _FakeWorkflow()
    view_model = FirstRunViewModel(workflow)

    assert view_model.state.step is FirstRunStep.WELCOME
    assert view_model.select_file("calendar.ics", "content")
    assert view_model.state.step is FirstRunStep.PREVIEW
    assert view_model.state.can_confirm
    assert {metric.key: metric.value for metric in view_model.state.metrics}["new"] == 2

    assert view_model.confirm()
    assert view_model.state.step is FirstRunStep.SUCCESS
    assert view_model.state.progress == 100
    assert view_model.state.total_processed == 4
    assert view_model.state.elapsed_label == "0.4 שניות"

    assert view_model.continue_to_dashboard()
    assert view_model.state.step is FirstRunStep.DASHBOARD
    assert workflow.prepare_calls == 1
    assert workflow.confirm_calls == 1


class _FailingWorkflow(_FakeWorkflow):
    def prepare(self, _filename: str, _content: str | None) -> PreparedCalendarImport:
        raise CalendarWorkflowError(WorkflowErrorCode.PARSER_ERROR, "הודעה ידידותית")


def test_parser_failure_transitions_to_friendly_error_state() -> None:
    view_model = FirstRunViewModel(_FailingWorkflow())

    view_model.select_file("broken.ics", "content")

    assert view_model.state.step is FirstRunStep.ERROR
    assert view_model.state.error_message == "הודעה ידידותית"
    assert not view_model.state.is_busy


def test_unsafe_snapshot_disables_confirmation_and_displays_warning() -> None:
    workflow = _FakeWorkflow(_prepared(unsafe=True))
    view_model = FirstRunViewModel(workflow)

    view_model.select_file("unsafe.ics", "content")

    assert view_model.state.step is FirstRunStep.PREVIEW
    assert not view_model.state.can_confirm
    assert view_model.state.warnings
    document = FirstRunView().render(view_model.state)
    assert 'disabled aria-disabled="true"' in document
    assert 'role="alert"' in document


class _BlockingWorkflow(_FakeWorkflow):
    def __init__(self) -> None:
        super().__init__()
        self.started = Event()
        self.release = Event()

    def prepare(self, filename: str, content: str | None) -> PreparedCalendarImport:
        self.prepare_calls += 1
        self.started.set()
        self.release.wait(timeout=5)
        return self.prepared


def test_duplicate_file_actions_are_rejected_while_import_is_in_progress() -> None:
    workflow = _BlockingWorkflow()
    view_model = FirstRunViewModel(workflow)
    first = Thread(target=view_model.select_file, args=("first.ics", "content"))
    first.start()
    assert workflow.started.wait(timeout=2)

    assert not view_model.select_file("second.ics", "content")
    assert view_model.state.step is FirstRunStep.LOADING
    assert view_model.state.is_busy

    workflow.release.set()
    first.join(timeout=2)
    assert workflow.prepare_calls == 1
    assert view_model.state.step is FirstRunStep.PREVIEW


def test_confirmation_without_preview_is_rejected() -> None:
    view_model = FirstRunViewModel(_FakeWorkflow())

    assert not view_model.confirm()
    assert view_model.state.step is FirstRunStep.ERROR


def test_first_run_screens_render_required_controls_and_accessibility() -> None:
    view_model = FirstRunViewModel(_FakeWorkflow())
    welcome = FirstRunView().render(view_model.state)
    assert '<html lang="he" dir="rtl">' in welcome
    assert 'type="file"' in welcome
    assert 'accept=".ics,text/calendar"' in welcome
    assert "data-file-form" in welcome
    assert 'id="main-content"' in welcome

    view_model.select_file("calendar.ics", "content")
    preview = FirstRunView().render(view_model.state)
    for label in ("חדשים", "יעודכנו", "ללא שינוי", "חסרים", "דורשים בדיקה", "אזהרות בטיחות"):
        assert label in preview
    assert "data-confirm-import" in preview

    view_model.confirm()
    success = FirstRunView().render(view_model.state)
    assert "אירועים יובאו" in success
    assert "עודכנו" in success
    assert "זמן הסנכרון" in success
    assert "data-continue-dashboard" in success


def test_client_script_prevents_duplicate_requests_and_handles_unreadable_files() -> None:
    script = (__import__("pathlib").Path(__file__).parents[2] / "static" / "prototype.js").read_text(encoding="utf-8")

    assert "requestInFlight" in script
    assert "if (requestInFlight) return" in script
    assert "content: null" in script
