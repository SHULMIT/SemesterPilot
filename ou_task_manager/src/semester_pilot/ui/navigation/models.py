from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class NavigationItem:
    key: str
    label: str
    href: str
    icon: str
    active: bool = False


def primary_navigation(active_key: str) -> tuple[NavigationItem, ...]:
    items = (
        NavigationItem("overview", "סקירה", "/dashboard", "⌂"),
        NavigationItem("assignments", "מטלות", "/assignments", "✓"),
        NavigationItem("calendar", "לוח שנה", "/?page=calendar", "□"),
        NavigationItem("courses", "קורסים", "/?page=courses", "◫"),
        NavigationItem("planner", "תכנון שבועי", "/?page=planner", "≡"),
        NavigationItem("import", "ייבוא לוח שנה", "/?page=import", "⇩"),
        NavigationItem("settings", "הגדרות", "/?page=settings", "⚙"),
    )
    return tuple(replace(item, active=item.key == active_key) for item in items)
