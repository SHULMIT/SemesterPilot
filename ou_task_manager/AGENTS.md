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

## Current architecture

`app.py` is the preserved legacy application and currently contains HTTP,
rendering, application logic, SQLite access, calendar parsing, and email code.
`send_weekly.py` is its scheduled-email entry point. The files under `templates/`
and `static/` are not used by the current standard-library HTTP server.

The intended package structure is recorded in `docs/architecture/0001-foundation.md`.
Introduce it incrementally from Milestone 1 onward, with domain code independent
of UI and infrastructure.

