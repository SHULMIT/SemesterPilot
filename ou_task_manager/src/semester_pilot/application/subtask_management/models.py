from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Subtask:
    id: int
    assignment_id: int
    title: str
    notes: str
    completed: bool
    estimated_minutes: int | None
    position: int
    created_at: datetime
    updated_at: datetime
    version: int


@dataclass(frozen=True, slots=True)
class SubtaskSummary:
    items: tuple[Subtask, ...]
    completed_count: int
    total_count: int
    percentage: int


@dataclass(frozen=True, slots=True)
class SaveSubtask:
    assignment_id: int
    title: str
    notes: str = ""
    estimated_minutes: int | None = None
    subtask_id: int | None = None
    expected_version: int | None = None


class SubtaskValidationError(ValueError):
    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("Subtask validation failed")
        self.errors = errors


class SubtaskNotFoundError(LookupError):
    pass


class StaleSubtaskError(RuntimeError):
    pass
