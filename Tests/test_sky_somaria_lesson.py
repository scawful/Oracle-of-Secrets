"""Offline safety controls for Tests/native/sky_somaria_lesson.py; no emulator or socket."""
import ast
import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
PATH = HERE / "native" / "sky_somaria_lesson.py"
sys.dont_write_bytecode = True


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lesson = load("sky_somaria_lesson_control", PATH)
door = lesson.door
SYMBOLS = "2C:FD00 Oracle_RoomTag_SomariaSocketDoor\n01:CC5A Oracle_RoomTag_Return\n"
HEADERS, STREAMS, POT_LIST = 0x04F400, 0x288000, 0x01E6A9


def offset(address):
    return ((address >> 16) & 0x7F) * 0x8000 + (address & 0x7FFF)


def subtype2(oid, x, y):
    return bytes([0xFC | x >> 4, (x & 0x0F) << 4 | y >> 2, (y & 3) << 6 | (oid - 0x100)])


def subtype3(oid, x, y):
    low = oid & 0x7F
    return bytes([x << 2 | (low & 3), y << 2 | (low >> 2 & 3), 0xF8 | low >> 4])


def stream(objects, doors):
    body = b"\x00\x00" + b"".join(objects) + b"\xff\xff\xff\xff\xf0\xff"
    return body + b"".join(bytes(d) for d in doors) + b"\xff\xff"


def lesson_rom(tags=None, doors=None, objects=None, pots=None, entrance=None):
    """Smallest synthetic wired candidate that satisfies validate_candidate."""
    rom = bytearray(offset(0x2CFE00))
    for address, expected, _ in door.PINNED:
        data = bytes.fromhex(expected)
        rom[offset(address):offset(address) + len(data)] = data
    rom[offset(door.HOOK):offset(door.HOOK) + 4] = door.HOOK_JML
    tags = {0x90: (0, 0), 0x91: (0x24, 0), 0x92: (0, 0), **(tags or {})}
    doors = {0x90: [(0x83, 0x00)], 0x91: [(0x22, 0x00), (0x83, 0x18)], 0x92: [(0x22, 0x00)], **(doors or {})}
    lesson_objects = [subtype3(0xFD0, 52, 53), subtype3(0xFAF, 12, 54), subtype3(0xFAF, 18, 54)]
    objects = {0x90: [], 0x91: lesson_objects, 0x92: [], **(objects or {})}
    table = HEADERS - 0x400
    rom[lesson.HEADER_POINTER_PC:lesson.HEADER_POINTER_PC + 3] = table.to_bytes(3, "little")
    rom[lesson.HEADER_BANK_PC] = HEADERS >> 16
    at = STREAMS
    for room in (0x90, 0x91, 0x92):
        header = HEADERS + room * 16
        rom[offset(table) + room * 2:offset(table) + room * 2 + 2] = (header & 0xFFFF).to_bytes(2, "little")
        rom[offset(header) + 5:offset(header) + 7] = bytes(tags[room])
        slot = lesson.OBJECT_POINTERS_PC + room * 3
        rom[slot:slot + 3] = at.to_bytes(3, "little")
        data = stream(objects[room], doors[room])
        rom[offset(at):offset(at) + len(data)] = data
        at += 0x100
    pot_slot = offset(lesson.POT_POINTERS) + 0x91 * 2
    rom[pot_slot:pot_slot + 2] = (POT_LIST & 0xFFFF).to_bytes(2, "little")
    pot_data = b"".join((y * 0x80 + x * 2).to_bytes(2, "little") + bytes([item])
                        for x, y, item in (pots or lesson.POTS)) + b"\xff\xff"
    rom[offset(POT_LIST):offset(POT_LIST) + len(pot_data)] = pot_data
    for name, (address, expected) in lesson.EXPANDED_ENTRANCE.items():
        data = (entrance or {}).get(name, expected)
        rom[offset(address):offset(address) + len(data)] = data
    exits = offset(lesson.EXIT_ROOMS)
    rom[exits:exits + 2] = b"\x90\x00"
    rom[exits + lesson.EXIT_COUNT * 2] = lesson.OUTSIDE_AREA
    address, costs = lesson.SOMARIA_COSTS
    rom[offset(address):offset(address) + 3] = costs
    return bytes(rom)


class Args:
    pass


