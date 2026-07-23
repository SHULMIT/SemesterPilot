# SemesterPilot UI foundation

## Current screen map

```text
First-run workflow
├── Welcome and local ICS selection
├── Loading and validation
├── Real synchronization preview
├── Explicit confirmation
├── Synchronization progress
├── Success summary
└── Real-data dashboard
    ├── Welcome and active semester
    ├── Today's agenda
    ├── Upcoming assignments
    ├── Weekly overview
    ├── Progress summary
    └── Recent import

Design-system library retained from Milestone 4
├── Application shell and navigation
├── Assignment and course components
├── Empty/loading/success/error states
└── Accessible dialog and form components
```

The dashboard is read-only. Assignment management, filters, status changes,
manual creation, and assignment details remain outside the current milestone.

## Presentation flow

```text
prototype.py (composition root)
    → CalendarImportWorkflowService
    → FirstRunViewModel
    → immutable FirstRunState
    → FirstRunView
    → reusable semantic HTML components
    → centralized CSS tokens and interaction script
```

The View and components depend only on presentation state. The ViewModel invokes
an injected application workflow and does not import infrastructure. The workflow
owns validation, calendar parsing, scope resolution, read-only preview, and
confirmed synchronization orchestration. Only the composition root knows the
SQLite and parser implementations.

## Design system inventory

- Foundation tokens: warm surfaces, turquoise and violet accents, semantic
  states, typography, spacing, sizing, radii, shadows, breakpoints, transitions,
  and focus rings.
- Inputs and actions: primary/secondary/ghost/disabled buttons, labeled fields,
  file selection, keyboard focus, and disabled/busy states.
- Content: cards, badges, status chips, course identity, assignment progress,
  page headers, alerts, empty states, loading states, and import metrics.
- Accessibility: Hebrew RTL, semantic landmarks, live status and error regions,
  native controls, skip links, visible focus, and reduced-motion behavior.

The current theme is light only. Semantic custom properties allow a future
theme scope to replace values without changing component selectors.

## Running the application

```powershell
python prototype.py
```

Open `http://127.0.0.1:5050`. Calendar parsing and preview use real application
services. No persistence change occurs until the user explicitly confirms the
synchronization.
