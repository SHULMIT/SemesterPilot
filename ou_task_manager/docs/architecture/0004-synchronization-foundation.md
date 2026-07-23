# ADR 0004: Establish synchronization identity, safety, and transaction boundaries

- Status: Accepted
- Date: 2026-07-23
- Scope: Foundation required before Milestone 3

## Context

Calendar synchronization will compare one imported snapshot with persisted
courses, events, and assignments. It must not merge unrelated recurrence
instances, mark records missing after a partial parse, or commit only part of an
import. The Milestone 2 preview exposed useful identity signals but did not yet
define their persistence-safe semantics.

## Decision

### Canonical identity

Every event identity is scoped by a non-empty calendar `source_id` and contains:

- `uid`: the opaque ICS UID when present;
- `recurrence_id`: normalized `RECURRENCE-ID` when present;
- `stable_key`: a conservative semantic key used when UID is unavailable;
- `content_hash`: a hash used to determine whether matched content changed.

The canonical key is `(source_id, uid, recurrence_id)` when UID exists. Without
UID it is `(source_id, stable_key)`. Content hash is not a stable identifier.
Events with different non-empty UIDs, recurrence identities, or sources do not
match through a weaker fallback.

### Matching policy

One `EventMatcher` applies the matching order: UID/recurrence identity, content
hash, then stable key. It is used by import-preview duplicate detection and will
be reused by synchronization, preventing preview and persistence from using
different matching semantics.

### Snapshot safety

Warnings have explicit severity. Skipped events and error-level structural or
normalization problems make a snapshot incomplete. An incomplete snapshot must
not be synchronized. Unresolved duplicate candidates also block synchronization.
Unknown event types remain valid for review and do not make a snapshot unsafe.

### Transaction ownership

`SQLiteDatabase.transaction()` owns one explicit write transaction and one
connection. SQLite repositories can bind to that connection. A future
`CalendarSyncService` must perform all course, event, assignment, missing-flag,
and import-history writes through repositories sharing that transaction.

## Consequences

ADR 0005 applies this foundation in Milestone 3 by adding academic-event and
history persistence plus the focused synchronization unit of work. The
pairwise matcher remains intentionally small; strategy registries, generic
units of work, and alternate database abstractions stay deferred until a real
second implementation requires them.
