# Repository instructions

SemesterPilot is a local-first, Hebrew-first academic assignment manager. Read
`PLAN.md` and this file before making changes.

## Working agreement

- Implement exactly one requested milestone at a time. Do not anticipate later milestones.
- Preserve the behavior of the legacy `app.py` until an accepted milestone explicitly replaces it.
- Never commit user databases, calendars, credentials, tokens, or `.env` files.
- Keep core behavior usable without email or any network connection.
- Add tests for behavioral changes and important bug fixes.
- Run `python -m ruff format --check .`, `python -m ruff check .`,
  `python -m mypy`, and `python -m pytest` before completion.
- Use temporary databases and synthetic calendar data in tests.
- Do not silently delete or migrate a user's database.
- Do not implement the full product UI until Milestone 4's isolated design-system
  prototype has received explicit owner approval.

## Current architecture

`app.py` is the preserved legacy application and currently contains HTTP,
rendering, application logic, SQLite access, calendar parsing, and email code.
`send_weekly.py` is its scheduled-email entry point. The files under `templates/`
and `static/` are not used by the current standard-library HTTP server.

The intended package structure is recorded in `docs/architecture/0001-foundation.md`.
Introduce it incrementally from Milestone 1 onward, with domain code independent
of UI and infrastructure.

## Required layers and dependency direction

The architecture has five explicit layers:

1. **Domain** — entities, value objects, enums, and business rules.
2. **Application / Services** — use cases and business workflows.
3. **Repository abstractions** — persistence contracts used by application services.
4. **Infrastructure** — SQLite, ICS and file access, email, notifications,
   scheduling, credentials, and repository implementations.
5. **UI** — rendering, interaction forwarding, navigation, and presentation state.

Dependencies point inward. Repository abstractions live with the domain or
application boundary; their SQLite implementations live in infrastructure.

The UI must never execute SQL, access SQLite directly, parse ICS files, calculate
priorities, generate weekly plans, send email, schedule reminders, or contain
domain business rules. Screens use ViewModels or Presenters.

Use this UI structure:

```text
ui/
├── theme/
├── components/
├── screens/
├── view_models/
├── navigation/
└── shared/
```

For a non-trivial screen, prefer `screen_view.py`, `screen_view_model.py`, and
`screen_state.py`. A View renders state and forwards interactions. A ViewModel
prepares display state and invokes application use cases. An application service
coordinates workflows and rules. A repository abstracts persistence. An
infrastructure implementation integrates external systems.

## Design and SOLID rules

- Give each class one clear responsibility; keep classes small and focused.
- Prefer composition over deep inheritance.
- Inject external dependencies.
- Keep business logic testable without launching the UI.
- Test ViewModels with fake services.
- Do not use global mutable state, god classes, or a `MainWindow` that manages the
  entire application.
- Do not add speculative abstractions without a real reason.

Create an interface only when multiple implementations exist, a second
implementation is planned soon, the dependency is external, or tests need a
replaceable implementation. Appropriate examples include `AssignmentRepository`,
`CalendarParser`, `NotificationSender`, `EmailSender`, and `CredentialStore`.
Do not create an interface for every class.

## Calendar import boundary

Calendar import is a pipeline of focused responsibilities: source parsing,
normalization, classification, course extraction, assignment extraction,
fingerprinting, import preview, and—only in its own milestone—synchronization.
Do not collapse these responsibilities into a large parser or scatter
institution-specific string matching across services.

Classification and extraction rules must be injected profiles. The initial
profile supports Hebrew Open University calendars; additional institutions and
languages must be addable without changing orchestration code. Canonical identity
is scoped by calendar source. Prefer UID plus `RECURRENCE-ID`; otherwise use the
stable match key. Use content hash to detect changes, not as the long-lived
identity. Never identify an event only by its title, and route all matching
through the shared event-matching policy.

Malformed events should produce structured warnings and allow other events to
continue whenever possible. Parsing and import-preview code must not execute SQL.
Incomplete snapshots and unresolved duplicates must not be synchronized. A
calendar synchronization operation must use repositories bound to one shared
SQLite transaction.
`CalendarSyncService` owns persisted add/update/unchanged/missing decisions and
must not be introduced before its milestone.

## Visual direction

SemesterPilot should be modern, calm, motivating, student-friendly, comfortable
for long study sessions, professional without feeling corporate, and visually
impressive without overload. Open University academic blue, turquoise, white,
calm neutral surfaces, academic familiarity, and Hebrew-first terminology may
inspire an independent identity. Never copy university branding, logos, layouts,
web pages, or copyrighted assets.

Avoid generic Bootstrap styling, dense enterprise tables, excessive gradients or
animations, tiny text, too many colors, childish visuals, and styling hard-coded
inside screens. Use centralized design tokens and reusable components.
