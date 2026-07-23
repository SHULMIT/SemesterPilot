# ADR 0010: Subtask ownership and assignment progress

## Status

Accepted for Milestone 8.

## Decision

Subtasks are local, user-owned records tied to exactly one imported assignment. Calendar synchronization neither reads nor writes the `subtasks` table. Subtask completion is calculated and displayed separately; it never changes the assignment status or its manually managed progress percentage. Even when every subtask is complete, completing the parent assignment remains an explicit user action.

Subtask edits use optimistic concurrency. Reordering swaps adjacent positions in one transaction and keeps positions contiguous. Assignment deletion remains out of scope; the foreign key uses `ON DELETE RESTRICT` so a future deletion workflow must make an explicit ownership decision.
