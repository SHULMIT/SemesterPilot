from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from semester_pilot.application.calendar.models import ImportPreview
from semester_pilot.application.synchronization.models import SyncScope, SynchronizationResult


class WorkflowErrorCode(StrEnum):
    INVALID_FILE = "invalid_file"
    UNREADABLE_FILE = "unreadable_file"
    UNSUPPORTED_FORMAT = "unsupported_format"
    EMPTY_CALENDAR = "empty_calendar"
    PARSER_ERROR = "parser_error"
    UNSAFE_SNAPSHOT = "unsafe_snapshot"
    NO_PREVIEW = "no_preview"


class CalendarWorkflowError(Exception):
    def __init__(self, code: WorkflowErrorCode, user_message: str) -> None:
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message


@dataclass(frozen=True, slots=True)
class ImportChangeSummary:
    added: int
    updated: int
    unchanged: int
    missing: int
    ambiguous: int
    skipped_reasons: tuple[str, ...] = ()

    @property
    def is_safe(self) -> bool:
        return not self.skipped_reasons

    @classmethod
    def from_result(cls, result: SynchronizationResult) -> ImportChangeSummary:
        return cls(
            added=len(result.added),
            updated=len(result.updated),
            unchanged=len(result.unchanged),
            missing=len(result.missing),
            ambiguous=len(result.ambiguous),
            skipped_reasons=result.skipped_reasons,
        )


@dataclass(frozen=True, slots=True)
class PreparedCalendarImport:
    filename: str
    preview: ImportPreview
    scope: SyncScope
    synchronization_preview: SynchronizationResult

    @property
    def summary(self) -> ImportChangeSummary:
        return ImportChangeSummary.from_result(self.synchronization_preview)


@dataclass(frozen=True, slots=True)
class CalendarImportCompletion:
    result: SynchronizationResult
    elapsed_seconds: float

    @property
    def total_processed(self) -> int:
        return len(self.result.added) + len(self.result.updated) + len(self.result.unchanged)

    @property
    def summary(self) -> ImportChangeSummary:
        return ImportChangeSummary.from_result(self.result)
