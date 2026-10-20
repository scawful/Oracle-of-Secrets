"""Offline safety controls for Tests/native/sky_somaria_lesson.py; no emulator or socket."""
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


def lesson_rom(tags=None, doors=None, objects=None, pots=None, ypos=b"\xd8\x13"):
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
    rom[lesson.HEADER_POINTER_PC:lesson.HEADER_POINTER_PC + 3] = (HEADERS - 0x400).to_bytes(3, "little")
    rom[lesson.HEADER_BANK_PC] = HEADERS >> 16
    at = STREAMS
    for room in (0x90, 0x91, 0x92):
        header = HEADERS + room * 16
        rom[offset(HEADERS - 0x400) + room * 2:offset(HEADERS - 0x400) + room * 2 + 2] = (header & 0xFFFF).to_bytes(2, "little")
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
    for name, (pc, expected) in lesson.ENTRANCE_FIELDS.items():
        rom[pc:pc + len(expected)] = ypos if name == "ypos" else expected
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
        self.assertEqual(report["exit_area"], "7A")
        self.assertEqual(report["pots"], [[12, 54, 0x0C], [18, 54, 0x0C]])

    def test_unwired_or_unauthored_candidates_are_refused(self):
        stair = subtype2(0x138, 10, 10)
        plateless = [subtype3(0xFAF, 12, 54), subtype3(0xFAF, 18, 54)]
        for kwargs, message in (
                ({"tags": {0x91: (0x00, 0)}}, "Room 91 header tags"),
                ({"tags": {0x92: (0x24, 0)}}, "Room 92 header tags"),
                ({"objects": {0x90: [stair]}}, "bypass stair"),
                ({"objects": {0x91: plateless}}, "plate"),
                ({"objects": {0x92: [subtype3(0xF99, 4, 4)]}}, "chest"),
                ({"doors": {0x92: [(0x22, 0x00), (0x83, 0x18)]}}, "shutters"),
                ({"pots": ((12, 54, 0x0C), (18, 54, 0x01))}, "pot items"),
                ({"ypos": b"\xd8\x0d"}, "Entrance \\$29 ypos")):
            with self.subTest(message=message), self.assertRaisesRegex(RuntimeError, message):
                lesson.validate_candidate(lesson_rom(**kwargs), SYMBOLS)
        rom = bytearray(lesson_rom())
        rom[offset(door.HOOK):offset(door.HOOK) + 4] = door.UNHOOKED_HOLES2
        with self.assertRaisesRegex(RuntimeError, "Unhooked candidate"):
            lesson.validate_candidate(bytes(rom), SYMBOLS)

    def test_route_overrides_stay_inside_recipe_bounds(self):
        self.assertEqual(lesson.route_plan({}), lesson.DEFAULT_ROUTE)
        self.assertEqual(lesson.route_plan({"cast_x": 420, "cast_y": None})["cast_x"], 420)
        for name, (low, high) in lesson.ROUTE_BOUNDS.items():
            for value in (low - 1, high + 1):
                with self.subTest(name=name, value=value), self.assertRaisesRegex(RuntimeError, "outside"):
                    lesson.route_plan({name: value})

    def test_state_uses_room_local_coordinates(self):
        low, anc = bytearray(0x700), bytearray(0x1F0)
        low[0xA0], low[0x22:0x24], low[0x20:0x22] = 0x91, (0x3A0).to_bytes(2, "little"), (0x1390).to_bytes(2, "little")
        anc[0x5A], anc[0x14], anc[0x28], anc[0x0A], anc[0x1E] = 0x2C, 0xA8, 0x03, 0xAF, 0x13
        state = lesson.state_from(bytes(low), bytes(anc), bytes(0x90), b"\x01\x00")
        self.assertEqual((state["lx"], state["ly"]), (416, 400))
        self.assertEqual((state["slots"][0]["lx"], state["slots"][0]["ly"]), (424, 431))
        self.assertEqual(lesson.block_slot(state), 0)
        self.assertEqual(state["potlift"], 1)

    def route(self, states):
        args = Args()
        route = lesson.LessonRoute(args, object(), lesson.route_plan({}))
        route.last = states[0]
        queue = list(states[1:])
        route.advance = lambda buttons, count: setattr(route, "last", queue.pop(0) if queue else route.last) or route.last
        return route

    def walking_state(self, lx):
        return {"module": 0x07, "submodule": 0, "indoors": 1, "room": 0x91, "area": 0, "x": lx, "y": 400,
                "lx": lx, "ly": 400, "doorway": 0, "shutter": 1, "hp": 0x48}

    def test_movement_refuses_stalls_and_frame_overruns(self):
        stuck = self.route([self.walking_state(100)])
        with self.assertRaisesRegex(RuntimeError, "no progress holding Right"):
            stuck.hold_until("Right", lambda s: s["lx"] >= 200, 600)
        self.route([self.walking_state(100)]).hold_until("Right", lambda s: False, 600, blocked_ok=True)
        moving = self.route([self.walking_state(100 + i) for i in range(400)])
        with self.assertRaisesRegex(RuntimeError, "missed target in 40 frames"):
            moving.hold_until("Right", lambda s: s["lx"] >= 999, 40)

    def test_body_refuses_writes_and_undeclared_buttons_before_the_socket(self):
        route = lesson.LessonRoute(Args(), object(), lesson.route_plan({}))
        with self.assertRaisesRegex(RuntimeError, "no memory writes"):
            route.write(0x7EF36E, 0x80)
        for buttons, count in (("B", 1), ("Select", 1), ("Up+A", 1), ("Right", 9), ("Right", 0)):
            with self.subTest(buttons=buttons, count=count), self.assertRaisesRegex(RuntimeError, "Undeclared"):
                route.advance(buttons, count)

    def test_source_never_uses_forbidden_runtime_controls(self):
        code = PATH.read_text()
        for token in ("write_memory", "write_block", "WRITEBLOCK", "SET_PC", "EXEC_LUA", "execute_lua",
                      "load_state", "LOADSTATE", "save_state", "SAVESTATE", "RESET", ".reset(", "LOADROM",
                      "load_script", "CHEAT", "Popen", "os.kill", "set_cpu", "SET_REG", "add_breakpoint",
                      "resume("):
            with self.subTest(token=token):
                self.assertNotIn(token, code)

    def test_describe_is_source_only_and_default_refuses(self):
        stream_out = io.StringIO()
        with redirect_stdout(stream_out):
            self.assertEqual(lesson.main(["--describe"]), 0)
        plan = json.loads(stream_out.getvalue())
        self.assertFalse(plan["native_executed"])
        self.assertEqual(plan["body"]["memory_writes"], [])
        self.assertEqual(plan["setup"]["checkpoint_chain"][-1], "d8-entrance")
        self.assertEqual(plan["phases"], list(lesson.PHASES))
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "out"
            with self.assertRaisesRegex(RuntimeError, "--execute-fixtures"):
                lesson.main(["--output", str(output)])
            with self.assertRaisesRegex(RuntimeError, "--execute-fixtures"):
                lesson.main(["--inspect", "--execute-fixtures", "--output", str(output)])
            self.assertFalse(output.exists())

    def test_execute_refuses_identity_mismatch_before_output_or_bridge(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rom, sym, output = root / "c.sfc", root / "c.sym", root / "out"
            rom.write_bytes(lesson_rom())
            sym.write_text(SYMBOLS)
            base = ["--execute-fixtures", "--socket", "/tmp/mesen2-sky-lesson.sock", "--pid", "1",
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
