"""Offline admission controls for the two room97 vertical drag callsites."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).parent / "native" / "goron97_cart_gate.py"
SPEC = importlib.util.spec_from_file_location("goron97_drag_binding", PATH)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)

WRAPPER = 0x2CFA00
NORTH, SOUTH = 0x31B05A, 0x31B0DA


def fixture():
    symbols = {"Minecart_MoveNorth": 0x31B028, "Minecart_MoveEast": 0x31B068,
               "Minecart_MoveSouth": 0x31B0A8, "Minecart_MoveWest": 0x31B0E8,
               "CartShutter97_DragNorthCall": NORTH, "CartShutter97_DragNorthCall_End": NORTH + 4,
               "CartShutter97_DragSouthCall": SOUTH, "CartShutter97_DragSouthCall_End": SOUTH + 4,
               "RoomTag_CartShutterDispatch": 0x2CFB00, "RoomTag_CartShutterDispatch_End": 0x2CFB13,
               "RoomTag_CartShutter97": 0x2CFB13, "RoomTag_CartShutter97_End": 0x2CFCA4,
               "CartShutter97_DragPlayer": WRAPPER, "CartShutter97_DragPlayer_End": WRAPPER + 0x67}
    rom = bytearray(gate.native.pc_offset(0x31B100))
    for address in (NORTH, SOUTH):
        at = gate.native.pc_offset(address)
        rom[at:at + 4] = b"\x22" + WRAPPER.to_bytes(3, "little")
    at = gate.native.pc_offset(0x01CC14)
    rom[at:at + 4] = b"\x5c\x00\xfb\x2c"
    at = gate.native.pc_offset(0x01C2EB)
    rom[at:at + 2] = b"\x14\xcc"
    return rom, symbols


def symbol_text(symbols):
    return "".join(f"{value >> 16:02X}:{value & 65535:04X} Oracle_{name}\n"
                   for name, value in symbols.items())


class Goron97DragBinding(unittest.TestCase):
    def test_both_vertical_calls_must_target_the_wrapper(self):
        rom, symbols = fixture()
        calls = gate.validate_drag_calls(rom, symbol_text(symbols), WRAPPER)
        self.assertEqual([call["name"] for call in calls],
                         ["CartShutter97_DragNorthCall", "CartShutter97_DragSouthCall"])
        for address in (NORTH, SOUTH):
            for raw in (b"\x5c\x00\xfa\x2c", b"\x22\x07\x82\x31", b"\x22\x01\xfa\x2c"):
                changed = bytearray(rom)
                at = gate.native.pc_offset(address)
                changed[at:at + 4] = raw
                with self.subTest(address=address, raw=raw.hex()), self.assertRaisesRegex(RuntimeError, "JSL target"):
                    gate.validate_drag_calls(changed, symbol_text(symbols), WRAPPER)

    def test_missing_wrong_span_or_wrong_owner_call_labels_are_refused(self):
        rom, symbols = fixture()
        for name in ("CartShutter97_DragNorthCall", "CartShutter97_DragSouthCall"):
            missing = dict(symbols); del missing[name]
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                gate.validate_drag_calls(rom, symbol_text(missing), WRAPPER)
            for start, size in ((symbols[name], 3), (0x30B05A, 4),
                                (symbols["Minecart_MoveEast"], 4)):
                changed = dict(symbols)
                changed[name], changed[name + "_End"] = start, start + size
                with self.subTest(name=name, start=start, size=size), self.assertRaisesRegex(RuntimeError, "callsite"):
                    gate.validate_drag_calls(rom, symbol_text(changed), WRAPPER)

    def test_compiled_hash_requires_the_separate_wrapper_span(self):
        rom, symbols = fixture()
        names = ("RoomTag_CartShutterDispatch", "RoomTag_CartShutter97", "CartShutter97_DragPlayer")
        spans = [rom[gate.native.pc_offset(symbols[name]):gate.native.pc_offset(symbols[name + "_End"])]
                 for name in names]
        expected = gate.digest(b"".join(spans))
        old_two_span_hash = gate.digest(b"".join(spans[:2]))
        changed = bytearray(rom); changed[gate.native.pc_offset(WRAPPER) + 50] ^= 1
        for image, code in ((rom, old_two_span_hash), (changed, expected)):
            with self.subTest(code=code), self.assertRaisesRegex(RuntimeError, "SHA256 mismatch"):
                gate.validate_candidate(image, symbol_text(symbols), code)


if __name__ == "__main__":
    unittest.main()
