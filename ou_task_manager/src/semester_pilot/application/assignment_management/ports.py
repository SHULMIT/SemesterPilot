from typing import Protocol

from semester_pilot.application.assignment_management.models import (
    AssignmentRecord,
    PersonalAssignmentUpdate,
)


class ManagedAssignmentRepository(Protocol):
    def list_current(self) -> tuple[AssignmentRecord, ...]: ...

    def get(self, assignment_id: int) -> AssignmentRecord | None: ...

    def update_personal_fields(
        self,
        assignment_id: int,
        expected_version: int,
        update: PersonalAssignmentUpdate,
    ) -> AssignmentRecord: ...
