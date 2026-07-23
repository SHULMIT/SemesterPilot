from semester_pilot.ui.navigation import primary_navigation
from semester_pilot.ui.view_models.models import (
    AssignmentState,
    CourseIdentityState,
    ImportMetricState,
    ImportPreviewState,
    PrototypePageState,
)


class PrototypeViewModel:
    """Prepares deterministic, UI-ready fake data for the Milestone 4 prototype."""

    _PAGE_COPY = {
        "overview": ("היום שלך", "סקירה", "מרחב רגוע כדי להבין מה חשוב ולהתחיל ללמוד."),
        "states": ("ספריית מצבים", "מצבי ממשק", "דוגמאות למצבים חוזרים ונגישים במוצר."),
        "import": ("בדיקה לפני פעולה", "תצוגה מקדימה לייבוא", "סיכום חזותי בלבד — ללא כתיבה או סנכרון."),
    }

    def build(self, page_key: str = "overview") -> PrototypePageState:
        resolved_key = page_key if page_key in self._PAGE_COPY else "overview"
        eyebrow, title, description = self._PAGE_COPY[resolved_key]
        systems = CourseIdentityState("10645", "תכנון וניתוח מערכות מידע", "turquoise")
        astronomy = CourseIdentityState("20120", "צפונות היקום", "blue")
        assignments = (
            AssignmentState("ממ״ן 03", systems, "יום ה׳, 30 ביולי", "בתהליך", "info", 62),
            AssignmentState("ממ״ן 01", astronomy, "יום א׳, 8 באוגוסט", "עוד לא התחלתי", "neutral", 0),
        )
        preview = ImportPreviewState(
            source_name="לוח אקדמי לדוגמה",
            file_name="semester-2027a.ics",
            summary="נמצאו 24 אירועים. שום שינוי לא יבוצע במסך ההדגמה.",
            metrics=(
                ImportMetricState("new", "חדשים", 6, "success"),
                ImportMetricState("updated", "עודכנו", 3, "info"),
                ImportMetricState("unchanged", "ללא שינוי", 13, "neutral"),
                ImportMetricState("missing", "חסרים", 1, "warning"),
                ImportMetricState("ambiguous", "דורשים בדיקה", 1, "danger"),
                ImportMetricState("unsafe", "לא בטוחים", 0, "neutral"),
            ),
            is_safe=True,
        )
        return PrototypePageState(
            page_key=resolved_key,
            page_title=title,
            page_eyebrow=eyebrow,
            page_description=description,
            navigation=primary_navigation("import" if resolved_key == "import" else "overview"),
            assignments=assignments,
            import_preview=preview,
            notice="זהו אב־טיפוס עם נתונים לדוגמה בלבד.",
        )
