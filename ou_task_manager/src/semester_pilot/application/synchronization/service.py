from __future__ import annotations

from semester_pilot.application.calendar.matching import EventMatcher
from semester_pilot.application.calendar.models import ImportedEvent, ImportPreview, MatchStrategy
from semester_pilot.application.synchronization.models import (
    AmbiguousMatch,
    MatchConfidence,
    PersistedAcademicEvent,
    SyncItem,
    SyncScope,
    SynchronizationHistory,
    SynchronizationResult,
)
from semester_pilot.application.synchronization.ports import (
    CalendarSyncUnitOfWork,
    CalendarSyncUnitOfWorkFactory,
)
from semester_pilot.domain.entities import Assignment


_MATCH_PRIORITY = {
    MatchStrategy.UID: 3,
    MatchStrategy.CONTENT_HASH: 2,
    MatchStrategy.STABLE_KEY: 1,
}


class CalendarSyncService:
    """Reconciles one complete calendar snapshot inside a shared transaction."""

    def __init__(
        self,
        unit_of_work_factory: CalendarSyncUnitOfWorkFactory,
        matcher: EventMatcher | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._matcher = matcher or EventMatcher()

    def synchronize(self, preview: ImportPreview, scope: SyncScope) -> SynchronizationResult:
        if preview.source_id != scope.source_id:
            raise ValueError("Import source_id must match the synchronization scope")
        if not preview.safety.can_synchronize:
            return SynchronizationResult(
                skipped_unsafe_event_indexes=tuple(imported.event.source_index for imported in preview.events),
                skipped_reasons=preview.safety.blocking_reasons,
            )

        added: list[SyncItem] = []
        updated: list[SyncItem] = []
        unchanged: list[SyncItem] = []
        missing: list[SyncItem] = []
        ambiguous: list[AmbiguousMatch] = []

        with self._unit_of_work_factory() as unit_of_work:
            persisted = unit_of_work.events.list_for_scope(scope)
            matched_ids: set[int] = set()
            protected_ids: set[int] = set()

            for imported in preview.events:
                candidates = self._best_candidates(imported, persisted)
                if candidates:
                    strategy = candidates[0][1]
                    candidate_ids = tuple(candidate.id for candidate, _ in candidates if candidate.id is not None)
                    is_weak = strategy is MatchStrategy.STABLE_KEY
                    is_reused = any(candidate_id in matched_ids for candidate_id in candidate_ids)
                    if is_weak or len(candidates) > 1 or is_reused:
                        protected_ids.update(candidate_ids)
                        ambiguous.append(
                            AmbiguousMatch(
                                event_index=imported.event.source_index,
                                match_type=strategy.value,
                                confidence=self._confidence(strategy),
                                reason=self._ambiguity_reason(is_weak, len(candidates), is_reused),
                                candidate_identifiers=candidate_ids,
                            )
                        )
                        continue
                    existing = candidates[0][0]
                    assert existing.id is not None
                    matched_ids.add(existing.id)
                    proposed = self._build_event(imported, scope, unit_of_work, existing)
                    if self._needs_update(existing, proposed):
                        saved = unit_of_work.events.update_source_fields(existing.id, proposed)
                        updated.append(SyncItem(imported.event.source_index, self._require_id(saved)))
                    else:
                        unchanged.append(SyncItem(imported.event.source_index, existing.id))
                    continue

                proposed = self._build_event(imported, scope, unit_of_work)
                saved = unit_of_work.events.create(proposed)
                saved_id = self._require_id(saved)
                matched_ids.add(saved_id)
                added.append(SyncItem(imported.event.source_index, saved_id))

            for existing in persisted:
                existing_id = self._require_id(existing)
                if existing_id in matched_ids or existing_id in protected_ids:
                    continue
                if not existing.is_missing:
                    unit_of_work.events.mark_missing(existing_id)
                missing.append(SyncItem(None, existing_id))

            history = unit_of_work.history.create(
                SynchronizationHistory(
                    id=None,
                    scope=scope,
                    added_count=len(added),
                    updated_count=len(updated),
                    unchanged_count=len(unchanged),
                    missing_count=len(missing),
                    ambiguous_count=len(ambiguous),
                )
            )

        return SynchronizationResult(
            added=tuple(added),
            updated=tuple(updated),
            unchanged=tuple(unchanged),
            missing=tuple(missing),
            ambiguous=tuple(ambiguous),
            history_id=history.id,
        )

    def preview(self, preview: ImportPreview, scope: SyncScope) -> SynchronizationResult:
        """Classify a snapshot against persistence without changing any data."""
        if preview.source_id != scope.source_id:
            raise ValueError("Import source_id must match the synchronization scope")
        if not preview.safety.can_synchronize:
            return SynchronizationResult(
                skipped_unsafe_event_indexes=tuple(imported.event.source_index for imported in preview.events),
                skipped_reasons=preview.safety.blocking_reasons,
            )

        added: list[SyncItem] = []
        updated: list[SyncItem] = []
        unchanged: list[SyncItem] = []
        missing: list[SyncItem] = []
        ambiguous: list[AmbiguousMatch] = []
        with self._unit_of_work_factory() as unit_of_work:
            persisted = unit_of_work.events.list_for_scope(scope)
            matched_ids: set[int] = set()
            protected_ids: set[int] = set()
            for imported in preview.events:
                candidates = self._best_candidates(imported, persisted)
                if not candidates:
                    added.append(SyncItem(imported.event.source_index, None))
                    continue
                strategy = candidates[0][1]
                candidate_ids = tuple(candidate.id for candidate, _ in candidates if candidate.id is not None)
                is_weak = strategy is MatchStrategy.STABLE_KEY
                is_reused = any(candidate_id in matched_ids for candidate_id in candidate_ids)
                if is_weak or len(candidates) > 1 or is_reused:
                    protected_ids.update(candidate_ids)
                    ambiguous.append(
                        AmbiguousMatch(
                            event_index=imported.event.source_index,
                            match_type=strategy.value,
                            confidence=self._confidence(strategy),
                            reason=self._ambiguity_reason(is_weak, len(candidates), is_reused),
                            candidate_identifiers=candidate_ids,
                        )
                    )
                    continue
                existing = candidates[0][0]
                existing_id = self._require_id(existing)
                matched_ids.add(existing_id)
                item = SyncItem(imported.event.source_index, existing_id)
                if self._source_fields_changed(existing, imported):
                    updated.append(item)
                else:
                    unchanged.append(item)

            for existing in persisted:
                existing_id = self._require_id(existing)
                if existing_id not in matched_ids and existing_id not in protected_ids:
                    missing.append(SyncItem(None, existing_id))

        return SynchronizationResult(
            added=tuple(added),
            updated=tuple(updated),
            unchanged=tuple(unchanged),
            missing=tuple(missing),
            ambiguous=tuple(ambiguous),
        )

    def _best_candidates(
        self,
        imported: ImportedEvent,
        persisted: list[PersistedAcademicEvent],
    ) -> list[tuple[PersistedAcademicEvent, MatchStrategy]]:
        matches = [
            (candidate, strategy)
            for candidate in persisted
            if (strategy := self._matcher.match(imported.identity, candidate.identity)) is not None
        ]
        if not matches:
            return []
        best_priority = max(_MATCH_PRIORITY[strategy] for _, strategy in matches)
        return [pair for pair in matches if _MATCH_PRIORITY[pair[1]] == best_priority]

    @staticmethod
    def _ambiguity_reason(is_weak: bool, candidate_count: int, is_reused: bool) -> str:
        if is_weak:
            return "Stable-key fallback is too weak for an automatic merge"
        if is_reused:
            return "More than one incoming event matched the same persisted event"
        return f"{candidate_count} persisted events have the same strongest identity"

    @staticmethod
    def _confidence(strategy: MatchStrategy) -> MatchConfidence:
        if strategy is MatchStrategy.UID:
            return MatchConfidence.HIGH
        if strategy is MatchStrategy.CONTENT_HASH:
            return MatchConfidence.EXACT
        return MatchConfidence.LOW

    @staticmethod
    def _build_event(
        imported: ImportedEvent,
        scope: SyncScope,
        unit_of_work: CalendarSyncUnitOfWork,
        existing: PersistedAcademicEvent | None = None,
    ) -> PersistedAcademicEvent:
        courses = unit_of_work.courses
        assignments = unit_of_work.assignments
        course_id: int | None = None
        assignment_id: int | None = None
        if imported.course:
            course = courses.get_or_create_imported(imported.course, scope)
            if course.id is None:
                raise RuntimeError("Persisted course did not receive an id")
            course_id = course.id
        if imported.assignment and course_id is not None:
            assignment: Assignment = assignments.get_or_create_imported(imported.assignment, course_id)
            if assignment.id is None:
                raise RuntimeError("Persisted assignment did not receive an id")
            assignment_id = assignment.id
            if (
                assignment.title != imported.assignment.title
                or assignment.due_at != imported.assignment.due_at
                or assignment.source_fingerprint != imported.identity.content_hash
            ):
                assignments.update_imported_fields(
                    assignment.id,
                    title=imported.assignment.title,
                    due_at=imported.assignment.due_at,
                    source_fingerprint=imported.identity.content_hash,
                )

        event = imported.event
        return PersistedAcademicEvent(
            id=existing.id if existing else None,
            scope=scope,
            external_uid=imported.identity.uid,
            recurrence_id=imported.identity.recurrence_id,
            stable_match_key=imported.identity.stable_key,
            content_hash=imported.identity.content_hash,
            event_type=imported.event_type,
            course_id=course_id,
            assignment_id=assignment_id,
            title=event.title,
            description=event.description,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            is_all_day=event.is_all_day,
            location=event.location,
            sequence=event.sequence,
            source_last_modified_at=event.last_modified_at,
            is_missing=False,
            source_archived_at=None,
            created_at=existing.created_at if existing else None,
            updated_at=existing.updated_at if existing else None,
        )

    @staticmethod
    def _needs_update(existing: PersistedAcademicEvent, proposed: PersistedAcademicEvent) -> bool:
        return (
            existing.content_hash != proposed.content_hash
            or existing.external_uid != proposed.external_uid
            or existing.recurrence_id != proposed.recurrence_id
            or existing.stable_match_key != proposed.stable_match_key
            or existing.event_type != proposed.event_type
            or existing.course_id != proposed.course_id
            or existing.assignment_id != proposed.assignment_id
            or existing.is_missing
        )

    @staticmethod
    def _source_fields_changed(existing: PersistedAcademicEvent, imported: ImportedEvent) -> bool:
        return (
            existing.content_hash != imported.identity.content_hash
            or existing.external_uid != imported.identity.uid
            or existing.recurrence_id != imported.identity.recurrence_id
            or existing.stable_match_key != imported.identity.stable_key
            or existing.event_type != imported.event_type
            or existing.is_missing
        )

    @staticmethod
    def _require_id(event: PersistedAcademicEvent) -> int:
        if event.id is None:
            raise RuntimeError("Persisted academic event did not receive an id")
        return event.id
