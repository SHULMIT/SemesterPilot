from __future__ import annotations

from datetime import date
from typing import Protocol

from semester_pilot.application.dashboard.models import DashboardData


class DashboardRepository(Protocol):
    def load(self, range_start: date, range_end: date) -> DashboardData: ...
