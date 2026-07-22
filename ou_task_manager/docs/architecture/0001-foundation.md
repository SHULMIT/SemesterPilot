# ADR 0001: Preserve the legacy app while establishing a package boundary

- Status: Accepted
- Date: 2026-07-22
- Milestone: 0 — Repository Audit and Foundation

## Context

The current working product is a single-file, standard-library web application.
It combines HTTP handling, HTML rendering, SQLite access, ICS parsing, planning
labels, and SMTP. Rewriting it during the foundation milestone would risk losing
working behavior before equivalent tests and domain boundaries exist.

## Decision

Keep `app.py` and its entry points working during Milestone 0. Establish quality
tooling and characterize its behavior with tests. Beginning with the relevant
later milestone, introduce this target structure incrementally:

```text
semester-pilot/
├── src/semester_pilot/
│   ├── domain/          # entities, values, enums, domain rules
│   ├── application/     # use cases and ports
│   ├── infrastructure/  # SQLite, ICS, notifications, scheduling
│   └── ui/              # PySide6 views and presenters
├── tests/
│   ├── unit/
│   └── integration/
├── docs/architecture/
├── app.py               # legacy compatibility entry point while migrating
└── pyproject.toml
```

Dependencies must point inward: UI and infrastructure may depend on application
ports and domain types; domain code must not depend on SQLite, PySide6, SMTP, or
the operating system. User data will ultimately live in the OS application-data
directory, but moving or migrating the existing database belongs to a later
milestone and must never happen implicitly.

## Consequences

This leaves known duplication and coupling in place temporarily. In return, the
existing program remains runnable, tests provide a migration safety net, and
future architecture changes can be reviewed in small milestones.

