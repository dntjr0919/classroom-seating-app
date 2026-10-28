"""
views 패키지 초기화 모듈
"""

from .grid_designer import GridDesignerDialog
from .hidden_admin_dialog import HiddenAdminDialog, MiniPresetSeatButton
from .seating_view import DeskCardWidget, SeatingBoardView
from .shortcut_dialog import (
    ACTION_CLEAR_ASSIGNMENT,
    ACTION_EXPORT_PRINT_PDF,
    ACTION_LAYOUT_MGMT,
    ACTION_LOAD_EXCEL,
    ACTION_OPEN_EXPORT_MENU,
    ACTION_ROSTER_MGMT,
    ACTION_RUN_PLACEMENT,
    ACTION_SAVE_EXCEL,
    ACTION_SHORTCUT_SETTINGS,
    DEFAULT_SHORTCUTS,
    ShortcutManager,
    ShortcutSettingsDialog,
)
from .student_dialog import StudentRosterDialog
from .theme_manager import ThemeManager, show_saved_file_message

__all__ = [
    "DeskCardWidget",
    "GridDesignerDialog",
    "HiddenAdminDialog",
    "MiniPresetSeatButton",
    "SeatingBoardView",
    "ShortcutManager",
    "ShortcutSettingsDialog",
    "StudentRosterDialog",
    "ThemeManager",
    "show_saved_file_message",
    "ACTION_CLEAR_ASSIGNMENT",
    "ACTION_EXPORT_PRINT_PDF",
    "ACTION_LAYOUT_MGMT",
    "ACTION_LOAD_EXCEL",
    "ACTION_OPEN_EXPORT_MENU",
    "ACTION_ROSTER_MGMT",
    "ACTION_RUN_PLACEMENT",
    "ACTION_SAVE_EXCEL",
    "ACTION_SHORTCUT_SETTINGS",
    "DEFAULT_SHORTCUTS",
]
