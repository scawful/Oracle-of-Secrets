"""Source-model controls for RoomTag_SomariaSocketDoor (room tag $24).

A minimal 65816-subset interpreter executes the routine text from
Dungeons/custom_tag.asm against a WRAM model. It checks the source contract
only; it is not CPU or native emulator proof. The tag $24 base-ROM census is
exercised on synthetic fixtures; run Tests/tag24_base_census.py for a real ROM.
"""
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
from pathlib import Path
import json
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Dungeons" / "custom_tag.asm"
ROUTINE = "RoomTag_SomariaSocketDoor"
RETURN_ADDRESS = 0x01CC5A

CENSUS_PATH = Path(__file__).parent / "tag24_base_census.py"
CENSUS_SPEC = importlib.util.spec_from_file_location("tag24_base_census", CENSUS_PATH)
census = importlib.util.module_from_spec(CENSUS_SPEC)
CENSUS_SPEC.loader.exec_module(census)

sys.path.insert(0, str(ROOT / "Scripts" / "Generate"))
from asm_source import _load_global_defines  # noqa: E402
from generate_hack_manifest import scan_room_tags  # noqa: E402
from generate_hooks_json import scan_hooks  # noqa: E402

M_FLAG = 0x20
X_FLAG = 0x10

QUALIFYING_SLOT = {0x0C4A: 0x2C, 0x0394: 0x00, 0x03C5: 0x00, 0x0380: 0x00,
                   0x03DB: 0x04, 0x029E: 0x00}
DOOR_WRITES = {0x0468, 0x0469, 0x068E, 0x068F, 0x0690, 0x0691, 0x0011}
ALLOWED_OPERANDS = {0x001B, 0x0646, 0x0308, 0x03F4, 0x0C4A, 0x0394, 0x03C5,
                    0x0380, 0x03DB, 0x029E, 0x0468, 0x068E, 0x0690, 0x012F, 0x0011}
ALLOCATION_START = 0x2CFD00
ALLOCATION_END = 0x2CFE00
LEGACY_HOOK_ORGS = ["org $01CC18 : JML CustomTag",
                    "org $01CC10 : JML RoomTag_MinishShutterDoor",
                    "org $01CC04 : JML RoomTag_MinishSwitch"]
GATEWAY_ADDRESS = 0x01CC89
GATEWAY_ORG = f"org ${GATEWAY_ADDRESS:06X} : JML {ROUTINE}"
GATEWAY_BOUND = "assert pc() == $01CC8D"
TAG24_VECTOR = 0x01C27D + 0x24 * 2


def code_lines(text):
    return [line.split(";", 1)[0].strip() for line in text.splitlines()]


def handler_entry_hooks(manifest):
    """Fixed-allocation metadata is allowed; an entry branch is activation."""
    entries = []
    for hook in manifest.get("hooks", []):
        target = (hook.get("target") or "").removeprefix("Oracle_")
        try:
            address = int(target.replace("$", "0x"), 0)
        except ValueError:
            address = None
        if (hook.get("kind", "").lower() in {"jmp", "jml", "jsr", "jsl"}
                and (target == ROUTINE or address == ALLOCATION_START)):
            entries.append(hook)
    return entries


def assembled_size(program):
    size = 0
    for mnemonic, suffix, operand in program:
        if mnemonic in ("SEP", "REP"):
            size += 2
        elif mnemonic == "DEX":
            size += 1
        elif mnemonic in ("BEQ", "BNE", "BMI", "BPL", "BRA"):
            size += 2
        elif mnemonic == "JML":
            size += 4
        else:
            size += 1 + {"b": 1, "w": 2}[suffix]
    return size


def routine_lines():
    lines = SOURCE.read_text().splitlines()
    start = lines.index(f"{ROUTINE}:")
    body = []
    for line in lines[start + 1:]:
        if line == "}":
            return body
        code = line.split(";", 1)[0].strip()
        if code in ("", "{"):
            continue
        body.extend(part.strip() for part in code.split(" : "))
    raise AssertionError("routine block is not closed")


