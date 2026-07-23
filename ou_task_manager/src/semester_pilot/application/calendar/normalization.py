from __future__ import annotations

import re
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from semester_pilot.application.calendar.models import (
    CalendarParseResult,
    CalendarProperty,
    ImportWarning,
    NormalizationResult,
    NormalizedCalendarEvent,
    SourceEvent,
    WarningSeverity,
)


def normalize_text(value: str) -> str:
    """Unescape RFC 5545 text and normalize whitespace and quote variants."""
    value = value.replace("\\n", "\n").replace("\\N", "\n")
    value = value.replace(r"\,", ",").replace(r"\;", ";").replace("\\\\", "\\")
    value = value.replace("“", '"').replace("”", '"').replace("׳", "'").replace("״", '"')
    return " ".join(value.split())


class CalendarNormalizer:
    """Normalizes source properties into consistent text and timezone-aware dates."""

    def __init__(self, default_timezone: str = "Asia/Jerusalem") -> None:
        self._default_timezone = ZoneInfo(default_timezone)

    def normalize(self, parsed: CalendarParseResult) -> NormalizationResult:
        events: list[NormalizedCalendarEvent] = []
        warnings = list(parsed.warnings)
        skipped_event_count = 0
        for source in parsed.events:
            event, event_warnings = self._normalize_event(source)
            warnings.extend(event_warnings)
            if event is not None:
                events.append(event)
            else:
                skipped_event_count += 1
        return NormalizationResult(tuple(events), tuple(warnings), skipped_event_count)

    def _normalize_event(self, source: SourceEvent) -> tuple[NormalizedCalendarEvent | None, tuple[ImportWarning, ...]]:
        warnings: list[ImportWarning] = []
        start_property = source.first("DTSTART")
        if start_property is None:
            return None, (
                ImportWarning(
                    "missing-dtstart",
                    "Event has no DTSTART and was skipped",
                    source.index,
                    WarningSeverity.ERROR,
                ),
            )
        try:
            starts_at, is_all_day = self._parse_datetime(start_property)
        except ValueError as exc:
            return None, (ImportWarning("invalid-dtstart", str(exc), source.index, WarningSeverity.ERROR),)

        ends_at: datetime | None = None
        end_property = source.first("DTEND")
        if end_property is not None:
            try:
                ends_at, _ = self._parse_datetime(end_property)
            except ValueError as exc:
                warnings.append(ImportWarning("invalid-dtend", str(exc), source.index))

        uid_property = source.first("UID")
        uid = normalize_text(uid_property.value).strip() if uid_property else None
        uid = uid or None
        recurrence_id: datetime | None = None
        recurrence_property = source.first("RECURRENCE-ID")
        if recurrence_property is not None:
            try:
                recurrence_id, _ = self._parse_datetime(recurrence_property)
            except ValueError as exc:
                warnings.append(ImportWarning("invalid-recurrence-id", str(exc), source.index, WarningSeverity.ERROR))
        sequence: int | None = None
        sequence_property = source.first("SEQUENCE")
        if sequence_property is not None:
            try:
                sequence = int(sequence_property.value.strip())
            except ValueError:
                warnings.append(ImportWarning("invalid-sequence", "SEQUENCE must be an integer", source.index))
        last_modified_at: datetime | None = None
        last_modified_property = source.first("LAST-MODIFIED") or source.first("DTSTAMP")
        if last_modified_property is not None:
            try:
                last_modified_at, _ = self._parse_datetime(last_modified_property)
            except ValueError as exc:
                warnings.append(ImportWarning("invalid-last-modified", str(exc), source.index))
        return (
            NormalizedCalendarEvent(
                source_index=source.index,
                uid=uid,
                recurrence_id=recurrence_id,
                title=self._text(source, "SUMMARY"),
                description=self._text(source, "DESCRIPTION"),
                location=self._text(source, "LOCATION"),
                starts_at=starts_at,
                ends_at=ends_at,
                is_all_day=is_all_day,
                sequence=sequence,
                last_modified_at=last_modified_at,
            ),
            tuple(warnings),
        )

    def _parse_datetime(self, prop: CalendarProperty) -> tuple[datetime, bool]:
        value = prop.value.strip()
        is_all_day = prop.parameters.get("VALUE", "").upper() == "DATE" or bool(re.fullmatch(r"\d{8}", value))
        if is_all_day:
            parsed_date = datetime.strptime(value, "%Y%m%d").date()
            return datetime.combine(parsed_date, time.min, self._default_timezone), True

        is_utc = value.endswith("Z")
        raw = value[:-1] if is_utc else value
        date_format = "%Y%m%dT%H%M%S" if len(raw) == 15 else "%Y%m%dT%H%M"
        try:
            parsed = datetime.strptime(raw, date_format)
        except ValueError as exc:
            raise ValueError(f"Invalid calendar date-time: {value}") from exc
        if is_utc:
            return parsed.replace(tzinfo=timezone.utc), False

        timezone_name = prop.parameters.get("TZID")
        if timezone_name:
            try:
                localized = parsed.replace(tzinfo=ZoneInfo(timezone_name))
                return localized.astimezone(timezone.utc), False
            except ZoneInfoNotFoundError as exc:
                raise ValueError(f"Unknown calendar timezone: {timezone_name}") from exc
        localized = parsed.replace(tzinfo=self._default_timezone)
        return localized.astimezone(timezone.utc), False

    @staticmethod
    def _text(source: SourceEvent, name: str) -> str:
        prop = source.first(name)
        return normalize_text(prop.value) if prop else ""
