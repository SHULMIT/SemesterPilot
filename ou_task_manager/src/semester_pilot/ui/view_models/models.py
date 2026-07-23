from dataclasses import dataclass

from semester_pilot.ui.navigation import NavigationItem


@dataclass(frozen=True, slots=True)
class CourseIdentityState:
    code: str
    name: str
    color: str


@dataclass(frozen=True, slots=True)
class AssignmentState:
    title: str
    course: CourseIdentityState
    due_label: str
    status_label: str
    status_tone: str
    progress: int


@dataclass(frozen=True, slots=True)
class ImportMetricState:
    key: str
    label: str
    value: int
    tone: str


@dataclass(frozen=True, slots=True)
class ImportPreviewState:
    source_name: str
    file_name: str
    summary: str
    metrics: tuple[ImportMetricState, ...]
    is_safe: bool


@dataclass(frozen=True, slots=True)
class PrototypePageState:
    page_key: str
    page_title: str
    page_eyebrow: str
    page_description: str
    navigation: tuple[NavigationItem, ...]
    assignments: tuple[AssignmentState, ...]
    import_preview: ImportPreviewState
    notice: str | None = None