def parse(lines):
    program, labels = [], {}
    for text in lines:
        if re.fullmatch(r"\.\w+", text):
            labels[text] = len(program)
            continue
        match = re.fullmatch(r"([A-Z]{3})(?:\.([bwl]))?(?:\s+(.*))?", text)
        if not match:
            raise AssertionError(f"unparsed line: {text!r}")
        program.append((match.group(1), match.group(2), (match.group(3) or "").strip()))
    return program, labels


def address_operands(program):
    found = set()
    for _, _, operand in program:
        match = re.fullmatch(r"\$([0-9A-F]+)(?:,\s*X)?", operand)
        if match:
            found.add(int(match.group(1), 16))
    return found


class Machine:
    def __init__(self, memory, p=M_FLAG | X_FLAG, a=0xBEEF, x=0x0006, y=0x1234):
        self.memory = dict(memory)
        self.p, self.a, self.x, self.y, self.sp = p, a, x, y, 0x01FB
        self.n = self.z = self.c = self.v = False
        self.reads, self.writes = [], {}
        self._normalize_index()

    def _normalize_index(self):
        if self.p & X_FLAG:
            self.x &= 0xFF
            self.y &= 0xFF

    def read(self, address, wide):
        self.reads.append(address)
        value = self.memory.get(address, 0)
        if wide:
            self.reads.append(address + 1)
            value |= self.memory.get(address + 1, 0) << 8
        return value

    def write(self, address, value, wide):
        for offset in range(2 if wide else 1):
            byte = (value >> (8 * offset)) & 0xFF
            self.memory[address + offset] = byte
            self.writes[address + offset] = byte

    def flags_nz(self, value, wide):
        self.z = value == 0
        self.n = bool(value & (0x8000 if wide else 0x80))

    def m16(self):
        return not self.p & M_FLAG

    def x16(self):
        return not self.p & X_FLAG

    def check_immediate(self, suffix, operand, wide):
        digits = len(operand) - 2
        size = {"b": 1, "w": 2}.get(suffix, 1 if digits <= 2 else 2)
        if size != (2 if wide else 1):
            raise AssertionError(f"immediate {operand} assembles {size} byte(s) "
                                 f"but runtime width is {2 if wide else 1}")
        return int(operand[2:], 16)

    def effective(self, operand):
        match = re.fullmatch(r"\$([0-9A-F]+)(,\s*X)?", operand)
        if not match:
            raise AssertionError(f"unsupported operand {operand!r}")
        address = int(match.group(1), 16)
        if match.group(2):
            address += self.x
        return address

    def load(self, suffix, operand, wide):
        if operand.startswith("#"):
            return self.check_immediate(suffix, operand, wide)
        return self.read(self.effective(operand), wide)

    def compare(self, register, value, wide):
        mask = 0xFFFF if wide else 0xFF
        result = (register - value) & mask
        self.c = (register & mask) >= value
        self.flags_nz(result, wide)

    def run(self, program, labels, limit=500):
        pc = 0
        for _ in range(limit):
            mnemonic, suffix, operand = program[pc]
            pc += 1
            if mnemonic == "SEP":
                self.p |= int(operand[2:], 16)
                self._normalize_index()
            elif mnemonic == "REP":
                self.p &= ~int(operand[2:], 16)
            elif mnemonic == "LDA":
                value = self.load(suffix, operand, self.m16())
                self.a = value if self.m16() else (self.a & 0xFF00) | value
                self.flags_nz(value, self.m16())
            elif mnemonic == "LDX":
                self.x = self.load(suffix, operand, self.x16())
                self.flags_nz(self.x, self.x16())
            elif mnemonic == "CMP":
                accumulator = self.a if self.m16() else self.a & 0xFF
                self.compare(accumulator, self.load(suffix, operand, self.m16()), self.m16())
            elif mnemonic == "CPX":
                self.compare(self.x, self.load(suffix, operand, self.x16()), self.x16())
            elif mnemonic == "BIT":
                wide = self.m16()
                value = self.read(self.effective(operand), wide)
                top = 0x8000 if wide else 0x80
                self.n, self.v = bool(value & top), bool(value & (top >> 1))
                self.z = (self.a & (0xFFFF if wide else 0xFF) & value) == 0
            elif mnemonic == "DEX":
                self.x = (self.x - 1) & (0xFFFF if self.x16() else 0xFF)
                self.flags_nz(self.x, self.x16())
            elif mnemonic == "STA":
                self.write(self.effective(operand), self.a, self.m16())
            elif mnemonic == "STX":
                self.write(self.effective(operand), self.x, self.x16())
            elif mnemonic == "STZ":
                self.write(self.effective(operand), 0, self.m16())
            elif mnemonic in ("BEQ", "BNE", "BMI", "BPL", "BRA"):
                taken = {"BEQ": self.z, "BNE": not self.z, "BMI": self.n,
                         "BPL": not self.n, "BRA": True}[mnemonic]
                if taken:
                    pc = labels[operand]
            elif mnemonic == "JML":
                return operand
            else:
                raise AssertionError(f"mnemonic {mnemonic} is outside the modeled contract")
        raise AssertionError("step limit reached")


