from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from semester_pilot.application.subtask_management import (
    SaveSubtask,
    Subtask,
    SubtaskManagementService,
    SubtaskValidationError,
)

NOW = datetime(2027, 1, 1)


class _Repo:
    def __init__(self) -> None:
        self.items: dict[int, Subtask] = {}
        self.next_id = 1

    def list_for_assignment(self, assignment_id: int) -> tuple[Subtask, ...]:
        return tuple(
            sorted(
                (x for x in self.items.values() if x.assignment_id == assignment_id), key=lambda x: (x.position, x.id)
            )
        )

    def get(self, subtask_id: int) -> Subtask | None:
        return self.items.get(subtask_id)

    def create(self, assignment_id: int, title: str, notes: str, estimated_minutes: int | None) -> Subtask:
        item = Subtask(
            self.next_id,
            assignment_id,
            title,
            notes,
            False,
            estimated_minutes,
            len(self.list_for_assignment(assignment_id)),
            NOW,
            NOW,
            1,
        )
        self.items[item.id] = item
        self.next_id += 1
        return item

    def update(self, subtask_id: int, version: int, title: str, notes: str, estimated_minutes: int | None) -> Subtask:
        item = self.items[subtask_id]
        updated = replace(item, title=title, notes=notes, estimated_minutes=estimated_minutes, version=version + 1)
        self.items[subtask_id] = updated
        return updated

    def set_completed(self, subtask_id: int, version: int, completed: bool) -> Subtask:
        self.items[subtask_id] = replace(self.items[subtask_id], completed=completed, version=version + 1)
        return self.items[subtask_id]

    def move(self, subtask_id: int, version: int, direction: int) -> tuple[Subtask, ...]:
        item = self.items[subtask_id]
        target = next(
            (x for x in self.list_for_assignment(item.assignment_id) if x.position == item.position + direction), None
        )
        if target:
            self.items[item.id] = replace(item, position=target.position, version=version + 1)
            self.items[target.id] = replace(target, position=item.position, version=target.version + 1)
        return self.list_for_assignment(item.assignment_id)

    def delete(self, subtask_id: int, version: int) -> int:
        assignment_id = self.items.pop(subtask_id).assignment_id
        for position, item in enumerate(self.list_for_assignment(assignment_id)):
            self.items[item.id] = replace(item, position=position)
        return assignment_id


def test_empty_create_edit_complete_reopen_move_delete_and_summary() -> None:
    repository = _Repo()
    service = SubtaskManagementService(repository)
    assert service.list(10).percentage == 0
    first = service.save(SaveSubtask(10, "  קריאה  ", "הערה", 30))
    second = service.save(SaveSubtask(10, "תרגול"))
    edited = service.save(SaveSubtask(10, "קריאת פרק", subtask_id=first.id, expected_version=1))
    service.set_completed(10, edited.id, edited.version, True)
    assert service.list(10).percentage == 50
    reopened = service.set_completed(10, edited.id, edited.version + 1, False)
    service.move(10, second.id, second.version, -1)
    assert [x.id for x in service.list(10).items] == [second.id, first.id]
    service.delete(10, reopened.id, reopened.version, True)
    assert service.list(10).total_count == 1


@pytest.mark.parametrize(
    ("command", "field"),
    [
        (SaveSubtask(1, ""), "title"),
        (SaveSubtask(1, "x" * 201), "title"),
        (SaveSubtask(1, "ok", "x" * 10_001), "notes"),
        (SaveSubtask(1, "ok", estimated_minutes=0), "estimated_minutes"),
    ],
)
def test_validation(command: SaveSubtask, field: str) -> None:
    with pytest.raises(SubtaskValidationError) as caught:
        SubtaskManagementService(_Repo()).save(command)
    assert field in caught.value.errors


def test_assignment_isolation_and_delete_confirmation() -> None:
    service = SubtaskManagementService(_Repo())
    item = service.save(SaveSubtask(1, "Synthetic step"))
    service.save(SaveSubtask(2, "Other synthetic step"))
    with pytest.raises(SubtaskValidationError):
        service.delete(1, item.id, item.version, False)
    assert service.list(1).total_count == service.list(2).total_count == 1
