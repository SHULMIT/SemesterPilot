from __future__ import annotations

from dataclasses import replace
from threading import Lock
from typing import Mapping, Protocol
from semester_pilot.application.subtask_management import SaveSubtask, SubtaskManagementService, SubtaskValidationError

from semester_pilot.application.assignment_management import (
    AssignmentFilter,
    AssignmentQuery,
    AssignmentRecord,
    AssignmentSort,
    AssignmentValidationError,
    EditAssignmentCommand,
    StaleAssignmentError,
)
from semester_pilot.application.assignment_management.models import AssignmentListResult
from semester_pilot.domain.enums import AssignmentStatus, PriorityLevel
from semester_pilot.ui.navigation import primary_navigation
from semester_pilot.ui.view_models.assignment_models import (
    AssignmentDetailState,
    AssignmentListItemState,
    AssignmentListState,
    SubtaskItemState,
)

_STATUS = {
    "NOT_STARTED": ("עוד לא התחלתי", "neutral"),
    "IN_PROGRESS": ("בתהליך", "info"),
    "WORK_COMPLETED": ("הושלמה", "success"),
    "SUBMITTED": ("הוגשה", "success"),
    "OVERDUE": ("באיחור", "danger"),
    "SKIPPED": ("דולגה", "neutral"),
}
_PRIORITY = {
    "LOW": ("נמוכה", "neutral"),
    "NORMAL": ("רגילה", "info"),
    "HIGH": ("גבוהה", "warning"),
    "URGENT": ("דחופה", "danger"),
}


class AssignmentUseCases(Protocol):
    def list_page(self, query: AssignmentQuery) -> AssignmentListResult: ...

    def get(self, assignment_id: int) -> AssignmentRecord: ...

    def update(self, command: EditAssignmentCommand) -> AssignmentRecord: ...


