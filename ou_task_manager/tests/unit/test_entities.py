from datetime import datetime

import pytest

from semester_pilot.domain import Assignment, AssignmentStatus, Course, PriorityLevel


def test_course_normalizes_identity_fields() -> None:
    course = Course(code=" 101 ", name=" Test course ")

    assert course.code == "101"
    assert course.name == "Test course"
    assert course.is_archived is False


@pytest.mark.parametrize("code,name", [("", "Course"), ("101", "  ")])
def test_course_requires_code_and_name(code: str, name: str) -> None:
    with pytest.raises(ValueError):
        Course(code=code, name=name)


def test_assignment_supports_distinct_status_and_priority_values() -> None:
    assignment = Assignment(
        course_id=1,
        number="01",
        title="First assignment",
        due_at=datetime(2027, 1, 10, 23, 59),
        status=AssignmentStatus.SUBMITTED,
        priority=PriorityLevel.HIGH,
    )

    assert assignment.status is AssignmentStatus.SUBMITTED
    assert assignment.status is not AssignmentStatus.WORK_COMPLETED
    assert assignment.priority is PriorityLevel.HIGH


def test_assignment_rejects_invalid_work_values() -> None:
    with pytest.raises(ValueError):
        Assignment(
            course_id=1,
            number="01",
            title="First assignment",
            due_at=datetime(2027, 1, 10),
            estimated_minutes=-1,
        )
