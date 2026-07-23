# ADR 0008: Build the dashboard from a scoped read model

- Status: Accepted
- Date: 2026-07-23
- Scope: Milestone 6 — Dashboard only

## Context

After the first successful calendar import, users need a calm overview of the
current semester. The dashboard combines courses, assignments, academic events,
and synchronization history, but it must not place SQL or date/status business
rules in the presentation layer. This milestone explicitly excludes assignment
management actions.

## Decision

`DashboardRepository` is a read-only application boundary that returns one
dashboard data snapshot. `SQLiteDashboardRepository` resolves the most recent
synchronization scope, then loads active-course count, scoped assignments,
relevant weekly events, and the recent import in a fixed four-query sequence.
It performs no per-row queries and no caching.

`DashboardService` owns calendar-week boundaries, today's agenda filtering,
upcoming-assignment ordering and limiting, completed/remaining/overdue
classification, weekly aggregation, and completion percentage. It accepts an
injectable clock so time-dependent behavior is deterministic in tests.

`DashboardViewModel` translates the application result into Hebrew UI labels,
formatted dates, semantic tones, and immutable display state. `DashboardView`
renders that state and has no infrastructure dependency. The Web composition
root injects the SQLite repository into the service and displays the dashboard
after the accepted first-run transition.

## Consequences

Dashboard rendering uses real local data and remains reusable by another Web or
Desktop presentation. Queries are scoped to the source, institution, and
semester of the most recent completed synchronization. Empty databases produce
encouraging empty states.

The “View all” affordance is a non-interactive placeholder. Assignment editing,
status transitions, search, filtering, details, and manual creation remain
outside this milestone.
