"""Offline safety controls for Tests/native/somaria_socket_door.py; no emulator or socket."""
import importlib.util
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import re
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
PATH = HERE / "native" / "somaria_socket_door.py"
sys.dont_write_bytecode = True


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


door = load("somaria_native_fixture_control", PATH)
model = load("somaria_source_model_control", HERE / "test_somaria_socket_door.py")
SYMBOLS = "2C:FD00 Oracle_RoomTag_SomariaSocketDoor\n01:CC5A Oracle_RoomTag_Return\n"


def offset(address):
    return ((address >> 16) & 0x7F) * 0x8000 + (address & 0x7FFF)


def wired_rom():
    rom = bytearray(offset(0x2CFE00))
    for address, expected, _ in door.PINNED:
        data = bytes.fromhex(expected)
        rom[offset(address):offset(address) + len(data)] = data
    rom[offset(door.HOOK):offset(door.HOOK) + 4] = door.HOOK_JML
    return rom


def patched(rom, address, data):
    copy = bytearray(rom)
    copy[offset(address):offset(address) + len(data)] = data
    return bytes(copy)


class FakeBridge:
    def __init__(self, pc):
        self.pc, self.paused, self.memory, self.calls = pc, True, {}, []

    def send_command(self, kind, params=None):
        self.calls.append((kind, dict(params or {})))
        if kind == "STATE":
            return {"success": True, "data": {"paused": self.paused, "frame": 1}}
        if kind == "READ":
            return {"success": True, "data": f"0x{self.memory.get(int(params['addr'], 16), 0):02X}"}
        raise AssertionError(f"unexpected command {kind}")

    def get_cpu_state(self):
        return {"pc": f"0x{self.pc:06X}", "sp": "0x01F0"}

    def write_memory(self, address, value):
        self.calls.append(("WRITE", {"addr": address, "value": value}))
        self.memory[address] = value
        return True


class Args:
    pass


