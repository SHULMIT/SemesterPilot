from __future__ import annotations

import ast
from pathlib import Path

import pytest

from semester_pilot.ui.components import (
    alert,
    badge,
    button,
    empty_state,
    loading_state,
    select_input,
    status_chip,
    text_input,
)
from semester_pilot.ui.screens.prototype_view import PrototypeView
from semester_pilot.ui.view_models.prototype_view_model import PrototypeViewModel

PROJECT_ROOT = Path(__file__).parents[2]
UI_ROOT = PROJECT_ROOT / "src" / "semester_pilot" / "ui"


@pytest.fixture
def view_model() -> PrototypeViewModel:
    return PrototypeViewModel()


@pytest.fixture
def view() -> PrototypeView:
    return PrototypeView()


def test_view_model_prepares_deterministic_ui_ready_state(view_model: PrototypeViewModel) -> None:
    state = view_model.build("import")

    assert state.page_key == "import"
    assert state.page_title == "תצוגה מקדימה לייבוא"
    assert state.import_preview.is_safe is True
    assert {metric.key: metric.value for metric in state.import_preview.metrics} == {
        "new": 6,
        "updated": 3,
        "unchanged": 13,
        "missing": 1,
        "ambiguous": 1,
        "unsafe": 0,
    }
    assert all(assignment.course.code for assignment in state.assignments)


def test_unknown_page_uses_safe_overview_state(view_model: PrototypeViewModel) -> None:
    assert view_model.build("not-a-page").page_key == "overview"


def test_presentation_layer_has_no_infrastructure_or_database_imports() -> None:
    forbidden_roots = {"sqlite3"}
    forbidden_segments = {"infrastructure", "repositories", "calendar", "synchronization"}
    violations: list[str] = []

    for path in UI_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            for module in modules:
                parts = set(module.split("."))
                if module.split(".")[0] in forbidden_roots or parts & forbidden_segments:
                    violations.append(f"{path.relative_to(PROJECT_ROOT)} imports {module}")

    assert violations == []


def test_document_is_hebrew_rtl_and_has_semantic_landmarks(view_model: PrototypeViewModel, view: PrototypeView) -> None:
    document = view.render(view_model.build())

    assert '<html lang="he" dir="rtl">' in document
    assert '<aside class="sidebar"' in document
    assert 'aria-label="ניווט ראשי"' in document
    assert '<main id="main-content"' in document
    assert '<header class="topbar">' in document


def test_navigation_renders_all_placeholders_and_active_state(
    view_model: PrototypeViewModel, view: PrototypeView
) -> None:
    document = view.render(view_model.build("import"))

    for label in ("סקירה", "מטלות", "לוח שנה", "קורסים", "תכנון שבועי", "ייבוא לוח שנה", "הגדרות"):
        assert label in document
    assert 'class="nav-link is-active"' in document
    assert 'aria-current="page"' in document


def test_reusable_components_render_semantics_and_labels() -> None:
    rendered = "".join(
        (
            button("שמירה"),
            button("ביטול", variant="secondary"),
            badge("חדש", tone="success"),
            status_chip("בתהליך", tone="info"),
            text_input("course", "שם קורס", "הקלידו שם"),
            select_input("semester", "סמסטר", ("א", "ב")),
            alert("שגיאה", "אפשר לנסות שוב", tone="danger"),
        )
    )

    assert 'class="button button--primary"' in rendered
    assert 'class="button button--secondary"' in rendered
    assert '<label for="course">שם קורס</label>' in rendered
    assert '<label for="semester">סמסטר</label>' in rendered
    assert 'role="alert"' in rendered


def test_empty_loading_error_and_dialog_states_render_accessibly(
    view_model: PrototypeViewModel, view: PrototypeView
) -> None:
    document = view.render(view_model.build("states"))

    assert "הכול נקי כאן" in document
    assert 'role="status" aria-live="polite"' in document
    assert 'role="alert"' in document
    assert '<dialog class="dialog"' in document
    assert 'aria-labelledby="dialog-title"' in document
    assert 'aria-describedby="dialog-description"' in document
    assert 'aria-label="סגירת חלון"' in document
    assert "data-dialog-open" in document


def test_component_state_helpers_have_screen_reader_friendly_output() -> None:
    assert 'aria-labelledby="empty-title"' in empty_state("ריק", "אין תוכן")
    assert 'aria-live="polite"' in loading_state("טוענים")


def test_import_preview_renders_every_result_category_without_real_action(
    view_model: PrototypeViewModel, view: PrototypeView
) -> None:
    document = view.render(view_model.build("import"))

    for label in ("חדשים", "עודכנו", "ללא שינוי", "חסרים", "דורשים בדיקה", "לא בטוחים"):
        assert label in document
    assert "שום שינוי לא יבוצע" in document
    assert "סנכרון אינו זמין באב־טיפוס" in document
    assert 'disabled aria-disabled="true"' in document
    assert 'type="file"' not in document


def test_accessibility_foundation_includes_skip_focus_progress_and_reduced_motion(
    view_model: PrototypeViewModel, view: PrototypeView
) -> None:
    document = view.render(view_model.build())
    css = (PROJECT_ROOT / "static" / "prototype.css").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "static" / "prototype.js").read_text(encoding="utf-8")

    assert 'class="skip-link" href="#main-content"' in document
    assert ":focus-visible" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert 'role="progressbar"' in document
    assert 'aria-valuenow="62"' in document
    assert 'aria-controls="primary-navigation"' in document
    assert "showModal" in javascript
    assert "dialog.close()" in javascript


def test_design_tokens_cover_required_categories() -> None:
    css = (PROJECT_ROOT / "static" / "prototype.css").read_text(encoding="utf-8")

    for token_prefix in (
        "--color-",
        "--font-",
        "--space-",
        "--radius-",
        "--shadow-",
        "--breakpoint-",
        "--transition-",
    ):
        assert token_prefix in css
    for semantic_state in ("success", "info", "warning", "danger"):
        assert f"--color-{semantic_state}" in css
    assert "@import" not in css
