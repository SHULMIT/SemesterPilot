from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from time import perf_counter
from typing import Protocol

from semester_pilot.application.calendar.models import ImportPreview, ImportWarning, SnapshotSafety
from semester_pilot.application.import_workflow.models import (
    CalendarImportCompletion,
    CalendarWorkflowError,
    PreparedCalendarImport,
    WorkflowErrorCode,
)
from semester_pilot.application.synchronization.models import SyncScope, SynchronizationResult


class CalendarPreviewer(Protocol):
    def preview(self, text: str) -> ImportPreview: ...


class CalendarSynchronizer(Protocol):
    def preview(self, preview: ImportPreview, scope: SyncScope) -> SynchronizationResult: ...

    def synchronize(self, preview: ImportPreview, scope: SyncScope) -> SynchronizationResult: ...


class CalendarImportWorkflowService:
    """Validates, previews, and confirms one calendar import workflow."""

    def __init__(
        self,
        import_service: CalendarPreviewer,
        synchronization_service: CalendarSynchronizer,
        institution: str,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        self._import_service = import_service
        self._synchronization_service = synchronization_service
        self._institution = institution
        self._clock = clock

    def prepare(self, filename: str, content: str | None) -> PreparedCalendarImport:
        filename = filename.strip()
        if not filename:
            raise CalendarWorkflowError(WorkflowErrorCode.INVALID_FILE, "לא נבחר קובץ לייבוא.")
        if not filename.casefold().endswith(".ics"):
            raise CalendarWorkflowError(
                WorkflowErrorCode.UNSUPPORTED_FORMAT,
                "אפשר לייבא קובץ לוח שנה בסיומת ‎.ics בלבד.",
            )
        if content is None:
            raise CalendarWorkflowError(
                WorkflowErrorCode.UNREADABLE_FILE,
                "לא הצלחנו לקרוא את הקובץ. ודאו שיש אליו גישה ונסו שוב.",
            )
        if not content.strip():
            raise CalendarWorkflowError(WorkflowErrorCode.EMPTY_CALENDAR, "הקובץ ריק ואין בו אירועי לוח שנה.")
        if "BEGIN:VCALENDAR" not in content.upper():
            raise CalendarWorkflowError(
                WorkflowErrorCode.UNSUPPORTED_FORMAT,
                "הקובץ אינו נראה כמו לוח שנה תקין מסוג ICS.",
            )
        try:
            preview = self._import_service.preview(content)
        except CalendarWorkflowError:
            raise
        except Exception as exc:
            raise CalendarWorkflowError(
                WorkflowErrorCode.PARSER_ERROR,
                "לא הצלחנו לנתח את לוח השנה. הקובץ נשאר ללא שינוי.",
            ) from exc
        if not preview.events:
            raise CalendarWorkflowError(
                WorkflowErrorCode.EMPTY_CALENDAR,
                "לא נמצאו אירועים שניתן לייבא מלוח השנה.",
            )
        preview, semester = self._select_semester(preview)
        scope = SyncScope(preview.source_id, self._institution, semester)
        sync_preview = self._synchronization_service.preview(preview, scope)
        return PreparedCalendarImport(filename, preview, scope, sync_preview)

    def confirm(self, prepared: PreparedCalendarImport) -> CalendarImportCompletion:
        if prepared.synchronization_preview.was_skipped:
            raise CalendarWorkflowError(
                WorkflowErrorCode.UNSAFE_SNAPSHOT,
                "לא ניתן לסנכרן את הקובץ עד שהאזהרות החוסמות יטופלו.",
            )
        started_at = self._clock()
        result = self._synchronization_service.synchronize(prepared.preview, prepared.scope)
        if result.was_skipped:
            raise CalendarWorkflowError(
                WorkflowErrorCode.UNSAFE_SNAPSHOT,
                "הסנכרון נעצר בבטחה והנתונים הקיימים לא השתנו.",
            )
        return CalendarImportCompletion(result, max(0.0, self._clock() - started_at))

    @staticmethod
    def _select_semester(preview: ImportPreview) -> tuple[ImportPreview, str]:
        scoped = [item for item in preview.events if item.course and item.course.semester]
        semesters = {item.course.semester for item in scoped if item.course and item.course.semester}
        if not semesters:
            return preview, str(min(item.event.starts_at.year for item in preview.events))
        if len(semesters) == 1:
            return preview, next(iter(semesters))

        # A multi-semester export has no explicit selected-semester metadata. Choose
        # its dominant semester, with the most recent matching event as a stable tie-breaker.
        semester = max(
            semesters,
            key=lambda value: (
                sum(item.course is not None and item.course.semester == value for item in scoped),
                max(item.event.starts_at for item in scoped if item.course and item.course.semester == value),
                value,
            ),
        )
        kept = tuple(item for item in preview.events if item.course and item.course.semester == semester)
        kept_indexes = {item.event.source_index for item in kept}
        duplicates = tuple(
            item
            for item in preview.potential_duplicates
            if item.first_event_index in kept_indexes and item.duplicate_event_index in kept_indexes
        )
        reasons = [reason for reason in preview.safety.blocking_reasons if reason != "unresolved-duplicates"]
        if duplicates:
            reasons.append("unresolved-duplicates")
        excluded = len(preview.events) - len(kept)
        warning = ImportWarning(
            "other-semesters-excluded",
            f"נבחר סמסטר {semester}; {excluded} אירועים מסמסטרים אחרים או ללא שיוך לסמסטר לא ייובאו.",
        )
        filtered = replace(
            preview,
            events=kept,
            courses=tuple(course for course in preview.courses if course.semester == semester),
            assignments=tuple(
                assignment for assignment in preview.assignments if assignment.event_index in kept_indexes
            ),
            potential_duplicates=duplicates,
            unknown_event_indexes=tuple(index for index in preview.unknown_event_indexes if index in kept_indexes),
            warnings=(*preview.warnings, warning),
            safety=SnapshotSafety(preview.safety.is_complete, not reasons, tuple(reasons)),
        )
        return filtered, semester
