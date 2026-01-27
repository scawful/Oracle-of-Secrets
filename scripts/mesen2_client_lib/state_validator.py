"""State validation module for verifying loaded save states.

Validates that a loaded save state matches its expected metadata,
catching issues like corrupted states or ROM version mismatches.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    """Result of validating a loaded save state."""

    valid: bool
    state_id: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    actual: dict[str, Any] = field(default_factory=dict)
    expected: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        """Allow using result in boolean context."""
        return self.valid

    def summary(self) -> str:
        """Return a human-readable summary."""
        if self.valid:
            if self.warnings:
                return f"OK with {len(self.warnings)} warning(s)"
            return "OK"
        return f"INVALID: {len(self.errors)} error(s)"


class StateValidator:
    """Validates loaded save states against expected metadata.

    After loading a save state, use this validator to verify that the
    game is in the expected state before running tests. This catches:
    - Corrupted save states
    - ROM version mismatches
    - Incorrect state loaded (e.g., wrong slot)
    """

    # SNES memory addresses
    ADDR_GAME_MODE = 0x7E0010
    ADDR_SUBMODULE = 0x7E0011
    ADDR_LINK_X = 0x7E0022
    ADDR_LINK_Y = 0x7E0020
    ADDR_AREA_ID = 0x7E008A
    ADDR_ROOM_ID = 0x7E00A0
    ADDR_INDOORS = 0x7E001B

    # Default position tolerance (pixels)
    DEFAULT_POSITION_TOLERANCE = 32

    def __init__(self, position_tolerance: int = DEFAULT_POSITION_TOLERANCE):
        """Initialize validator.

        Args:
            position_tolerance: Max position difference before warning (pixels)
        """
        self.position_tolerance = position_tolerance

    def read_current_state(self, bridge) -> dict[str, Any]:
        """Read current game state from emulator.

        Args:
            bridge: MesenBridge instance

        Returns:
            Dictionary with current state values
        """
        return {
            "mode": bridge.read_memory(self.ADDR_GAME_MODE),
            "submodule": bridge.read_memory(self.ADDR_SUBMODULE),
            "area": bridge.read_memory(self.ADDR_AREA_ID),
            "room": bridge.read_memory(self.ADDR_ROOM_ID),
            "indoors": bool(bridge.read_memory(self.ADDR_INDOORS)),
            "link_x": bridge.read_memory16(self.ADDR_LINK_X),
            "link_y": bridge.read_memory16(self.ADDR_LINK_Y),
        }

    def validate(
        self,
        bridge,
        expected: dict[str, Any],
        state_id: str = ""
    ) -> ValidationResult:
        """Validate current state against expected metadata.

        Args:
            bridge: MesenBridge instance connected to emulator
            expected: Expected state from manifest (gameState, linkState, meta)
            state_id: State ID for error messages

        Returns:
            ValidationResult with detailed validation outcome
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Read current state from emulator
        actual = self.read_current_state(bridge)

        # Extract expected values from manifest format
        game_state = expected.get("gameState", {})
        link_state = expected.get("linkState", {})
        meta = expected.get("meta", {})

        # Parse expected mode (can be string like "0x09" or int)
        expected_mode = self._parse_hex_value(game_state.get("mode"))
        expected_submode = self._parse_hex_value(game_state.get("submode"))
        expected_room = self._parse_hex_value(game_state.get("room"))
        expected_indoors = game_state.get("indoors")

        # Validate game mode
        if expected_mode is not None and actual["mode"] != expected_mode:
            errors.append(
                f"Mode mismatch: got {hex(actual['mode'])}, "
                f"expected {hex(expected_mode)}"
            )

        # Validate submodule (warning only - can change quickly)
        if expected_submode is not None and actual["submodule"] != expected_submode:
            warnings.append(
                f"Submodule mismatch: got {hex(actual['submodule'])}, "
                f"expected {hex(expected_submode)}"
            )

        # Validate indoors flag
        if expected_indoors is not None and actual["indoors"] != expected_indoors:
            errors.append(
                f"Indoor flag mismatch: got {actual['indoors']}, "
                f"expected {expected_indoors}"
            )

        # Validate room/area based on indoor status
        if expected_room is not None:
            if actual["indoors"]:
                if actual["room"] != expected_room:
                    errors.append(
                        f"Room mismatch: got {hex(actual['room'])}, "
                        f"expected {hex(expected_room)}"
                    )
            else:
                # For overworld, compare area
                expected_area = self._parse_hex_value(
                    game_state.get("overworldArea") or game_state.get("roomId")
                )
                if expected_area is not None and actual["area"] != expected_area:
                    errors.append(
                        f"Area mismatch: got {hex(actual['area'])}, "
                        f"expected {hex(expected_area)}"
                    )

        # Validate position (warning only - save states can have slight variations)
        expected_x = link_state.get("x")
        expected_y = link_state.get("y")

        if expected_x is not None and expected_y is not None:
            dx = abs(actual["link_x"] - expected_x)
            dy = abs(actual["link_y"] - expected_y)

            if dx > self.position_tolerance or dy > self.position_tolerance:
                warnings.append(
                    f"Position differs: got ({actual['link_x']}, {actual['link_y']}), "
                    f"expected ({expected_x}, {expected_y}), "
                    f"delta=({dx}, {dy})"
                )

        return ValidationResult(
            valid=len(errors) == 0,
            state_id=state_id,
            errors=errors,
            warnings=warnings,
            actual=actual,
            expected={
                "mode": expected_mode,
                "submodule": expected_submode,
                "indoors": expected_indoors,
                "room": expected_room,
                "link_x": expected_x,
                "link_y": expected_y,
            }
        )

    def _parse_hex_value(self, value: Any) -> int | None:
        """Parse a hex string or int value.

        Args:
            value: Value that could be int, hex string, or None

        Returns:
            Integer value or None
        """
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                # Handle "0x09" or "09" format
                return int(value, 16) if value.startswith("0x") else int(value, 16)
            except ValueError:
                return None
        return None

    def validate_quick(self, bridge, expected_mode: int) -> bool:
        """Quick validation - just check game mode.

        Args:
            bridge: MesenBridge instance
            expected_mode: Expected game mode value

        Returns:
            True if mode matches
        """
        actual_mode = bridge.read_memory(self.ADDR_GAME_MODE)
        return actual_mode == expected_mode
