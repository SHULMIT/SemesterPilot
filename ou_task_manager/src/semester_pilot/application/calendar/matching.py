from semester_pilot.application.calendar.models import EventIdentity, MatchStrategy


class EventMatcher:
    """Applies the canonical source-scoped event matching policy."""

    def match(self, left: EventIdentity, right: EventIdentity) -> MatchStrategy | None:
        if left.source_id != right.source_id:
            return None
        if left.uid and right.uid:
            if left.uid == right.uid and left.recurrence_id == right.recurrence_id:
                return MatchStrategy.UID
            return None
        if left.content_hash == right.content_hash:
            return MatchStrategy.CONTENT_HASH
        if left.stable_key == right.stable_key:
            return MatchStrategy.STABLE_KEY
        return None
