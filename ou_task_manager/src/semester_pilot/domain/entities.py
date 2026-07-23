from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from semester_pilot.domain.enums import AssignmentStatus, PriorityLevel


@dataclass(slots=True)
class Course:
    """An academic course tracked by the student."""

    code: str
    name: str
    id: int | None = None
    external_key: str | None = None
    semester: str | None = None
    institution: str | None = None
    color: str | None = None
    archived_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        self.code = self.code.strip()
        self.name = self.name.strip()
        if not self.code:
            raise ValueError("Course code must not be empty")
        if not self.name:
            raise ValueError("Course name must not be empty")

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None


@dataclass(slots=True)
class Assignment:
    """A course assignment and its student-owned progress data."""

    course_id: int
    number: str
    title: str
    due_at: datetime
    id: int | None = None
    description: str = ""
    recommended_start_at: datetime | None = None
    status: AssignmentStatus = AssignmentStatus.NOT_STARTED
    priority: PriorityLevel = PriorityLevel.NORMAL
    estimated_minutes: int | None = None
    actual_minutes: int = 0
    progress_percentage: int = 0
    notes: str = ""
    source_event_id: int | None = None
    source_fingerprint: str | None = None
    completed_at: datetime | None = None
    submitted_at: datetime | None = None
    archived_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    version: int = 1

    def __post_init__(self) -> None:
        self.number = self.number.strip()
        self.title = self.title.strip()
        if self.course_id <= 0:
            raise ValueError("Assignment course_id must be positive")
        if not self.number:
            raise ValueError("Assignment number must not be empty")
        if not self.title:
            raise ValueError("Assignment title must not be empty")
        if self.estimated_minutes is not None and self.estimated_minutes < 0:
            raise ValueError("Estimated minutes must not be negative")
        if self.actual_minutes < 0:
            raise ValueError("Actual minutes must not be negative")
        if not 0 <= self.progress_percentage <= 100:
            raise ValueError("Progress percentage must be between 0 and 100")
        if self.version < 1:
            raise ValueError("Assignment version must be positive")

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None
