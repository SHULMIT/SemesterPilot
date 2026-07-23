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
│   ├── application/     # use cases and application services
│   ├── repositories/    # persistence abstractions
│   ├── infrastructure/  # SQLite, ICS, email, files, notifications
│   └── ui/
│       ├── theme/
│       ├── components/
│       ├── screens/
│       ├── view_models/
│       ├── navigation/
│       └── shared/
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

The five required layers are Domain, Application / Services, Repository
abstractions, Infrastructure, and UI. Repository contracts belong at the inward
application boundary; concrete persistence belongs in infrastructure.

## UI boundary

Screens use ViewModels or Presenters. For non-trivial screens, prefer
`screen_view.py`, `screen_view_model.py`, and `screen_state.py`.

- A View renders prepared state and forwards user interactions.
- A ViewModel prepares display state and invokes application use cases.
- An application service coordinates business workflows and rules.
- A repository abstracts persistence.
- An infrastructure implementation integrates SQLite, ICS and file access,
  email, credentials, notifications, and scheduling.

UI code must not execute SQL, directly access SQLite, parse ICS files, calculate
priorities, generate weekly plans, send email, schedule reminders, or contain
domain business rules. Business rules must run in tests without launching UI;
ViewModels must be testable with fake services.

## Design principles

Classes have one clear responsibility and remain small and focused. Prefer
composition over deep inheritance and dependency injection for external
dependencies. Global mutable state, god classes, and a `MainWindow` that manages
the entire application are prohibited.

An interface is justified only when multiple implementations exist, a second is
planned soon, the dependency is external, or tests require replacement. Useful
examples are `AssignmentRepository`, `CalendarParser`, `NotificationSender`,
`EmailSender`, and `CredentialStore`; interfaces are not required for every class.
Speculative abstractions are avoided.

## UI design gate

Before real services or SQLite are connected to the product UI, Milestone 4 must
produce an isolated fake/in-memory prototype, centralized design tokens, reusable
components, light and dark themes, Hebrew-first RTL behavior, navigation and a
screen map. The repository owner must approve that foundation before the full UI
milestones begin.

## Consequences

This leaves known duplication and coupling in place temporarily. In return, the
existing program remains runnable, tests provide a migration safety net, and
future architecture changes can be reviewed in small milestones.
