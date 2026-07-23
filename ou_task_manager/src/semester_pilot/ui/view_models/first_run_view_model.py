from __future__ import annotations

from dataclasses import replace
from threading import Lock
from typing import Protocol

from semester_pilot.application.import_workflow import (
    CalendarImportCompletion,
    CalendarWorkflowError,
    ImportChangeSummary,
    PreparedCalendarImport,
)
from semester_pilot.ui.view_models.first_run_models import (
    FirstRunState,
    FirstRunStep,
    ResultMetricState,
)


class CalendarImportWorkflow(Protocol):
    def prepare(self, filename: str, content: str | None) -> PreparedCalendarImport: ...

    def confirm(self, prepared: PreparedCalendarImport) -> CalendarImportCompletion: ...


class FirstRunViewModel:
    """Owns first-run presentation state and invokes the injected import use case."""

    def __init__(self, workflow: CalendarImportWorkflow) -> None:
        self._workflow = workflow
        self._lock = Lock()
        self._busy = False
        self._prepared: PreparedCalendarImport | None = None
        self._state = self._welcome_state()

    @property
    def state(self) -> FirstRunState:
        with self._lock:
            return self._state

    def select_file(self, filename: str, content: str | None) -> bool:
        if not self._begin(
            FirstRunState(
                step=FirstRunStep.LOADING,
                title="בודקים את לוח השנה",
                description="קוראים ומנתחים את האירועים. זה אמור לקחת רק רגע.",
                is_busy=True,
                progress=35,
                filename=filename or None,
            )
        ):
            return False
        try:
            prepared = self._workflow.prepare(filename, content)
            summary = prepared.summary
            warnings = tuple(warning.message for warning in prepared.preview.warnings)
            if not summary.is_safe:
                warnings += tuple(self._safety_message(reason) for reason in summary.skipped_reasons)
            with self._lock:
                self._prepared = prepared
                self._state = FirstRunState(
                    step=FirstRunStep.PREVIEW,
                    title="לוח השנה מוכן לבדיקה",
                    description="עברו על הסיכום לפני שמאשרים את הסנכרון.",
                    filename=prepared.filename,
                    metrics=self._metrics(summary),
                    warnings=warnings,
                    can_confirm=summary.is_safe,
                    progress=70,
                )
        except CalendarWorkflowError as exc:
            self._set_error(exc.user_message, filename)
        except Exception:
            self._set_error("משהו השתבש בזמן בדיקת הקובץ. הנתונים הקיימים לא השתנו.", filename)
        finally:
            self._end()
        return True

    def confirm(self) -> bool:
        with self._lock:
            prepared = self._prepared
        if prepared is None:
            self._set_error("אין תצוגה מקדימה לאישור. בחרו קובץ ICS תחילה.", None)
            return False
        if not self._begin(
            FirstRunState(
                step=FirstRunStep.SYNCHRONIZING,
                title="מסנכרנים את לוח השנה",
                description="שומרים את האירועים בבטחה. אין לסגור את החלון.",
                is_busy=True,
                progress=85,
                filename=prepared.filename,
            )
        ):
            return False
        try:
            completion = self._workflow.confirm(prepared)
            with self._lock:
                self._prepared = None
                self._state = FirstRunState(
                    step=FirstRunStep.SUCCESS,
                    title="הכול מוכן ללמידה",
                    description="לוח השנה סונכרן בהצלחה והמרחב האישי שלך מוכן.",
                    progress=100,
                    filename=prepared.filename,
                    metrics=self._metrics(completion.summary),
                    elapsed_label=self._elapsed_label(completion.elapsed_seconds),
                    total_processed=completion.total_processed,
                )
        except CalendarWorkflowError as exc:
            self._set_error(exc.user_message, prepared.filename)
        except Exception:
            self._set_error("הסנכרון לא הושלם. כל השינויים בוטלו ואפשר לנסות שוב.", prepared.filename)
        finally:
            self._end()
        return True

    def reset(self) -> bool:
        with self._lock:
            if self._busy:
                return False
            self._prepared = None
            self._state = self._welcome_state()
        return True

    def continue_to_dashboard(self) -> bool:
        with self._lock:
            if self._busy or self._state.step is not FirstRunStep.SUCCESS:
                return False
            self._state = FirstRunState(
                step=FirstRunStep.DASHBOARD,
                title="המרחב שלך מוכן",
                description="הייבוא הראשון הושלם. ניהול המטלות המלא יתווסף באבן הדרך הבאה.",
            )
        return True

    def _begin(self, state: FirstRunState) -> bool:
        with self._lock:
            if self._busy:
                return False
            self._busy = True
            self._state = state
        return True

    def _end(self) -> None:
        with self._lock:
            self._busy = False
            if self._state.is_busy:
                self._state = replace(self._state, is_busy=False)

    def _set_error(self, message: str, filename: str | None) -> None:
        with self._lock:
            self._state = FirstRunState(
                step=FirstRunStep.ERROR,
                title="לא הצלחנו להשלים את הייבוא",
                description="אפשר לתקן את הבעיה ולנסות שוב.",
                filename=filename,
                error_message=message,
            )

    @staticmethod
    def _metrics(summary: ImportChangeSummary) -> tuple[ResultMetricState, ...]:
        return (
            ResultMetricState("new", "חדשים", summary.added, "success"),
            ResultMetricState("updated", "יעודכנו", summary.updated, "info"),
            ResultMetricState("unchanged", "ללא שינוי", summary.unchanged, "neutral"),
            ResultMetricState("missing", "חסרים", summary.missing, "warning"),
            ResultMetricState("ambiguous", "דורשים בדיקה", summary.ambiguous, "danger"),
            ResultMetricState(
                "unsafe",
                "אזהרות בטיחות",
                len(summary.skipped_reasons),
                "danger" if not summary.is_safe else "neutral",
            ),
        )

    @staticmethod
    def _elapsed_label(seconds: float) -> str:
        if seconds < 0.1:
            return "פחות משנייה"
        return f"{seconds:.1f} שניות"

    @staticmethod
    def _safety_message(reason: str) -> str:
        messages = {
            "incomplete-snapshot": "הקובץ אינו שלם ולכן הסנכרון נחסם כדי להגן על הנתונים.",
            "unresolved-duplicates": "נמצאו אירועים כפולים שדורשים בדיקה לפני הסנכרון.",
        }
        return messages.get(reason, "נמצאה אזהרת בטיחות שחוסמת את הסנכרון.")

    @staticmethod
    def _welcome_state() -> FirstRunState:
        return FirstRunState(
            step=FirstRunStep.WELCOME,
            title="מתחילים סמסטר רגוע יותר",
            description="ייבוא קצר של לוח השנה יעזור לרכז את כל המועדים במקום אחד.",
        )
