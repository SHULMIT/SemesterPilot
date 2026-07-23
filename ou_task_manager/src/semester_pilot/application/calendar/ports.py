from typing import Protocol

from semester_pilot.application.calendar.models import CalendarParseResult


class CalendarParser(Protocol):
    """Parses calendar source syntax without classifying or persisting events."""

    def parse(self, text: str) -> CalendarParseResult: ...