class SkySomariaLessonControls(unittest.TestCase):
    def test_wired_lesson_candidate_is_admitted(self):
        report = lesson.validate_candidate(lesson_rom(), SYMBOLS)
        self.assertEqual(report["tag24"]["hook"], "01CC89 JML 2CFD00")
        self.assertEqual(report["expanded_entrance_29"]["room"], "9000")
        self.assertEqual(report["exit_area"], "7A")

    def test_unwired_or_unauthored_candidates_are_refused(self):
        plateless = [subtype3(0xFAF, 12, 54), subtype3(0xFAF, 18, 54)]
        for kwargs, message in (
                ({"tags": {0x91: (0x00, 0)}}, "Room 91 header tags"),
                ({"tags": {0x92: (0x24, 0)}}, "Room 92 header tags"),
                ({"objects": {0x90: [subtype2(0x138, 10, 10)]}}, "bypass stair"),
                ({"objects": {0x91: plateless}}, "plate"),
                ({"objects": {0x92: [subtype3(0xF99, 4, 4)]}}, "chest"),
                ({"doors": {0x92: [(0x22, 0x00), (0x83, 0x18)]}}, "shutters"),
                ({"pots": ((12, 54, 0x0C), (18, 54, 0x01))}, "pot items"),
                ({"entrance": {"room": b"\x60\x00"}}, "entrance \\$29 room"),
                ({"entrance": {"ypos": b"\xd8\x0d"}}, "entrance \\$29 ypos")):
            with self.subTest(message=message), self.assertRaisesRegex(RuntimeError, message):
                lesson.validate_candidate(lesson_rom(**kwargs), SYMBOLS)
        rom = bytearray(lesson_rom())
        rom[offset(door.HOOK):offset(door.HOOK) + 4] = door.UNHOOKED_HOLES2
        with self.assertRaisesRegex(RuntimeError, "Unhooked candidate"):
            lesson.validate_candidate(bytes(rom), SYMBOLS)

    def test_warp_subclass_redirects_only_entrance_29_after_live_checks(self):
        live = {address: expected for address, expected in lesson.EXPANDED_ENTRANCE.values()}

        class Bus:
            def read_block(self, address, length):
                return live[address][:length]

        class Legacy:
            def __init__(self, bridge):
                self.b = bridge

            def _entrance_destination(self, entrance):
                return ("legacy", entrance["id"])

            def _exit_area(self, room):
                return 0x7A if room == 0x90 else None

            def r16(self, address):
                return 0x0060

        cheats = lesson.lesson_cheats(Legacy)(Bus())
        self.assertEqual(cheats._entrance_destination({"id": "0x29"}), (0x90, 0x7A))
        self.assertEqual(cheats.legacy_room, 0x0060)
        self.assertEqual(cheats._entrance_destination({"id": "0x2A"}), ("legacy", "0x2A"))
        live[0x0F8052] = b"\x60\x00"
        with self.assertRaisesRegex(RuntimeError, "Live expanded entrance \\$29 room"):
            cheats._entrance_destination({"id": "0x29"})

    def test_bootstrap_writes_are_allowlisted_and_body_admits_none(self):
        self.assertEqual({a for a, _, _ in lesson.BOOTSTRAP_WRITES},
                         {0x7EF350, 0x7E0202, 0x7E0303, 0x7E0304, 0x7EF36E})
        boot = lesson.Bootstrap(Args(), object(), None)
        for address, value in ((0x7EF36D, 0x48), (0x7EF36C, 0x50), (0x7E037B, 0x01), (0x7EF36E, 0x80),
                               (0x7E0020, 0xD8), (0x7EF3C8, 0x29)):
            with self.subTest(address=address), self.assertRaisesRegex(RuntimeError, "Undeclared bootstrap write"):
                boot.write(address, value, "probe")
        route = lesson.LessonRoute(Args(), object(), lesson.route_plan({}))
        with self.assertRaisesRegex(RuntimeError, "no memory writes"):
            route.write(0x7EF36E, 0x10)
        for buttons, count in (("B", 1), ("Start", 1), ("Up+A", 1), ("Right", 9), ("Right", 0)):
            with self.subTest(buttons=buttons, count=count), self.assertRaisesRegex(RuntimeError, "Undeclared"):
                route.advance(buttons, count)

    def test_source_never_uses_forbidden_runtime_controls(self):
        code = PATH.read_text()
        for token in ("SET_PC", "EXEC_LUA", "execute_lua", "load_state", "LOADSTATE", "save_state", "SAVESTATE",
                      "RESET", ".reset(", "LOADROM", "load_script", "CHEAT", "Popen", "os.kill", "set_cpu",
                      "SET_REG", "add_breakpoint", "resume(", "write_block"):
            with self.subTest(token=token):
                self.assertNotIn(token, code)
        body = next(ast.get_source_segment(code, node) for node in ast.parse(code).body
                    if isinstance(node, ast.ClassDef) and node.name == "LessonRoute")
        for token in ("write_memory", "_poke", "warp", "BOOTSTRAP_WRITES"):
            with self.subTest(body_token=token):
                self.assertNotIn(token, body)

    def test_movement_refuses_stalls_and_frame_overruns(self):
        def route(states):
            fixture = lesson.LessonRoute(Args(), object(), lesson.route_plan({}))
            fixture.last, queue = states[0], list(states[1:])
            fixture.advance = lambda b, n: setattr(fixture, "last", queue.pop(0) if queue else fixture.last) or fixture.last
            return fixture

        def at(lx):
            return {"module": 0x07, "submodule": 0, "indoors": 1, "room": 0x91, "area": 0, "x": lx, "y": 400,
                    "lx": lx, "ly": 400, "doorway": 0, "shutter": 1, "hp": 0x48}

        with self.assertRaisesRegex(RuntimeError, "no progress holding Right"):
            route([at(100)]).hold_until("Right", lambda s: s["lx"] >= 200, 600)
        route([at(100)]).hold_until("Right", lambda s: False, 600, blocked_ok=True)
        with self.assertRaisesRegex(RuntimeError, "missed target in 40 frames"):
            route([at(100 + i) for i in range(400)]).hold_until("Right", lambda s: s["lx"] >= 999, 40)
        for name, (low, high) in lesson.ROUTE_BOUNDS.items():
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, "outside"):
                lesson.route_plan({name: high + 1})

    def test_run_reads_the_starting_state_before_the_first_phase(self):
        low, save = bytearray(0x700), bytearray(0x90)
        low[0x10], low[0x1B], low[0xA0] = 0x07, 0x01, 0x90
        low[0x20:0x22], low[0x22:0x24] = (0x13D8).to_bytes(2, "little"), (0x0100).to_bytes(2, "little")
        low[0x202], low[0x303] = 0x0F, 0x12
        save[0x10], save[0x2D] = 0x01, 0x48
        memory = {0x7E0000: bytes(low), 0x7E0BF0: bytes(0x1F0), 0x7EF340: bytes(save), lesson.POTLIFT: b"\0\0"}
        with tempfile.TemporaryDirectory() as temporary:
            args = Args()
            args.output = Path(temporary)
            route = lesson.LessonRoute(args, object(), lesson.route_plan({}))
            route.block = lambda address, size: memory[address][:size]
            shots = []
            route.shot = shots.append
            route.run("preconditions")
        self.assertTrue(route.result["runtime_checks_passed"])
        self.assertEqual(route.result["completed_through"], "preconditions")
        self.assertIn("room 0090 area 00 local (256,472)", route.result["phases"][0]["start"])
        self.assertEqual(shots, ["start-room90"])
        self.assertEqual(route.result["writes"], [])

    def test_describe_is_source_only_and_default_refuses(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(lesson.main(["--describe"]), 0)
        plan = json.loads(out.getvalue())
        self.assertFalse(plan["native_executed"])
        self.assertEqual(plan["body"]["memory_writes"], [])
        self.assertEqual(len(plan["bootstrap"]["writes_after_landing"]), len(lesson.BOOTSTRAP_WRITES))
        self.assertNotIn("checkpoint d8-entrance", json.dumps(plan))
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "out"
            for argv in ([], ["--inspect", "--execute-fixtures"], ["--bootstrap", "--execute-fixtures"]):
                with self.subTest(argv=argv), self.assertRaisesRegex(RuntimeError, "exactly one of"):
                    lesson.main(argv + ["--output", str(output)])
            self.assertFalse(output.exists())

    def test_attach_refuses_identity_mismatch_before_output_or_bridge(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rom, sym, output = root / "c.sfc", root / "c.sym", root / "out"
            rom.write_bytes(lesson_rom())
            sym.write_text(SYMBOLS)
            base = ["--bootstrap", "--socket", "/tmp/mesen2-sky-lesson.sock", "--pid", "1",
                    "--owned-rom", str(rom), "--symbols", str(sym), "--client-root", str(root),
                    "--status-file", str(root / "s.status"), "--owner-file", str(root / "o"),
                    "--owner", "control", "--output", str(output),
                    "--symbols-sha256", lesson.digest(sym.read_bytes())]
            with self.assertRaisesRegex(RuntimeError, "ROM SHA256 mismatch"):
                lesson.main(base + ["--rom-sha256", "0" * 64])
            bad = list(base)
            bad[bad.index("--socket") + 1] = "/tmp/mesen2-oos-rc-play.sock"
            with self.assertRaisesRegex(RuntimeError, "task-owned private socket"):
                lesson.main(bad + ["--rom-sha256", lesson.digest(rom.read_bytes())])
            unwired = bytearray(rom.read_bytes())
            unwired[offset(door.HOOK):offset(door.HOOK) + 4] = door.UNHOOKED_HOLES2
            rom.write_bytes(bytes(unwired))
            with self.assertRaisesRegex(RuntimeError, "Unhooked candidate"):
                lesson.main(base + ["--rom-sha256", lesson.digest(bytes(unwired))])
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
