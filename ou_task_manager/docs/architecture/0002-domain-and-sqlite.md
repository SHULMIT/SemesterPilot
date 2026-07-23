# ADR 0002: Evolve the legacy schema through compatible migrations

- Status: Accepted; amended by ADR 0004
- Date: 2026-07-23
- Milestone: 1 — Domain Model and SQLite

## Context

The legacy application stores courses, assignments, and settings in tables used
directly by `app.py`. Milestone 1 needs domain-oriented persistence without
breaking that application or destructively replacing an existing user database.

## Decision

Introduce `Course` and `Assignment` as the only current domain entities, with
`AssignmentStatus` and `PriorityLevel` enums. Define only `CourseRepository` and
`AssignmentRepository` protocols, because persistence is external and tests need
replaceable contracts. Concrete implementations live in infrastructure.

SQLite uses ordered migrations recorded in `schema_migrations` and mirrored in
`PRAGMA user_version`. Each migration runs in an explicit transaction. The first
migration establishes the legacy tables when absent; the second adds domain
columns and indexes in place. Existing rows and legacy column names remain.

The compatibility entry point delegates connection configuration and schema
initialization to the new infrastructure. Legacy-created assignments populate
the required domain columns, while the HTTP behavior and database location stay
unchanged.

ADR 0004 adds an explicit shared SQLite transaction boundary. Repositories may
use short-lived connections for individual operations or bind to a caller-owned
connection so synchronization can commit or roll back all related writes
atomically.

## Consequences

The schema temporarily contains legacy compatibility columns such as `due_date`
and `completed` alongside `due_at` and `status`. This duplication is deliberate
until a later accepted milestone retires the legacy application. There are no
calendar parsing, synchronization, planning, notification, email, or UI changes
in this decision.
