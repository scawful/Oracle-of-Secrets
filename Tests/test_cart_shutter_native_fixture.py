"""Offline refusal controls for the Phase A cart-shutter fixture; no socket."""
import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.dont_write_bytecode = True
PATH = Path(__file__).parent / "native" / "cart_shutter_door.py"
spec = importlib.util.spec_from_file_location("cart_shutter_fixture_control", PATH)
cart = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cart)


def symbols(handler=0x318000):
    return f"{handler >> 16:02X}:{handler & 65535:04X} Oracle_RoomTag_ShutterDoorRequiresCart\n01:CC5A Oracle_RoomTag_Return\n"


def wired_rom(handler=0x318000):
    rom = bytearray(cart.dispatch.pc_offset(handler) + len(cart.HANDLER_BYTES))
    for address, expected, _ in cart.PINNED:
        start = cart.dispatch.pc_offset(address)
        rom[start:start + len(expected) // 2] = bytes.fromhex(expected)
    start = cart.dispatch.pc_offset(cart.HOOK)
    rom[start:start + 4] = b"\x5c" + handler.to_bytes(3, "little")
    start = cart.dispatch.pc_offset(handler)
    rom[start:start + len(cart.HANDLER_BYTES)] = cart.HANDLER_BYTES
    return rom


def changed(rom, address, data):
    result = bytearray(rom)
    start = cart.dispatch.pc_offset(address)
    result[start:start + len(data)] = data
    return bytes(result)


class FakeBridge:
    def __init__(self, paused=True, pc=cart.HOOK):
        self.paused, self.pc, self.memory, self.calls = paused, pc, {}, []

    def send_command(self, command, params=None):
        self.calls.append((command, params))
        if command == "STATE":
            return {"success": True, "data": {"paused": self.paused}}
        if command == "READ":
            return {"success": True, "data": hex(self.memory.get(int(params["addr"], 16), 0))}
        raise AssertionError("Unexpected native command " + command)

    def get_cpu_state(self):
        return {"pc": self.pc, "sp": 0x1F0}

    def write_memory(self, address, value):
        self.calls.append(("WRITE", address, value))
        self.memory[address] = value
        return True


class CartShutterNativeControls(unittest.TestCase):
    def test_handler_is_resolved_instead_of_fixed_to_an_old_build(self):
        for handler in (0x318000, 0x32A400):
            with self.subTest(handler=handler):
                result = cart.validate_candidate(wired_rom(handler), symbols(handler))
                self.assertEqual(result["handler"], f"{handler:06X}")
                self.assertEqual(result["handler_size"], 41)

    def test_unhooked_wrong_target_and_jsl_are_refused(self):
        rom = wired_rom()
        for wrong in (cart.UNHOOKED, bytes.fromhex("5c108031"), bytes.fromhex("22008031")):
            with self.subTest(wrong=wrong.hex()), self.assertRaises(RuntimeError):
                cart.validate_candidate(changed(rom, cart.HOOK, wrong), symbols())

    def test_missing_ambiguous_wrong_return_and_wram_symbols_are_refused(self):
        for text in ("01:CC5A Oracle_RoomTag_Return\n",
                     symbols() + "32:8000 Oracle_RoomTag_ShutterDoorRequiresCart\n",
                     symbols().replace("01:CC5A", "01:CC58"), symbols(0x7E8000)):
            with self.subTest(symbols=text), self.assertRaises(RuntimeError):
                cart.validate_candidate(wired_rom(), text)

    def test_every_dispatch_boundary_is_pinned(self):
        rom = wired_rom()
        for address, expected, label in cart.PINNED:
            corrupt = bytes([bytes.fromhex(expected)[0] ^ 0xFF])
            with self.subTest(label=label), self.assertRaisesRegex(RuntimeError, "Pinned bytes differ"):
                cart.validate_candidate(changed(rom, address, corrupt), symbols())

    def test_compiled_body_and_truncated_rom_are_refused(self):
        rom = wired_rom()
        for offset in range(len(cart.HANDLER_BYTES)):
            corrupt = bytes([cart.HANDLER_BYTES[offset] ^ 0xFF])
            with self.subTest(offset=offset), self.assertRaisesRegex(RuntimeError, "Compiled cart shutter body"):
                cart.validate_candidate(changed(rom, 0x318000 + offset, corrupt), symbols())
        with self.assertRaisesRegex(RuntimeError, "ROM too short"):
            cart.validate_candidate(rom[:-1], symbols())

    def test_truth_table_has_one_open_and_three_unchanged_cases(self):
        cases = cart.describe()["cases"]
        self.assertEqual({(c["mounted"], c["door"]) for c in cases}, {(0, 0), (0, 1), (1, 0), (1, 1)})
        self.assertEqual([c["name"] for c in cases if c["expected_handler_writes"]], ["mounted-closed-opens"])
        for case in cases:
            self.assertEqual(set(cart.case_writes(case)), cart.ADMITTED - set(cart.TAGS))
            self.assertEqual(case["writes"]["0036"], 0xA5)

    def test_watchpoints_cover_adjacent_flag_byte_and_forbidden_writes(self):
        watches = cart.watches(cart.OPEN)
        covered = lambda address, kind: any(lo <= address <= hi and k == kind for lo, hi, k in watches)
        self.assertFalse(covered(0x35, "read"))
        self.assertTrue(covered(0x36, "read"))
        self.assertTrue(covered(0x12F, "read"))
        self.assertFalse(covered(0x468, "write"))
        self.assertTrue(covered(0x467, "write"))
        self.assertTrue(covered(0x692, "write"))
        self.assertTrue(covered(0x1FFFF, "write"))
        self.assertTrue(any(lo <= 0x468 <= hi for lo, hi, kind in cart.watches({}) if kind == "write"))

    def test_forbidden_unpaused_and_wrong_boundary_writes_are_refused(self):
        for address, paused, pc in ((0x22, True, cart.HOOK), (0x35, False, cart.HOOK),
                                    (0x35, True, cart.HOOK + 1)):
            bridge = FakeBridge(paused, pc)
            fixture = cart.CartShutterFixture(SimpleNamespace(), bridge, {"handler": "318000"})
            with self.subTest(address=address, paused=paused, pc=pc), self.assertRaises(RuntimeError):
                fixture.write(address, 1, "test", cart.HOOK)
            self.assertFalse(any(call[0] == "WRITE" for call in bridge.calls))

    def test_allowed_write_is_read_back_and_restore_clears_dirty_state(self):
        bridge = FakeBridge()
        bridge.memory[0x7E0035] = 0
        fixture = cart.CartShutterFixture(SimpleNamespace(), bridge, {"handler": "318000"})
        fixture.write(0x35, 1, "test", cart.HOOK)
        self.assertEqual(fixture.dirty, {0x35: 0})
        fixture.restore({0x35}, "test restore", cart.HOOK)
        self.assertEqual(bridge.memory[0x7E0035], 0)
        self.assertFalse(fixture.dirty)

    def test_unhooked_runtime_is_rejected_before_process_or_bridge_access(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            rom = changed(wired_rom(), cart.HOOK, cart.UNHOOKED)
            (p / "candidate.sfc").write_bytes(rom)
            (p / "candidate.sym").write_text(symbols())
            args = ["--execute-fixtures", "--socket", "/tmp/mesen2-cart-test.sock", "--pid", "123",
                    "--owner", "cart-test", "--owner-file", str(p / "owner"), "--status-file", str(p / "status"),
                    "--owned-rom", str(p / "candidate.sfc"), "--symbols", str(p / "candidate.sym"),
                    "--rom-sha256", cart.digest(rom), "--symbols-sha256", cart.digest(symbols().encode()),
                    "--client-root", str(p / "client"), "--output", str(p / "output")]
            with mock.patch.object(cart.subprocess, "check_output") as process:
                with self.assertRaisesRegex(RuntimeError, "Unhooked candidate"):
                    cart.main(args)
                process.assert_not_called()
            self.assertFalse((p / "output").exists())

    def test_describe_is_source_only_and_candidate_validation_returns_failure(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(cart.main(["--describe"]), 0)
        self.assertFalse(json.loads(out.getvalue())["native_executed"])
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p / "bad.sfc").write_bytes(wired_rom()[:-1])
            (p / "symbols").write_text(symbols())
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cart.main(["--validate-candidate", "--owned-rom", str(p / "bad.sfc"),
                                           "--symbols", str(p / "symbols")]), 2)


if __name__ == "__main__":
    unittest.main()
