# ADR 0005: Persist and synchronize source-scoped calendar snapshots

- Status: Accepted
- Date: 2026-07-23
- Scope: Milestone 3

## Context

ADR 0004 established canonical identity, conservative matching, snapshot safety,
and a shared SQLite transaction boundary. Milestone 3 must turn those decisions
into durable synchronization without allowing calendar data to overwrite the
student's progress or allowing a partial snapshot to hide valid records.

## Decision

### Persistence model and scope

Academic events are persisted separately from courses and assignments. Every
event records its source, institution, semester, UID, recurrence identity,
stable key, content hash, normalized source fields, relationships, missing
state, and timestamps. Course uniqueness is scoped by source, institution,
course code, and semester; assignment uniqueness is scoped by course and
assignment number.

Existing rows are migrated into a reserved `legacy` source and empty
institution/semester values. This retains their identifiers and assignment
relationships while preventing new imports from accidentally claiming them.

### Reconciliation policy

`CalendarSyncService` loads only the requested source/institution/semester and
uses the shared `EventMatcher`. UID plus recurrence identity is authoritative.
An exact content fingerprint may match a UID-less event. Stable-key-only
matches and multiple strongest candidates are reported as ambiguous and are
not merged. Ambiguous candidates are also protected from missing detection.

A complete snapshot classifies records as added, updated, unchanged, missing,
or ambiguous. Missing records are flagged and timestamped rather than deleted;
their flag is cleared when they reappear. An unsafe snapshot is rejected before
opening the synchronization unit of work and cannot change missing state or
write history.

### Ownership and atomicity

Calendar synchronization owns event source fields and imported assignment
title, due time, and source fingerprint. It does not update assignment notes,
status, priority, estimates, recorded work, completion/submission state, or
planning fields. Course name is treated as source-owned within its import
scope.

One SQLite-backed unit of work supplies focused course, assignment, academic
event, and history repositories on one connection. All reconciliation writes
and the history record commit together; any failure rolls back the whole run.
The application service depends only on the unit-of-work and repository ports,
not SQLite or SQL.

## Consequences

Repeated identical snapshots create a history entry but do not duplicate data
or change event/assignment update timestamps. Source and semester scopes remain
isolated, recurrence instances remain distinct, and unknown event types can be
stored for later review.

The current history is a compact run summary rather than a per-field audit log.
Missing records are not yet exposed through a UI, and automatic resolution of
weak identities is intentionally deferred. Those are later-milestone concerns.
