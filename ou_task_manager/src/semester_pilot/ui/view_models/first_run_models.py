from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FirstRunStep(StrEnum):
    WELCOME = "welcome"
    LOADING = "loading"
    PREVIEW = "preview"
    SYNCHRONIZING = "synchronizing"
    SUCCESS = "success"
    ERROR = "error"
    DASHBOARD = "dashboard"


@dataclass(frozen=True, slots=True)
class ResultMetricState:
    key: str
    label: str
    value: int
    tone: str


@dataclass(frozen=True, slots=True)
class FirstRunState:
    step: FirstRunStep
    title: str
    description: str
    is_busy: bool = False
    progress: int = 0
    filename: str | None = None
    metrics: tuple[ResultMetricState, ...] = ()
    warnings: tuple[str, ...] = ()
    error_message: str | None = None
    can_confirm: bool = False
    elapsed_label: str | None = None
    total_processed: int = 0