class AssignmentViewModel:
    """Prepares assignment list/detail state and guards duplicate saves."""

    def __init__(self, service: AssignmentUseCases, subtasks: SubtaskManagementService | None = None) -> None:
        self._service = service
        self._subtasks = subtasks
        self._lock = Lock()
        self._saving = False

    def build_list(self, parameters: Mapping[str, tuple[str, ...]]) -> AssignmentListState:
        filters = frozenset(item for value in parameters.get("filter", ()) if (item := self._filter(value)) is not None)
        priority = self._priority(parameters.get("priority", ("",))[0])
        sort = self._sort(parameters.get("sort", (AssignmentSort.DUE_SOON.value,))[0])
        search = parameters.get("search", ("",))[0]
        course = parameters.get("course", ("",))[0]
        result = self._service.list_page(AssignmentQuery(search, filters, course or None, priority, sort))
        return AssignmentListState(
            navigation=primary_navigation("assignments"),
            assignments=tuple(
                self._list_item(record, record.id in result.overdue_ids) for record in result.assignments
            ),
            courses=result.courses,
            search=search,
            selected_filters=tuple(item.value for item in filters),
            selected_course=course,
            selected_priority=priority.value if priority else "",
            selected_sort=sort.value,
        )

    def build_detail(self, assignment_id: int) -> AssignmentDetailState:
        return self._detail(self._service.get(assignment_id))

    def save_subtask(self, assignment_id: int, values: Mapping[str, str]) -> tuple[bool, AssignmentDetailState]:
        if not self._subtasks:
            return False, self.build_detail(assignment_id)
        with self._lock:
            if self._saving:
                return False, self._with_subtask_feedback(assignment_id, "שמירה כבר מתבצעת.", values)
            self._saving = True
        try:
            self._subtasks.save(
                SaveSubtask(
                    assignment_id=assignment_id,
                    subtask_id=self._optional_integer(values.get("subtask_id")),
                    expected_version=self._optional_integer(values.get("version")),
                    title=values.get("title", ""),
                    notes=values.get("notes", ""),
                    estimated_minutes=self._optional_integer(values.get("estimated_minutes")),
                )
            )
            state = self._with_subtask_feedback(assignment_id, success="תת־המשימה נשמרה.")
        except SubtaskValidationError as exc:
            state = self._with_subtask_feedback(assignment_id, " ".join(exc.errors.values()), values)
        except Exception as exc:
            state = self._with_subtask_feedback(assignment_id, str(exc) or "שמירת תת־המשימה נכשלה.", values)
        finally:
            with self._lock:
                self._saving = False
        return True, state

    def subtask_action(self, assignment_id: int, values: Mapping[str, str]) -> tuple[bool, AssignmentDetailState]:
        if not self._subtasks:
            return False, self.build_detail(assignment_id)
        try:
            subtask_id = self._integer(values.get("subtask_id"), 0)
            version = self._integer(values.get("version"), 0)
            action = values.get("action")
            if action in {"complete", "reopen"}:
                self._subtasks.set_completed(assignment_id, subtask_id, version, action == "complete")
            elif action in {"up", "down"}:
                self._subtasks.move(assignment_id, subtask_id, version, -1 if action == "up" else 1)
            elif action == "delete":
                self._subtasks.delete(assignment_id, subtask_id, version, values.get("confirmed") == "true")
            else:
                raise ValueError("פעולה לא מוכרת.")
            return True, self._with_subtask_feedback(assignment_id, success="הפעולה הושלמה.")
        except Exception as exc:
            return True, self._with_subtask_feedback(assignment_id, str(exc) or "הפעולה נכשלה.")

    def _with_subtask_feedback(
        self,
        assignment_id: int,
        error: str | None = None,
        draft: Mapping[str, str] | None = None,
        success: str | None = None,
    ) -> AssignmentDetailState:
        return replace(
            self._detail(self._service.get(assignment_id)),
            subtask_error=error,
            subtask_draft=tuple((draft or {}).items()),
            success_message=success,
        )

    def save(self, assignment_id: int, values: Mapping[str, str]) -> tuple[bool, AssignmentDetailState]:
        with self._lock:
            if self._saving:
                return False, self._attempted_state(assignment_id, values, "השמירה כבר מתבצעת.")
            self._saving = True
        try:
            command = EditAssignmentCommand(
                assignment_id=assignment_id,
                expected_version=self._integer(values.get("version"), 0),
                priority=values.get("priority", ""),
                notes=values.get("notes", ""),
                estimated_minutes=self._optional_integer(values.get("estimated_minutes")),
                progress_percentage=self._integer(values.get("progress_percentage"), -1),
                is_completed=values.get("is_completed") == "true",
            )
            updated = self._service.update(command)
            state = self._detail(updated, success="השינויים נשמרו בהצלחה.")
        except AssignmentValidationError as exc:
            state = self._attempted_state(assignment_id, values, field_errors=exc.field_errors)
        except StaleAssignmentError as exc:
            state = self._attempted_state(assignment_id, values, str(exc))
        except (TypeError, ValueError):
            state = self._attempted_state(
                assignment_id, values, field_errors={"form": "יש להזין ערכים מספריים תקינים."}
            )
        except Exception:
            state = self._attempted_state(
                assignment_id, values, "השמירה נכשלה. הפרטים שהזנת נשמרו בטופס ואפשר לנסות שוב."
            )
        finally:
            with self._lock:
                self._saving = False
        return True, state

    def _attempted_state(
        self,
        assignment_id: int,
        values: Mapping[str, str],
        global_error: str | None = None,
        field_errors: dict[str, str] | None = None,
    ) -> AssignmentDetailState:
        current = self._detail(self._service.get(assignment_id))
        return AssignmentDetailState(
            id=current.id,
            title=current.title,
            course_label=current.course_label,
            due_label=current.due_label,
            description=current.description,
            imported_event_label=current.imported_event_label,
            source_identity_label=current.source_identity_label,
            location=current.location,
            is_missing=current.is_missing,
            priority=values.get("priority", current.priority),
            notes=values.get("notes", current.notes),
            estimated_minutes=values.get("estimated_minutes", current.estimated_minutes),
            progress_percentage=values.get("progress_percentage", current.progress_percentage),
            is_completed=values.get("is_completed") == "true",
            version=current.version,
            field_errors=tuple((field_errors or {}).items()),
            global_error=global_error,
        )

    @staticmethod
    def _list_item(record: AssignmentRecord, is_overdue: bool) -> AssignmentListItemState:
        return AssignmentListItemState(
            id=record.id,
            title=record.title,
            course_code=record.course_code,
            course_name=record.course_name,
            due_label=record.due_at.strftime("%d/%m/%Y"),
            status_label=_STATUS[record.status.value][0],
            status_tone=_STATUS[record.status.value][1],
            priority_label=_PRIORITY[record.priority.value][0],
            priority_tone=_PRIORITY[record.priority.value][1],
            progress=record.progress_percentage,
            is_overdue=is_overdue,
            is_missing=record.is_missing_from_source,
        )

    def _detail(self, record: AssignmentRecord, success: str | None = None) -> AssignmentDetailState:
        identity = record.external_uid or "אין UID זמין"
        if record.recurrence_id:
            identity += f" · מופע {record.recurrence_id}"
        summary = self._subtasks.list(record.id) if self._subtasks else None
        return AssignmentDetailState(
            id=record.id,
            title=record.title,
            course_label=f"{record.course_name} · {record.course_code}",
            due_label=record.due_at.strftime("%d/%m/%Y · %H:%M"),
            description=record.description,
            imported_event_label=(record.imported_event_type or "אירוע מטלה מיובא").replace("_", " "),
            source_identity_label=identity,
            location=record.imported_location,
            is_missing=record.is_missing_from_source,
            priority=record.priority.value,
            notes=record.notes,
            estimated_minutes=str(record.estimated_minutes or ""),
            progress_percentage=str(record.progress_percentage),
            is_completed=record.status in {AssignmentStatus.WORK_COMPLETED, AssignmentStatus.SUBMITTED},
            version=record.version,
            success_message=success,
            subtasks=tuple(
                SubtaskItemState(
                    item.id,
                    item.title,
                    item.notes,
                    item.completed,
                    str(item.estimated_minutes or ""),
                    item.position,
                    item.version,
                )
                for item in summary.items
            )
            if summary
            else (),
            subtask_completed=summary.completed_count if summary else 0,
            subtask_total=summary.total_count if summary else 0,
            subtask_percentage=summary.percentage if summary else 0,
        )

    @staticmethod
    def _filter(value: str) -> AssignmentFilter | None:
        try:
            return AssignmentFilter(value)
        except ValueError:
            return None

    @staticmethod
    def _priority(value: str) -> PriorityLevel | None:
        try:
            return PriorityLevel(value) if value else None
        except ValueError:
            return None

    @staticmethod
    def _sort(value: str) -> AssignmentSort:
        try:
            return AssignmentSort(value)
        except ValueError:
            return AssignmentSort.DUE_SOON

    @staticmethod
    def _integer(value: str | None, default: int) -> int:
        return int(value) if value not in {None, ""} else default

    @staticmethod
    def _optional_integer(value: str | None) -> int | None:
        return int(value) if value not in {None, ""} else None
