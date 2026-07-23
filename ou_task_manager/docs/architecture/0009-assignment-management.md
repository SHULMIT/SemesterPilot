# ADR 0009: Assignment management boundary

## Status

Accepted for Milestone 7.

## Decision

Assignment queries and edits pass through `AssignmentManagementService`. The web presentation consumes only UI-ready ViewModel state; the SQLite implementation is injected at the composition root.

Imported identity and calendar-owned fields (course, title, description, deadline, UID, recurrence identity and source metadata) remain read-only in this workflow. The focused repository update writes only student-owned fields: status, priority, notes, estimate, progress and completion time.

Every assignment has an integer version. Personal updates use `WHERE id = ? AND version = ?` and increment the version atomically. Calendar synchronization also increments the version when it changes imported assignment fields, so an open edit form cannot silently overwrite a concurrent synchronization result.

List filtering, normalized search, sorting, overdue evaluation and completion transitions belong to the application service. Missing-source state is derived from the linked academic event and displayed without deleting the assignment.

## Consequences

- A future desktop or web presentation can reuse the same use cases.
- Synchronization keeps user-owned fields intact.
- A stale form must be refreshed and deliberately resubmitted.
- Manual assignment creation, deletion and calendar-field editing remain outside this milestone.
