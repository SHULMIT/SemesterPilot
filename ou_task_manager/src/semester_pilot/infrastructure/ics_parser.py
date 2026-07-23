from __future__ import annotations

from collections import defaultdict
from types import MappingProxyType

from semester_pilot.application.calendar.models import (
    CalendarParseResult,
    CalendarProperty,
    ImportWarning,
    SourceEvent,
    WarningSeverity,
)


def _unfold_lines(text: str) -> list[str]:
    normalized = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    unfolded: list[str] = []
    for line in normalized.split("\n"):
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def _split_unquoted(value: str, separator: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quoted = False
    for character in value:
        if character == '"':
            quoted = not quoted
        if character == separator and not quoted:
            parts.append("".join(current))
            current = []
        else:
            current.append(character)
    parts.append("".join(current))
    return parts


def _property_from_line(line: str) -> tuple[str, CalendarProperty] | None:
    pieces = _split_unquoted(line, ":")
    if len(pieces) < 2:
        return None
    left = pieces[0]
    value = ":".join(pieces[1:])
    segments = _split_unquoted(left, ";")
    name = segments[0].upper().strip()
    if not name:
        return None
    parameters: dict[str, str] = {}
    for segment in segments[1:]:
        if "=" not in segment:
            continue
        key, parameter_value = segment.split("=", 1)
        parameters[key.upper().strip()] = parameter_value.strip().strip('"')
    return name, CalendarProperty(value=value, parameters=MappingProxyType(parameters))


class IcsCalendarParser:
    """Tolerant RFC 5545 VEVENT syntax parser with per-event warnings."""

    def parse(self, text: str) -> CalendarParseResult:
        events: list[SourceEvent] = []
        warnings: list[ImportWarning] = []
        current: defaultdict[str, list[CalendarProperty]] | None = None
        event_index = 0

        for line_number, line in enumerate(_unfold_lines(text), start=1):
            marker = line.strip().upper()
            if marker == "BEGIN:VEVENT":
                if current is not None:
                    warnings.append(
                        ImportWarning(
                            "nested-vevent",
                            f"New VEVENT started before the previous one ended at line {line_number}",
                            event_index,
                            WarningSeverity.ERROR,
                        )
                    )
                    events.append(self._source_event(event_index, current))
                event_index += 1
                current = defaultdict(list)
                continue
            if marker == "END:VEVENT":
                if current is None:
                    warnings.append(
                        ImportWarning(
                            "unexpected-event-end",
                            f"Unexpected END:VEVENT at line {line_number}",
                            severity=WarningSeverity.ERROR,
                        )
                    )
                else:
                    events.append(self._source_event(event_index, current))
                    current = None
                continue
            if current is None or not line:
                continue
            parsed = _property_from_line(line)
            if parsed is None:
                warnings.append(
                    ImportWarning(
                        "malformed-property",
                        f"Malformed property at line {line_number}",
                        event_index,
                    )
                )
                continue
            name, prop = parsed
            current[name].append(prop)

        if current is not None:
            warnings.append(
                ImportWarning(
                    "unterminated-vevent",
                    "VEVENT has no END:VEVENT",
                    event_index,
                    WarningSeverity.ERROR,
                )
            )
            events.append(self._source_event(event_index, current))
        if not events:
            warnings.append(
                ImportWarning(
                    "no-events",
                    "Calendar contains no VEVENT components",
                    severity=WarningSeverity.ERROR,
                )
            )
        return CalendarParseResult(tuple(events), tuple(warnings))

    @staticmethod
    def _source_event(index: int, properties: defaultdict[str, list[CalendarProperty]]) -> SourceEvent:
        frozen = {name: tuple(values) for name, values in properties.items()}
        return SourceEvent(index=index, properties=MappingProxyType(frozen))
