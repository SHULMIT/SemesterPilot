from .models import SaveSubtask, Subtask, SubtaskNotFoundError, SubtaskSummary, SubtaskValidationError
from .ports import SubtaskRepository

TITLE_LIMIT = 200
NOTES_LIMIT = 10_000


class SubtaskManagementService:
    def __init__(self, repository: SubtaskRepository) -> None:
        self._repository = repository

    def list(self, assignment_id: int) -> SubtaskSummary:
        items = self._repository.list_for_assignment(assignment_id)
        completed = sum(item.completed for item in items)
        return SubtaskSummary(items, completed, len(items), round(completed * 100 / len(items)) if items else 0)

    def save(self, command: SaveSubtask) -> Subtask:
        title = command.title.strip()
        notes = command.notes.strip()
        errors: dict[str, str] = {}
        if not title:
            errors["title"] = "יש להזין כותרת."
        elif len(title) > TITLE_LIMIT:
            errors["title"] = f"הכותרת יכולה להכיל עד {TITLE_LIMIT} תווים."
        if len(notes) > NOTES_LIMIT:
            errors["notes"] = f"ההערות יכולות להכיל עד {NOTES_LIMIT} תווים."
        if command.estimated_minutes is not None and command.estimated_minutes <= 0:
            errors["estimated_minutes"] = "הזמן המשוער חייב להיות חיובי."
        if errors:
            raise SubtaskValidationError(errors)
        if command.subtask_id is None:
            return self._repository.create(command.assignment_id, title, notes, command.estimated_minutes)
        existing = self._owned(command.assignment_id, command.subtask_id)
        if command.expected_version is None:
            raise SubtaskValidationError({"version": "גרסת העריכה חסרה."})
        return self._repository.update(existing.id, command.expected_version, title, notes, command.estimated_minutes)

    def set_completed(self, assignment_id: int, subtask_id: int, version: int, completed: bool) -> Subtask:
        self._owned(assignment_id, subtask_id)
        return self._repository.set_completed(subtask_id, version, completed)

    def move(self, assignment_id: int, subtask_id: int, version: int, direction: int) -> SubtaskSummary:
        self._owned(assignment_id, subtask_id)
        if direction not in {-1, 1}:
            raise SubtaskValidationError({"position": "כיוון ההזזה אינו תקין."})
        self._repository.move(subtask_id, version, direction)
        return self.list(assignment_id)

    def delete(self, assignment_id: int, subtask_id: int, version: int, confirmed: bool) -> SubtaskSummary:
        self._owned(assignment_id, subtask_id)
        if not confirmed:
            raise SubtaskValidationError({"confirmation": "נדרש אישור מפורש למחיקה."})
        self._repository.delete(subtask_id, version)
        return self.list(assignment_id)

    def _owned(self, assignment_id: int, subtask_id: int) -> Subtask:
        item = self._repository.get(subtask_id)
        if item is None or item.assignment_id != assignment_id:
            raise SubtaskNotFoundError("Subtask does not belong to this assignment")
        return item
