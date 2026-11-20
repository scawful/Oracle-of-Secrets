#!/usr/bin/env python3
"""Door-surround policy: D4/D5/D6 may stamp; shared vanilla rooms stay off."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASM = ROOT / "Dungeons" / "door_surrounds.asm"
TABLE = ROOT / "Dungeons" / "generated" / "door_surround_exceptions.asm"
DUNGEONS_ASM = ROOT / "Dungeons" / "dungeons.asm"
DUNGEONS_JSON = ROOT / "Docs" / "Dev" / "Planning" / "dungeons.json"
ROOM_LIMIT = 0x110
OWNERS = {"D4", "D5", "D6"}


def _owners() -> dict[int, set[str]]:
    data = json.loads(DUNGEONS_JSON.read_text(encoding="utf-8"))
    out: dict[int, set[str]] = {}
    for dungeon in data["dungeons"]:
        for room in dungeon["rooms"]:
            out.setdefault(int(room["id"], 16), set()).add(dungeon["id"])
    return out


def _enabled() -> list[int]:
    text = TABLE.read_text(encoding="utf-8")
    start = text.index("Oracle_DoorSurrounds_EnabledRooms:")
    end = text.index("Oracle_DoorSurrounds_EnabledRoomsEnd:")
    body = text[start:end]
    db_lines = [line.split(";", 1)[0] for line in body.splitlines() if re.match(r"\s*db\s", line)]
    raw = [int(tok, 16) for tok in re.findall(r"\$([0-9A-Fa-f]{2})", "\n".join(db_lines))]
    if len(raw) != ROOM_LIMIT:
        raise AssertionError(f"enable table is {len(raw)} bytes, want ${ROOM_LIMIT:04X}")
    return raw


def _exceptions() -> list[tuple[int, int]]:
    text = TABLE.read_text(encoding="utf-8")
    start = text.index("Oracle_DoorSurrounds_Exceptions:")
    end = text.index("Oracle_DoorSurrounds_ExceptionsEnd:")
    pairs = [
        (int(room, 16), int(key, 16))
        for room, key in re.findall(r"dw \$([0-9A-Fa-f]+), \$([0-9A-Fa-f]+)", text[start:end])
    ]
    return pairs


class DoorSurroundPolicyTest(unittest.TestCase):
    def test_only_d4_d5_d6_rooms_are_enabled(self):
        owners = _owners()
        enabled = [i for i, byte in enumerate(_enabled()) if byte]
        self.assertTrue(enabled)
        for room in enabled:
            self.assertEqual(_enabled()[room], 0x01)
            own = owners.get(room, set())
            self.assertTrue(own, f"room ${room:03X} is enabled but not in dungeons.json")
            self.assertTrue(own <= OWNERS, f"room ${room:03X} belongs to {sorted(own)}")
            self.assertEqual(len(own), 1, f"room ${room:03X} is shared by {sorted(own)}")

    def test_every_exclusive_d4_d5_d6_room_in_window_is_enabled(self):
        owners = _owners()
        enabled = _enabled()
        expected = {
            room
            for room, own in owners.items()
            if own <= OWNERS and len(own) == 1 and room < ROOM_LIMIT
        }
        got = {i for i, byte in enumerate(enabled) if byte}
        self.assertEqual(got, expected)
        self.assertIn(0x10B, got)  # D4 dam entrance
        self.assertNotIn(0x00, got)
        self.assertNotIn(0x012, got)

    def test_other_dungeon_rooms_stay_off(self):
        owners = _owners()
        enabled = _enabled()
        for room, own in owners.items():
            if room >= ROOM_LIMIT:
                continue
            if not (own <= OWNERS):
                self.assertEqual(enabled[room], 0, f"${room:03X} {sorted(own)} must stay off")

    def test_exceptions_are_unique_and_terminated(self):
        pairs = _exceptions()
        self.assertGreater(len(pairs), 100)
        self.assertEqual(len(pairs), len(set(pairs)))
        self.assertEqual(pairs, sorted(pairs))
        tail = TABLE.read_text(encoding="utf-8")
        self.assertIn("Oracle_DoorSurrounds_ExceptionsEnd:\n  dw $FFFF, $FFFF\n", tail)
        self.assertIn('db "DSR2"', tail)
        self.assertIn("dw $0110", tail)

    def test_hook_does_not_consume_bank_2c_or_header(self):
        asm = ASM.read_text(encoding="utf-8")
        wiring = DUNGEONS_ASM.read_text(encoding="utf-8")
        self.assertIn("org $5E8400", asm)
        self.assertIn("assert pc() == $018914", asm)
        self.assertIn("assert pc() == $01B560", asm)
        self.assertIn("assert pc() <= $5E8C00", asm)
        self.assertNotIn("!ENABLE_DUNGEON_DOOR_SURROUNDS", asm)
        self.assertIn('incsrc "Dungeons/door_surrounds.asm"', wiring)
        self.assertIn("door surrounds consumed bank $2C", wiring)
        self.assertNotRegex(asm, r"^\s*!ENABLE_", "door surrounds must not define a feature flag")


if __name__ == "__main__":
    unittest.main()
