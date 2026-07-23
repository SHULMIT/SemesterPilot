"""Framework-independent presentation layer for SemesterPilot."""

from semester_pilot.ui.screens.assignment_view import AssignmentView
from semester_pilot.ui.screens.dashboard_view import DashboardView
from semester_pilot.ui.screens.first_run_view import FirstRunView
from semester_pilot.ui.screens.prototype_view import PrototypeView
from semester_pilot.ui.view_models.assignment_view_model import AssignmentViewModel
from semester_pilot.ui.view_models.dashboard_view_model import DashboardViewModel
from semester_pilot.ui.view_models.first_run_view_model import FirstRunViewModel
from semester_pilot.ui.view_models.prototype_view_model import PrototypeViewModel

__all__ = [
    "AssignmentView",
    "AssignmentViewModel",
    "DashboardView",
    "DashboardViewModel",
    "FirstRunView",
    "FirstRunViewModel",
    "PrototypeView",
    "PrototypeViewModel",
]
