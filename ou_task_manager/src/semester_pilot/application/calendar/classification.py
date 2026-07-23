import re
from collections.abc import Sequence

from semester_pilot.application.calendar.models import ClassificationRule, NormalizedCalendarEvent
from semester_pilot.domain.enums import EventType


class EventClassifier:
    """Classifies normalized events using an injected, ordered rule profile."""

    def __init__(self, rules: Sequence[ClassificationRule]) -> None:
        self._rules = tuple(rules)

    def classify(self, event: NormalizedCalendarEvent) -> EventType:
        for rule in self._rules:
            searchable = " ".join(str(getattr(event, field)) for field in rule.fields)
            if any(re.search(pattern, searchable, flags=re.IGNORECASE) for pattern in rule.patterns):
                return rule.event_type
        return EventType.UNKNOWN
