# ADR 0003: Use a configurable calendar import pipeline

- Status: Accepted; amended by ADR 0004
- Date: 2026-07-23
- Milestone: 2 — Robust ICS Parsing

## Context

Calendar import and synchronization are the product's central capability. The
legacy implementation combines syntax parsing, Hebrew phrase matching,
extraction, and output conversion in one function. Extending that approach to
more institutions, languages, time zones, and reimport behavior would create a
fragile parser and make failures difficult to isolate.

## Decision

Use a pipeline of small, injected components:

```text
CalendarParser (port) -> IcsCalendarParser
        |
CalendarNormalizer
        |
EventClassifier <- configurable rule profile
        |
CourseExtractor + AssignmentExtractor <- configurable patterns
        |
FingerprintGenerator
        |
CalendarImportService -> in-memory ImportPreview
        |
CalendarSyncService (Milestone 3, not implemented here)
```

`IcsCalendarParser` understands VEVENT structure, unfolding, property parameters,
and syntax warnings only. The normalizer owns text, identifier, all-day, UTC,
TZID, and floating-time normalization. Classification rules and extraction
patterns are centralized profiles; the first profile is Hebrew Open University.

Identity exposes three source-scoped signals in priority order:

1. trimmed ICS UID plus `RECURRENCE-ID` when present;
2. a SHA-256 content hash of normalized event type, course, assignment number,
   title, start, and recurrence identity;
3. a stable match key using event type plus course, semester, and assignment
   identity, or event type plus course, normalized title, and start for other
   events.

The import service creates an in-memory preview and detects duplicates within the
source batch. It performs no persistence or existing-record comparison.
Recoverable event failures are represented as structured warnings; other events
continue through the pipeline.

ADR 0004 defines the shared matching policy and snapshot safety gate required
before these signals can be used for persistence.

## Milestone boundary

Changed-deadline, renamed-assignment, and missing-event fixtures verify that the
parser emits stable UID/fallback inputs and accurate current-event sets. Deciding
whether persisted records are added, updated, unchanged, or missing belongs
exclusively to `CalendarSyncService` in Milestone 3, along with transactions,
import history, and preservation of user-owned fields.

## Consequences

Adding another institution requires a rule/extraction profile and composition
configuration rather than edits throughout the parser. The RFC 5545 parser is a
tolerant standard-library subset rather than a full recurrence engine; unsupported
or malformed values remain visible through warnings and can be expanded without
changing the application pipeline.
