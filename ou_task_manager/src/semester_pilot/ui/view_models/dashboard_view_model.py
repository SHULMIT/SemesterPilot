from __future__ import annotations

from datetime import date, datetime
from typing import Protocol

from semester_pilot.application.dashboard.models import DashboardOverview
from semester_pilot.ui.navigation import primary_navigation
from semester_pilot.ui.view_models.dashboard_models import (
    DashboardAgendaState,
    DashboardAssignmentState,
    DashboardCountState,
    DashboardState,
    RecentImportState,
)

_EVENT_PRESENTATION = {
    "LESSON": ("שיעור", "info", "◫"),
    "EXAM": ("בחינה", "danger", "◇"),
    "ASSIGNMENT_DEADLINE": ("הגשה", "warning", "✓"),
}
_PRIORITY_PRESENTATION = {
    "LOW": ("נמוכה", "neutral"),
    "NORMAL": ("רגילה", "info"),
    "HIGH": ("גבוהה", "warning"),
    "URGENT": ("דחופה", "danger"),
}
_STATUS_PRESENTATION = {
    "NOT_STARTED": ("עוד לא התחלתי", "neutral"),
    "IN_PROGRESS": ("בתהליך", "info"),
    "WORK_COMPLETED": ("העבודה הושלמה", "success"),
    "SUBMITTED": ("הוגשה", "success"),
    "OVERDUE": ("באיחור", "danger"),
    "SKIPPED": ("דולגה", "neutral"),
}
_HEBREW_WEEKDAYS = ("יום שני", "יום שלישי", "יום רביעי", "יום חמישי", "יום שישי", "שבת", "יום ראשון")
_HEBREW_MONTHS = (
    "ינואר",
    "פברואר",
    "מרץ",
    "אפריל",
    "מאי",
    "יוני",
    "יולי",
    "אוגוסט",
    "ספטמבר",
    "אוקטובר",
    "נובמבר",
    "דצמבר",
)


class DashboardLoader(Protocol):
    def load(self) -> DashboardOverview: ...


class DashboardViewModel:
    """Maps the dashboard use-case result to immutable Hebrew display state."""

    def __init__(self, loader: DashboardLoader) -> None:
        self._loader = loader

    def build(self) -> DashboardState:
        overview = self._loader.load()
        hour = overview.generated_at.hour
        greeting = "בוקר טוב" if hour < 12 else "צהריים טובים" if hour < 18 else "ערב טוב"
        agenda = tuple(
            DashboardAgendaState(
                title=item.title,
                course_name=item.course_name,
                time_label=item.starts_at.strftime("%H:%M"),
                type_label=_EVENT_PRESENTATION[item.event_type.value][0],
                tone=_EVENT_PRESENTATION[item.event_type.value][1],
                icon=_EVENT_PRESENTATION[item.event_type.value][2],
            )
            for item in overview.todays_agenda
        )
        assignments = tuple(
            DashboardAssignmentState(
                title=item.title,
                course_code=item.course_code,
                course_name=item.course_name,
                due_label=self._date_label(item.due_at),
                priority_label=_PRIORITY_PRESENTATION[item.priority.value][0],
                priority_tone=_PRIORITY_PRESENTATION[item.priority.value][1],
                status_label=_STATUS_PRESENTATION[item.status.value][0],
                status_tone=_STATUS_PRESENTATION[item.status.value][1],
            )
            for item in overview.upcoming_assignments
        )
        weekly = (
            DashboardCountState("מטלות להגשה", overview.weekly.assignments_due, "turquoise", "✓"),
            DashboardCountState("בחינות", overview.weekly.exams, "violet", "◇"),
            DashboardCountState("שיעורים", overview.weekly.lessons, "neutral", "◫"),
        )
        progress = (
            DashboardCountState("הושלמו", overview.progress.completed, "success", "✓"),
            DashboardCountState("נשארו", overview.progress.remaining, "info", "○"),
            DashboardCountState("באיחור", overview.progress.overdue, "danger", "!"),
        )
        recent = overview.recent_import
        recent_state = (
            RecentImportState(
                synchronized_label=self._date_time_label(recent.synchronized_at),
                source_label=recent.scope.source_id.replace("-", " ").title(),
                summary=(
                    f"{recent.added_count} חדשים · {recent.updated_count} עודכנו · "
                    f"{recent.unchanged_count} ללא שינוי · {recent.missing_count} חסרים"
                ),
            )
            if recent
            else None
        )
        return DashboardState(
            greeting=greeting,
            date_label=self._date_label(overview.generated_at),
            semester_label=overview.current_semester or "טרם זוהה סמסטר",
            active_course_count=overview.active_course_count,
            navigation=primary_navigation("overview"),
            agenda=agenda,
            assignments=assignments,
            weekly=weekly,
            progress=progress,
            completion_percent=overview.progress.completion_percent,
            recent_import=recent_state,
        )

    @staticmethod
    def _date_label(value: date | datetime) -> str:
        return f"{_HEBREW_WEEKDAYS[value.weekday()]}, {value.day} ב{_HEBREW_MONTHS[value.month - 1]}"

    @classmethod
    def _date_time_label(cls, value: datetime) -> str:
        return f"{cls._date_label(value)} · {value.strftime('%H:%M')}"
