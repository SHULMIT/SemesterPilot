# ADR 0006: Isolate the web presentation prototype behind UI-ready state

- Status: Accepted
- Date: 2026-07-23
- Scope: Milestone 4

## Context

SemesterPilot needs an RTL-first visual foundation before product workflows are
built. The current local web application is intentionally preserved, but its
legacy server mixes persistence and rendering. Building the future interface on
that structure would couple presentation to SQLite and make a future desktop or
alternate web client unnecessarily difficult.

## Decision

### Presentation boundary

The new `semester_pilot.ui` package is framework-independent and contains:

- `navigation`: immutable navigation definitions and active state;
- `view_models`: immutable UI-ready state and an in-memory prototype ViewModel;
- `components`: reusable semantic HTML components;
- `screens`: views that render application shells and screen compositions;
- `theme`: centralized CSS tokens and visual rules (stored as a static asset);
- `shared`: reserved for cross-screen presentation helpers when a real need appears.

Views receive presentation state and do not query application services. The
prototype ViewModel uses deterministic fake data and has no infrastructure
dependency. Future workflow ViewModels may invoke injected application use
cases, but templates and components will continue to receive UI-ready values.

`prototype.py` is an isolated composition root and local static-file server. It
constructs the ViewModel and View, but imports no SQLite, repository, parser, or
synchronization implementation. The accepted legacy `app.py` remains operational
and unchanged by this milestone.

### Visual system

The light theme uses academic navy and turquoise with quiet neutral surfaces.
Colors, semantic states, typography, spacing, sizes, radii, elevation,
breakpoints, transitions, and focus treatment are tokens. Components use these
tokens rather than page-specific styling. Tokens are structured as semantic CSS
custom properties so a future dark theme can override values without changing
component rules.

Hebrew and RTL are document-level defaults. The shell places persistent
navigation on the right, becomes an accessible drawer at tablet sizes, and
collapses multi-column content on small screens.

### Accessibility

The prototype uses semantic landmarks, explicit form labels, native buttons and
dialog, a skip link, visible `:focus-visible` treatment, ARIA status/alert
announcements, progress semantics, modal labels, keyboard-close behavior from
native `dialog`, and reduced-motion overrides. It uses a system font stack and
has no network or third-party asset dependency.

## Consequences

The prototype can be run independently with `python prototype.py` and contains
no real import or synchronization action. Navigation beyond the representative
screens is intentionally placeholder-only. The same application/domain layers
can later support this Web UI, a Desktop UI, or another client through injected
application use cases.

The renderer is deliberately small and dependency-free. A template framework
may replace it once full workflows justify that dependency; the ViewModel state
boundary and design tokens should remain stable.
