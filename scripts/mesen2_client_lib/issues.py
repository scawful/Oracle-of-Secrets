"""Known issue patterns for Oracle debugging."""

from .constants import LOST_WOODS_AREAS


def _is_lost_woods(state: dict) -> bool:
    """Check if current area is in Lost Woods."""
    return state.get("area", 0) in LOST_WOODS_AREAS


def _scroll_offset_nonzero(state: dict) -> bool:
    """Check if scroll offset is non-zero (potential camera issue)."""
    # This would require reading the actual scroll values
    return False  # Placeholder - implement with actual detection


KNOWN_ISSUES = {
    "lost_woods_scroll": {
        "description": "Camera offset drift in Lost Woods transitions",
        "trigger": _is_lost_woods,
        "watch": ["E1", "E7"],
        "warning": "WARNING: In Lost Woods area - watch for E1 offset drift after transitions.",
    },
    "water_collision": {
        "description": "Water collision at wrong Y offset",
        "trigger": lambda state: state.get("area") == 0x27,
        "watch": ["collision_map"],
        "warning": "Check collision at Link Y + 20 pixels (TileDetect offset)",
    },
    "probe_detection": {
        "description": "Vanilla probe sets $0D80,X not SprTimerD",
        "trigger": lambda _: False,  # Manual check only
        "watch": ["SprState", "SprTimerD"],
        "warning": "Probe detection uses SprState ($0D80,X), NOT SprTimerD ($0EE0,X)",
    },
}