class SomariaNativeFixtureControls(unittest.TestCase):
    def test_wired_candidate_is_admitted(self):
        code = door.validate_candidate(bytes(wired_rom()), SYMBOLS)
        self.assertEqual(code["hook"], "01CC89 JML 2CFD00")
        self.assertEqual(code["handler_size"], 111)

    def test_unhooked_and_wrong_hook_candidates_are_refused(self):
        rom = bytes(wired_rom())
        with self.assertRaisesRegex(RuntimeError, "Unhooked candidate"):
            door.validate_candidate(patched(rom, door.HOOK, door.UNHOOKED_HOLES2), SYMBOLS)
        for wrong in ("5c00fe2c", "2200fd2c", "4c00fd00"):
            with self.subTest(hook=wrong), self.assertRaisesRegex(RuntimeError, "Wrong tag \\$24 hook"):
                door.validate_candidate(patched(rom, door.HOOK, bytes.fromhex(wrong)), SYMBOLS)

    def test_wrong_missing_or_ambiguous_symbols_are_refused(self):
        rom = bytes(wired_rom())
        for text, message in (
                (SYMBOLS.replace("2C:FD00", "2C:FE00"), "Handler symbol"),
                (SYMBOLS.replace("01:CC5A", "01:CC58"), "RoomTag_Return"),
                ("01:CC5A Oracle_RoomTag_Return\n", "RoomTag_SomariaSocketDoor"),
                (SYMBOLS + "2C:FD10 RoomTag_SomariaSocketDoor\n", "ambiguous")):
            with self.subTest(message=message), self.assertRaisesRegex(RuntimeError, message):
                door.validate_candidate(rom, text)

    def test_every_pinned_boundary_is_enforced(self):
        rom = bytes(wired_rom())
        for address, expected, label in door.PINNED:
            corrupt = bytes([bytes.fromhex(expected)[0] ^ 0xFF])
            with self.subTest(label=label), self.assertRaisesRegex(RuntimeError, "Pinned bytes differ"):
                door.validate_candidate(patched(rom, address, corrupt), SYMBOLS)
        with self.assertRaisesRegex(RuntimeError, "ROM too short"):
            door.validate_candidate(rom[:offset(0x2CFD40)], SYMBOLS)

    def test_pinned_handler_decodes_the_documented_boundaries(self):
        body = door.HANDLER_BYTES
        self.assertEqual(len(body), model.assembled_size(model.parse(model.routine_lines())[0]))
        self.assertEqual(body[0x06:0x09], bytes.fromhex("ad4606"))      # LDA $0646 (read control)
        self.assertEqual(body[0x51:0x54], bytes.fromhex("8e6804"))      # STX $0468 (write control)
        self.assertEqual(body[-4:], bytes.fromhex("5c5acc01"))          # JML RoomTag_Return

    @unittest.skipUnless(os.environ.get("OOS_SOMARIA_CANDIDATE_ROM"), "set OOS_SOMARIA_CANDIDATE_ROM")
    def test_built_candidate_matches_pins_and_reports_hook_state(self):
        rom = Path(os.environ["OOS_SOMARIA_CANDIDATE_ROM"]).read_bytes()
        self.assertEqual(rom[offset(door.HANDLER):offset(door.HANDLER) + 111], door.HANDLER_BYTES)
        hook = rom[offset(door.HOOK):offset(door.HOOK) + 4]
        if hook == door.UNHOOKED_HOLES2:
            with self.assertRaisesRegex(RuntimeError, "Unhooked candidate"):
                door.validate_candidate(rom, SYMBOLS)
        else:
            door.validate_candidate(rom, SYMBOLS)

    def test_case_expectations_match_the_source_routine_model(self):
        program, labels = model.parse(model.routine_lines())
        names = [row["name"] for row in door.CASES]
        self.assertEqual(len(names), len(set(names)))
        for row in door.CASES:
            memory = {0x001B: 0x01, 0x0011: 0x00, 0x000E: 0x00, 0x00AE: 0x24, 0x00AF: 0x00}
            memory.update(door.case_writes(row))
            machine = model.Machine(memory)
            with self.subTest(case=row["name"]):
                self.assertEqual(machine.run(program, labels), "RoomTag_Return")
                self.assertEqual(machine.writes, door.EXPECTED[row["expect"]])

    def test_rejections_differ_from_a_qualifying_open_door_by_their_named_input(self):
        base = dict(door.case_writes(door.case("base", 0, "none")))
        for row in door.CASES:
            if not row["name"].startswith("reject-"):
                continue
            changed = {a for a, v in door.case_writes(row) if base[a] != v}
            with self.subTest(case=row["name"]):
                self.assertEqual(row["expect"], "close")
                self.assertTrue(changed)
                self.assertTrue(changed <= set(door.GLOBALS + door.SLOT_FIELDS))

    def test_writes_stay_inside_admitted_fixture_boundary(self):
        for row in door.CASES:
            for address, value in door.case_writes(row):
                self.assertIn(address, door.ADMITTED)
                self.assertTrue(0 <= value <= 0xFF)
        self.assertEqual(door.ADMITTED & {0x000E, 0x001B, 0x0010, 0x00A0, 0x00A1, 0x04C7}, set())
        handler_reads = {0x001B, 0x0646, 0x0308, 0x03F4} | {t + s for t in door.SLOT_FIELDS for s in range(5)}
        for lo, hi, label in door.READ_WATCH:
            watched = set(range(lo, hi + 1))
            with self.subTest(watch=label):
                self.assertEqual(watched & handler_reads, set())
                self.assertEqual(watched & (door.ADMITTED - {0x0642}), set())

    def test_write_watch_covers_all_wram_except_allowed_bytes(self):
        for allowed in (set(), set(door.EXPECTED["open"]), set(door.EXPECTED["close"]), {0, door.WRAM_END}):
            covered = set()
            for lo, hi, kind in door.write_watch(allowed):
                self.assertEqual(kind, "write")
                self.assertLessEqual(lo, hi)
                covered |= set(range(lo, hi + 1))
            with self.subTest(allowed=sorted(allowed)):
                self.assertEqual(covered, set(range(door.WRAM_END + 1)) - allowed)
        self.assertEqual(door.write_watch(set()), [(0, door.WRAM_END, "write")])

    def make_fixture(self, pc):
        args = Args()
        bridge = FakeBridge(pc)
        return door.SomariaDoorFixture(args, bridge), bridge

    def test_write_guard_refuses_before_any_socket_write(self):
        fixture, bridge = self.make_fixture(door.HOOK)
        for address in (0x0640, 0x000E, 0x00A0, 0x7EF350 & 0xFFFF):
            with self.subTest(address=address), self.assertRaisesRegex(RuntimeError, "Forbidden"):
                fixture.write(address, 1, "probe")
        with self.assertRaisesRegex(RuntimeError, "admitted only at"):
            fixture.write(0x0646, 1, "probe", door.DISPATCH)
        bridge.paused = False
        with self.assertRaisesRegex(RuntimeError, "paused"):
            fixture.write(0x0646, 1, "probe", door.HOOK)
        self.assertFalse([c for c in bridge.calls if c[0] == "WRITE"])
        self.assertEqual(fixture.dirty, {})

    def test_write_records_readback_and_restore_returns_originals_in_reverse(self):
        fixture, bridge = self.make_fixture(door.HOOK)
        bridge.memory.update({0x7E0646: 0x00, 0x7E0C4A: 0x07})
        fixture.write(0x0646, 0x01, "probe", door.HOOK)
        fixture.write(0x0C4A, 0x2C, "probe", door.HOOK)
        self.assertEqual(fixture.result["writes"][0]["readback"], 0x01)
        self.assertEqual(fixture.dirty, {0x0646: 0x00, 0x0C4A: 0x07})
        bridge.pc = door.TAG_SLOT0_RETURN
        fixture.restore({0x0646, 0x0C4A}, "restore", door.TAG_SLOT0_RETURN)
        writes = [c[1] for c in bridge.calls if c[0] == "WRITE"]
        self.assertEqual([(w["addr"], w["value"]) for w in writes[2:]], [(0x7E0C4A, 0x07), (0x7E0646, 0x00)])
        self.assertEqual(fixture.dirty, {})

    def test_source_never_uses_forbidden_runtime_controls(self):
        code = PATH.read_text()
        for token in ("SET_PC", "EXEC_LUA", "execute_lua", "load_state", "LOADSTATE", "save_state",
                      "SAVESTATE", "clear_breakpoints", '"clear"', "write_block", "WRITEBLOCK",
                      "RESET", ".reset(", "LOADROM", "load_script", "CHEAT", "Popen", "os.kill",
                      "write_memory16", "set_cpu", "SET_REG"):
            with self.subTest(token=token):
                self.assertNotIn(token, code)
        self.assertEqual(re.findall(r"owned_rom\.(write\w*)", code), [])

    def test_describe_is_source_only_and_default_refuses(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            self.assertEqual(door.main(["--describe"]), 0)
        plan = json.loads(stream.getvalue())
        self.assertFalse(plan["native_executed"])
        self.assertEqual(len(plan["cases"]), len(door.CASES))
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "out"
            with self.assertRaisesRegex(RuntimeError, "--execute-fixtures"):
                door.main(["--output", str(output)])
            self.assertFalse(output.exists())

    def test_validate_candidate_cli_refuses_unhooked_without_socket(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rom, sym = root / "c.sfc", root / "c.sym"
            rom.write_bytes(patched(bytes(wired_rom()), door.HOOK, door.UNHOOKED_HOLES2))
            sym.write_text(SYMBOLS)
            stream = io.StringIO()
            with redirect_stdout(stream):
                code = door.main(["--validate-candidate", "--owned-rom", str(rom), "--symbols", str(sym)])
            self.assertEqual(code, 2)
            self.assertIn("Unhooked candidate", json.loads(stream.getvalue())["error"])

    def test_execute_refuses_identity_mismatch_before_output_or_bridge(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rom, sym, output = root / "c.sfc", root / "c.sym", root / "out"
            rom.write_bytes(bytes(wired_rom()))
            sym.write_text(SYMBOLS)
            base = ["--execute-fixtures", "--socket", "/tmp/mesen2-somaria-test.sock", "--pid", "1",
                    "--owned-rom", str(rom), "--symbols", str(sym), "--client-root", str(root),
                    "--status-file", str(root / "s.status"), "--owner-file", str(root / "o"),
                    "--owner", "control", "--output", str(output),
                    "--symbols-sha256", door.digest(sym.read_bytes())]
            with self.assertRaisesRegex(RuntimeError, "ROM SHA256 mismatch"):
                door.main(base + ["--rom-sha256", "0" * 64])
            bad = list(base)
            bad[bad.index("--socket") + 1] = "/tmp/mesen2-oos-rc-play.sock"
            with self.assertRaisesRegex(RuntimeError, "task-owned private socket"):
                door.main(bad + ["--rom-sha256", door.digest(rom.read_bytes())])
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
