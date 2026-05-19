from dataclasses import dataclass
from importlib import resources

CLI_NAME = 'ucap'
FORMATTED_CLI_NAME = 'uCap'

LOGGER_NAME = CLI_NAME
LOG_FORMAT = '[%(asctime)s]%(name)s:%(levelname)s: %(message)s'

# Sentinel for "use maximum SWD frequency"
MAX_FREQ = 2_000_000_000  # 2 GHz, clamped by backend to hardware max

MON_GUI_ICON_SIZE = 16

MON_GUI_DRAINING_DATA_LIMIT = 5000

ASSETS_DIR = resources.files('ucap.assets')
QSS_PATH = ASSETS_DIR.joinpath('style.qss')

MON_CURVE_COLORS = [
    '#3b82f6',
    '#f97316',
    '#22c55e',
    '#ef4444',
    '#a855f7',
    '#84cc16',
    '#ec4899',
    '#06b6d4',
    '#eab308',
    '#6366f1',
]

MON_GUI_THEMES = {
    "dark": {
        "bg_primary": "#09090b",
        "bg_secondary": "#18181b",
        "bg_tertiary": "#27272a",
        "bg_hover": "#3f3f46",
        "bg_pressed": "#52525b",
        "bg_checked": "#1e3a5f",
        "text_primary": "#fafafa",
        "text_secondary": "#d4d4d8",
        "text_muted": "#a1a1aa",
        "border": "#52525b",
        "border_hover": "#71717a",
        "border_checked": "#3b82f6",
        "separator": "#27272a",
        "accent": "#3b82f6",
        "success": "#22c55e",
        "error": "#ef4444",
        "plot_bg": "#18181b",
        "plot_grid": "#52525b",
        "plot_axis": "#a1a1aa",
        "probe_bg": "rgba(24,24,27,245)",
    },
    "light": {
        "bg_primary": "#ffffff",
        "bg_secondary": "#fafafa",
        "bg_tertiary": "#f4f4f5",
        "bg_hover": "#e4e4e7",
        "bg_pressed": "#d4d4d8",
        "bg_checked": "#dbeafe",
        "text_primary": "#18181b",
        "text_secondary": "#3f3f46",
        "text_muted": "#71717a",
        "border": "#d4d4d8",
        "border_hover": "#a1a1aa",
        "border_checked": "#3b82f6",
        "separator": "#e4e4e7",
        "accent": "#3b82f6",
        "success": "#16a34a",
        "error": "#dc2626",
        "plot_bg": "#ffffff",
        "plot_grid": "#a1a1aa",
        "plot_axis": "#52525b",
        "probe_bg": "rgba(255,255,255,245)",
    },
}


@dataclass(slots=True)
class ShortcutDef:
    sequence: str
    description: str


SHORTCUTS: dict[str, ShortcutDef] = {
    "pause":
    ShortcutDef(
        sequence="Space",
        description="Pause/Resume monitor",
    ),
    "save":
    ShortcutDef(
        sequence="Ctrl+S",
        description="Save data to disk",
    ),
    "clear":
    ShortcutDef(
        sequence="Ctrl+L",
        description="Clear data",
    ),
    "zoom":
    ShortcutDef(
        sequence="Z",
        description="Drag to zoom into a region",
    ),
    "view_all":
    ShortcutDef(
        sequence="V",
        description="Show all data",
    ),
    "auto_y":
    ShortcutDef(
        sequence="Y",
        description="Auto-scale Y axis",
    ),
    "probe":
    ShortcutDef(
        sequence="P",
        description="Show data values at cursor",
    ),
    "theme":
    ShortcutDef(
        sequence="Ctrl+T",
        description="Toggle light/dark theme",
    ),
}