def room(door=0x0001, extra=None):
    memory = {0x001B: 0x01, 0x0646: 0x00, 0x0308: 0x00, 0x03F4: 0x00,
              0x0468: door & 0xFF, 0x0469: door >> 8, 0x000E: 0x01,
              0x00AE: 0x24, 0x00AF: 0x16, 0x068E: 0x34, 0x068F: 0x12,
              0x0690: 0x78, 0x0691: 0x56, 0x0011: 0x00, 0x012F: 0x00}
    memory.update(extra or {})
    return memory


def with_block(memory, slot=0, **slot_overrides):
    fields = dict(QUALIFYING_SLOT)
    fields.update({int(key[1:], 16): value for key, value in slot_overrides.items()})
    for base, value in fields.items():
        memory[base + slot] = value
    memory[0x0646] = 0x01
    return memory


def census_rom(tags=None, state="base"):
    """Headerless LoROM fixture: header table at $22:8000, headers at $22:8300.

    Every header byte other than tag1/tag2 is $24, so a wrong offset reports users.
    """
    data = bytearray(0x118000)
    data[0xB5DC:0xB5E0] = bytes.fromhex("bf008022")
    data[0xB5E6:0xB5E8] = bytes.fromhex("a922")
    for room in range(census.ROOM_COUNT):
        header = 0x8300 + room * 14
        data[0x110000 + room * 2:0x110002 + room * 2] = header.to_bytes(2, "little")
        pc = 0x110000 + header - 0x8000
        data[pc:pc + 14] = bytes([0x24]) * 14
        data[pc + 5], data[pc + 6] = (tags or {}).get(room, (0x00, 0x00))
    data[0xC2C5:0xC2C7] = bytes.fromhex("89cc")
    data[0xCC89:0xCC95] = census.EXPECTED_BODY[state]
    return data


class SomariaSocketDoorModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lines = routine_lines()
        cls.program, cls.labels = parse(cls.lines)

    def execute(self, memory, **registers):
        machine = Machine(memory, **registers)
        target = machine.run(self.program, self.labels)
        self.assertEqual(target, "RoomTag_Return")
        self.assertEqual(machine.p & (M_FLAG | X_FLAG), M_FLAG | X_FLAG)
        self.assertEqual(machine.sp, 0x01FB)
        return machine

    def assert_opened(self, machine):
        self.assertEqual(machine.writes, {0x0468: 0, 0x0469: 0, 0x068E: 0, 0x068F: 0,
                                          0x0690: 0, 0x0691: 0, 0x012F: 0x25, 0x0011: 0x05})

    def assert_closed_now(self, machine):
        self.assertEqual(machine.writes, {0x0468: 1, 0x0469: 0, 0x068E: 0, 0x068F: 0,
                                          0x0690: 0, 0x0691: 0, 0x0011: 0x05})

    def test_return_constant_and_single_dispatcher_gateway(self):
        text = SOURCE.read_text()
        self.assertRegex(text, r"(?m)^RoomTag_Return = \$01CC5A$")
        self.assertEqual(RETURN_ADDRESS, 0x01CC5A)
        users = []
        for path in ROOT.rglob("*.asm"):
            for line in path.read_text(errors="replace").splitlines():
                code = line.split(";", 1)[0].strip()
                if ROUTINE in code:
                    users.append((path.relative_to(ROOT).as_posix(), code))
        self.assertEqual(users, [("Dungeons/custom_tag.asm", GATEWAY_ORG),
                                 ("Dungeons/custom_tag.asm", f"{ROUTINE}:")])
        for path in ROOT.rglob("hooks.json"):
            entries = handler_entry_hooks(json.loads(path.read_text()))
            self.assertLessEqual(len(entries), 1, str(path))
            for entry in entries:
                self.assertEqual(int(entry["address"], 0), GATEWAY_ADDRESS, str(path))

    def test_gateway_guards_vector_and_whole_native_body(self):
        lines = code_lines(SOURCE.read_text())
        org = lines.index(GATEWAY_ORG)
        self.assertEqual(lines[org + 1], GATEWAY_BOUND)
        self.assertEqual(GATEWAY_ADDRESS + 4, int(GATEWAY_BOUND.rsplit("$", 1)[1], 16))
        guards = {}
        for index, line in enumerate(lines):
            match = re.fullmatch(r'assert read([124])\(\$([0-9A-F]{6})\) == \$([0-9A-F]+), ".+"',
                                 line)
            if match and index < org:
                self.assertLess(index, org, line)
                guards[int(match.group(2), 16)] = (int(match.group(1)), int(match.group(3), 16))
        self.assertEqual(TAG24_VECTOR, 0x01C2C5)
        body = census.HOLES2_BODY
        self.assertEqual(body, bytes.fromhex("c23020cccd90f6a0050080d9"))
        expected = {TAG24_VECTOR: (2, census.HOLES2_VECTOR)}
        for offset in range(0, len(body), 4):
            expected[GATEWAY_ADDRESS + offset] = (4, int.from_bytes(body[offset:offset + 4],
                                                                    "little"))
        self.assertEqual(guards, expected)
        self.assertEqual(census.GATEWAY, b"\x5C" + ALLOCATION_START.to_bytes(3, "little"))

    def test_generators_register_exactly_one_tag24_gateway(self):
        hooks = [{"address": f"0x{entry.address:06X}", "name": entry.name, "kind": entry.kind,
                  "target": entry.target, "module": entry.module,
                  "expected_m": entry.expected_m, "expected_x": entry.expected_x,
                  "expected_exit_m": entry.expected_exit_m,
                  "expected_exit_x": entry.expected_exit_x,
                  "protected_size": entry.protected_size}
                 for entry in scan_hooks(ROOT)]
        self.assertEqual(handler_entry_hooks({"hooks": hooks}), [{
            "address": "0x01CC89", "name": ROUTINE, "kind": "jml", "target": ROUTINE,
            "module": "Dungeons", "expected_m": 8, "expected_x": 8,
            "expected_exit_m": 8, "expected_exit_x": 8, "protected_size": 4}])
        defines = _load_global_defines(ROOT)
        vectors = bytearray(0xC2FD)
        vectors[0xC2C5:0xC2C7] = bytes.fromhex("89cc")
        for rom_data in (None, bytes(vectors)):
            with self.subTest(source_only=rom_data is None):
                tags = [tag for tag in scan_room_tags(ROOT, defines, rom_data=rom_data)
                        if tag["tag_id"] == "0x24" or tag["address"] == "0x01CC89"]
                self.assertEqual([(tag["tag_id"], tag["address"], tag["name"], tag["enabled"])
                                  for tag in tags], [("0x24", "0x01CC89", ROUTINE, True)])
        vectors[0xC2C5:0xC2C7] = bytes.fromhex("8acc")
        self.assertFalse([tag for tag in scan_room_tags(ROOT, defines, rom_data=bytes(vectors))
                          if tag["address"] == "0x01CC89"])

    def test_census_resolves_relocated_headers_with_no_tag24_users(self):
        report = census.census(bytes(census_rom()))
        self.assertEqual(report["errors"], [])
        self.assertEqual((report["room_count"], report["tag24_users"]), (296, []))
        self.assertEqual((report["header_table_snes"], report["header_table_pc"],
                          report["header_bank"]), ("0x228000", "0x110000", "0x22"))
        self.assertEqual((report["vector"], report["holes2_bytes"]),
                         ("0xCC89", "c23020cccd90f6a0050080d9"))

    def test_census_reports_tag24_in_either_header_slot(self):
        report = census.census(bytes(census_rom({0x091: (0x24, 0x00), 0x127: (0x16, 0x24)})))
        self.assertEqual(report["tag24_users"], [{"room": "0x091", "slot": "tag1"},
                                                 {"room": "0x127", "slot": "tag2"}])
        self.assertEqual(report["room_count"], 296)
        self.assertEqual(len(report["errors"]), 1)

    def test_census_rejects_changed_vector_body_or_resolver(self):
        cases = {"vector": (0xC2C5, 0x8A), "resolver opcode": (0xB5DC, 0xAF)}
        cases.update({f"body byte {index}": (0xCC89 + index, census.HOLES2_BODY[index] ^ 0xFF)
                      for index in range(len(census.HOLES2_BODY))})
        for name, (pc, value) in cases.items():
            with self.subTest(name=name):
                data = census_rom()
                data[pc] = value
                self.assertTrue(census.census(bytes(data))["errors"])
        for name, data in {"copier header": bytes(0x200) + bytes(census_rom()),
                           "truncated bank operand": bytes(census_rom())[:0xB5E7],
                           "truncated header bank": bytes(census_rom())[:0x110000]}.items():
            with self.subTest(name=name):
                self.assertTrue(census.census(data)["errors"])

    def test_census_patched_state_requires_gateway_and_untouched_tail(self):
        patched = census_rom(state="patched")
        self.assertEqual(census.census(bytes(patched), "patched")["errors"], [])
        self.assertTrue(census.census(bytes(patched))["errors"])
        self.assertTrue(census.census(bytes(census_rom()), "patched")["errors"])
        extended = bytes(patched) + bytes(2_150_714 - len(patched))
        self.assertNotEqual(len(extended) % 0x8000, 0)
        self.assertEqual(extended[0xC2C5:0xC2C7], bytes.fromhex("89cc"))
        self.assertEqual(extended[0xCC89:0xCC95], census.GATEWAY + census.HOLES2_BODY[4:])
        report = census.census(extended, "patched")
        self.assertEqual(report["errors"], [])
        self.assertEqual((report["room_count"], report["tag24_users"]), (296, []))
        for index in range(len(census.HOLES2_BODY)):
            with self.subTest(index=index):
                data = bytearray(patched)
                data[0xCC89 + index] ^= 0xFF
                self.assertTrue(census.census(bytes(data), "patched")["errors"])

    def test_census_file_audit_records_hashes_and_never_writes(self):
        with tempfile.TemporaryDirectory() as temporary:
            rom = Path(temporary) / "base.sfc"
            rom.write_bytes(bytes(census_rom()))
            digest = hashlib.sha256(rom.read_bytes()).hexdigest()
            report = census.audit_file(rom, digest.upper())
            self.assertTrue(report["ok"], report["errors"])
            self.assertEqual((report["sha256_before"], report["sha256_after"]), (digest, digest))
            wrong = census.audit_file(rom, "0" * 64)
            self.assertFalse(wrong["ok"])
            self.assertIn("ROM SHA-256 does not match --expected-sha256", wrong["errors"])
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(census.main(["--rom", str(rom), "--expected-sha256", digest]), 0)
                self.assertEqual(census.main(["--rom", str(rom), "--state", "patched"]), 1)
            self.assertIn('"ok": true', output.getvalue())
            self.assertEqual(hashlib.sha256(rom.read_bytes()).hexdigest(), digest)

    def test_manifest_allocation_is_allowed_but_handler_branches_are_not(self):
        allocation = {"address": "0x2CFD00", "name": ROUTINE, "kind": "patch"}
        self.assertEqual(handler_entry_hooks({"hooks": [allocation]}), [])
        for kind in ("jmp", "jml", "jsr", "jsl"):
            for target in (ROUTINE, "Oracle_" + ROUTINE, "$2CFD00", "0x2CFD00"):
                with self.subTest(kind=kind, target=target):
                    entry = {"address": "0x01CC89", "kind": kind, "target": target}
                    self.assertEqual(handler_entry_hooks({"hooks": [allocation, entry]}), [entry])

    def test_fixed_tail_allocation_is_not_a_hook(self):
        lines = code_lines(SOURCE.read_text())
        label = lines.index(f"{ROUTINE}:")
        self.assertEqual(lines[label - 2:label], ["pushpc", f"org ${ALLOCATION_START:06X}"])
        orgs = [line for line in lines if line.startswith("org ")]
        self.assertEqual(orgs, LEGACY_HOOK_ORGS + [GATEWAY_ORG, "org $08E731", "org $09AC81", "org $088A26", "org $2CFC00",
                                                f"org ${ALLOCATION_START:06X}"])
        self.assertEqual(ALLOCATION_START >> 16, 0x2C)
        collision = (ROOT / "Dungeons" / "Collision" / "custom_collision.asm").read_text()
        guard = (ROOT / "Core" / "patches.asm").read_text()
        self.assertIn(f"org ${ALLOCATION_END:06X}", code_lines(collision))
        self.assertIn("org $2CFF00", code_lines(guard))

    def test_pc_stack_balance_and_end_bound(self):
        lines = [line for line in code_lines(SOURCE.read_text()) if line]
        directives = [line for line in lines if line in ("pushpc", "pullpc")]
        self.assertEqual(directives, ["pullpc", "pushpc", "pullpc", "pushpc", "pullpc", "pushpc"])
        self.assertEqual(lines[-1], "pushpc")
        start = lines.index(f"{ROUTINE}:")
        close = lines.index("}", start)
        self.assertEqual(lines[close + 1], "SomariaSocket_CulledBlock:")
        cull_close = lines.index("}", close + 1)
        self.assertEqual(lines[cull_close + 1:cull_close + 3],
                         [f"assert pc() <= ${ALLOCATION_END:06X}", "pullpc"])
        size = assembled_size(self.program)
        self.assertEqual(size, 111)
        self.assertLessEqual(ALLOCATION_START + size, ALLOCATION_END)

    def test_routine_has_no_stack_or_subroutine_instructions(self):
        mnemonics = {mnemonic for mnemonic, _, _ in self.program}
        self.assertFalse(mnemonics & {"PHA", "PHX", "PHY", "PHP", "PHB", "PHD", "PHK",
                                      "PLA", "PLX", "PLY", "PLP", "PLB", "PLD",
                                      "JSR", "JSL", "RTS", "RTL", "RTI", "PEA", "PEI"})
        exits = [operand for mnemonic, _, operand in self.program if mnemonic == "JML"]
        self.assertEqual(exits, ["RoomTag_Return"])

    def test_static_operands_stay_inside_footprint(self):
        self.assertEqual(address_operands(self.program) - ALLOWED_OPERANDS, set())

    def test_qualifying_block_opens_closed_door_with_sfx(self):
        self.assert_opened(self.execute(with_block(room(door=1))))

    def test_qualifying_block_on_open_door_writes_nothing(self):
        self.assertEqual(self.execute(with_block(room(door=0))).writes, {})

    def test_no_block_closes_open_door_without_sfx(self):
        self.assert_closed_now(self.execute(room(door=0)))

    def test_no_block_on_closed_door_writes_nothing(self):
        self.assertEqual(self.execute(room(door=1)).writes, {})

    def test_transition_sequence_is_reversible(self):
        machine = self.execute(with_block(room(door=1)))
        self.assert_opened(machine)
        memory = machine.memory
        memory[0x0011] = 0x00
        machine = self.execute(memory)
        self.assertEqual(machine.writes, {})
        memory = machine.memory
        memory[0x0C4A] = 0x00  # pit deletion frees the slot and leaves SOMBTN set
        self.assertEqual(memory[0x0646], 0x01)
        machine = self.execute(memory)
        self.assert_closed_now(machine)
        memory = machine.memory
        memory[0x0011] = 0x00
        self.assert_opened(self.execute(with_block(memory)))

    def test_altitude_ff_counts_as_grounded(self):
        self.assert_opened(self.execute(with_block(room(door=1), x029E=0xFF)))

    def test_each_front_slot_qualifies_and_slot_five_does_not(self):
        for slot in range(5):
            with self.subTest(slot=slot):
                self.assert_opened(self.execute(with_block(room(door=1), slot=slot)))
        self.assertEqual(self.execute(with_block(room(door=1), slot=5)).writes, {})

    def test_stale_or_invalid_signal_is_rejected(self):
        cases = {
            "slot freed by pit deletion": {"x0C4A": 0x00},
            "slot became exploding block": {"x0C4A": 0x2D},
            "spawn delay running": {"x0394": 0x03},
            "bouncing": {"x03C5": 0x01},
            "lifted or carried": {"x0380": 0x03},
            "only three probe points on switch": {"x03DB": 0x03},
            "airborne": {"x029E": 0x10},
        }
        for name, slot_fields in cases.items():
            with self.subTest(name=name):
                self.assert_closed_now(self.execute(with_block(room(door=0), **slot_fields)))
        globals_cases = {"outdoors": {0x001B: 0x00}, "Link carrying": {0x0308: 0x80},
                         "transit lines": {0x03F4: 0x02}, "SOMBTN clear": {0x0646: 0x00}}
        for name, fields in globals_cases.items():
            with self.subTest(name=name):
                memory = with_block(room(door=0))
                memory.update(fields)
                self.assert_closed_now(self.execute(memory))

    def test_stale_slot_does_not_mask_live_slot(self):
        memory = with_block(room(door=1), slot=4, x03DB=0x00)
        self.assert_opened(self.execute(with_block(memory, slot=1)))

    def test_incompatible_pressure_sources_never_open(self):
        memory = room(door=0, extra={
            0x0642: 0x01,                          # sprite, ice block, follower tag
            0x0478: 0x02, 0x0500: 0x05, 0x0501: 0x00,
            0x0466: 0x00, 0x0467: 0x00,            # push block on switch latch
            0x02E4: 0x00, 0x004D: 0x00,            # Link free to press a floor switch
            0x0020: 0x40, 0x0022: 0x80,            # Link coordinates
            0x7EF350: 0x01,                        # Somaria owned in inventory
        })
        machine = self.execute(memory)
        self.assert_closed_now(machine)
        forbidden = {0x0642, 0x0466, 0x0467, 0x0478, 0x0479, 0x02E4, 0x004D,
                     0x0020, 0x0021, 0x0022, 0x0023, 0x7EF350}
        forbidden |= set(range(0x0500, 0x0560))
        self.assertEqual(set(machine.reads) & forbidden, set())

    def test_door_compare_is_sixteen_bit(self):
        machine = self.execute(with_block(room(door=0x0100)))
        self.assert_opened(machine)

    def test_abi_normalizes_widths_and_preserves_dispatcher_state(self):
        for p in (0x00, M_FLAG, X_FLAG, M_FLAG | X_FLAG):
            for memory in (with_block(room(door=1)), room(door=0), room(door=1)):
                with self.subTest(p=p, door=memory[0x0468]):
                    machine = self.execute(memory, p=p, y=0x0042)
                    self.assertEqual(machine.y, 0x0042)
                    for address in (0x000E, 0x00AE, 0x00AF):
                        self.assertEqual(machine.memory[address], memory[address])
                        self.assertNotIn(address, machine.writes)
                    self.assertLessEqual(set(machine.writes), DOOR_WRITES | {0x012F})


if __name__ == "__main__":
    unittest.main()
