# ADR 0007: Connect first-run presentation through an import workflow use case

- Status: Accepted
- Date: 2026-07-23
- Scope: Milestone 5

## Context

The calendar parser and transactional synchronization engine already exist, and
Milestone 4 established a replaceable presentation boundary. A new user now
needs to select an ICS file, inspect real synchronization decisions, explicitly
confirm them, and reach the application shell without exposing SQLite or
duplicating synchronization policy in the Web UI.

## Decision

`CalendarImportWorkflowService` validates the file and ICS envelope, invokes the
existing import pipeline, rejects an empty calendar, derives one scoped semester,
and asks `CalendarSyncService` for a read-only comparison. Confirmation passes
the prepared import back to the workflow, which invokes the existing atomic
synchronization and records elapsed time. Unsafe previews cannot be confirmed.

`CalendarSyncService.preview()` shares canonical matching, confidence, scope,
ambiguity, and missing-event policy with synchronization. It reads persisted
events but creates no courses, assignments, events, or history records.

`FirstRunViewModel` owns welcome, loading, preview, synchronizing, success,
error, and dashboard-arrival presentation states. It receives the workflow by
injection, keeps the prepared import private, and rejects overlapping actions.
The browser also disables duplicate actions while a request is active.

`FirstRunView` renders UI-ready state only. `prototype.py` is the composition
root for migration infrastructure, parser, synchronizer, workflow, ViewModel,
and View. The browser sends the selected file only to the loopback server, with
a request-size limit; no external service or cloud storage is involved.

## Consequences

The UI displays real add/update/unchanged/missing/ambiguous/safety results
without writing before confirmation. This milestone ends at a minimal
dashboard-arrival screen. Live dashboard and assignment behavior remain
Milestone 6 work.
