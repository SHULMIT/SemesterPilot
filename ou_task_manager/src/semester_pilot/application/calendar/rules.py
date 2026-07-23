from semester_pilot.application.calendar.models import ClassificationRule
from semester_pilot.domain.enums import EventType


OPEN_UNIVERSITY_HEBREW_RULES: tuple[ClassificationRule, ...] = (
    ClassificationRule(
        EventType.ASSIGNMENT_DEADLINE,
        (r"מועד\s+אחרון\s+להגשת\s+ממ[\"״']?ן", r"\bמטלה\s*\d+\b"),
    ),
    ClassificationRule(
        EventType.EXAM_REGISTRATION,
        (r"הרשמה\s+לבחינת\s+גמר", r"הרשמה\s+לבחינה"),
    ),
    ClassificationRule(EventType.EXAM, (r"בחינת\s+גמר", r"\bבחינה\b")),
    ClassificationRule(
        EventType.LESSON,
        (r"מפגש\s+בהנחיה\s+מקוונת", r"\bמפגש\b", r"\bשיעור\b"),
    ),
    ClassificationRule(EventType.SEMESTER_START, (r"התחלת\s+סמסטר", r"פתיחת\s+סמסטר")),
    ClassificationRule(EventType.SEMESTER_END, (r"סיום\s+סמסטר",)),
    ClassificationRule(
        EventType.REGISTRATION_DEADLINE,
        (r"מועד\s+אחרון\s+להרשמה", r"סיום\s+הרשמה"),
    ),
    ClassificationRule(
        EventType.GENERAL_ACADEMIC,
        (r"\bסמסטר\b", r"\bאקדמי", r"\bהרשמה\b"),
    ),
)
