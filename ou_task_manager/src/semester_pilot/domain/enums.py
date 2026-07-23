from enum import StrEnum


class AssignmentStatus(StrEnum):
    """The student's progress through an assignment."""

    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    WORK_COMPLETED = "WORK_COMPLETED"
    SUBMITTED = "SUBMITTED"
    OVERDUE = "OVERDUE"
    SKIPPED = "SKIPPED"


class PriorityLevel(StrEnum):
    """A persisted, user-visible priority level."""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class EventType(StrEnum):
    """Semantic types supported by calendar classification."""

    ASSIGNMENT_DEADLINE = "ASSIGNMENT_DEADLINE"
    LESSON = "LESSON"
    EXAM = "EXAM"
    EXAM_REGISTRATION = "EXAM_REGISTRATION"
    SEMESTER_START = "SEMESTER_START"
    SEMESTER_END = "SEMESTER_END"
    REGISTRATION_DEADLINE = "REGISTRATION_DEADLINE"
    GENERAL_ACADEMIC = "GENERAL_ACADEMIC"
    UNKNOWN = "UNKNOWN"
