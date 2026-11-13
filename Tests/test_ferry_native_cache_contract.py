"""Compare the ferry producer's wire layout with existing native cache fixtures.

Source/data checks only. No assembler, ROM write, CPU or native behavior claim.
"""
from pathlib import Path
import importlib.util
import re
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLACEMENTS = ROOT / "Data/overworld/kalyxo_boat_placements.asm"


def words_after(path, label):
    lines = path.read_text().split(label + ":", 1)[1].splitlines()
    words = []
    for line in lines:
        code = line.split(";", 1)[0].strip()
        if code.startswith("assert "):
            break
        if code.startswith("dw "):
            words.extend(int(v.strip()[1:], 16) for v in code[3:].split(","))
    return words


def emit_fixture(native_words):
    """Expand actual dw operands, with arguments from an existing native record."""
    source = PLACEMENTS.read_text()
    args, body = re.search(r"macro BoatNativeCache\(([^)]+)\)(.*?)endmacro", source, re.S).groups()
    # Native engine fields: area0, scroll4/6, position8/A, repeated areaC,
    # originE, triggers10/12, bounds14..22, graphics24/26, reserved/modifiers28..30.
    indexes = [0, 2, 3, 4, 5, 7, 8, 9, *range(10, 20)]
    values = dict(zip((a.strip() for a in args.split(",")), (native_words[i] for i in indexes)))
    actual = []
    for line in body.splitlines():
        if line.strip().startswith("dw "):
            for operand in line.strip()[3:].split(","):
                operand = operand.strip()
                actual.append(values[operand[1:-1]] if operand.startswith("<") else int(operand[1:], 16))
    return struct.pack("<" + "H" * len(actual), *actual)


class FerryNativeCacheContract(unittest.TestCase):
    def test_goron_native_cache_wire_equivalence(self):
        words = words_after(ROOT / "Overworld/goron_checkpoint.asm", "GoronCheckpoint_Cache")
        self.assertEqual(len(words), 25)
        self.assertEqual(emit_fixture(words), struct.pack("<25H", *words))

    def test_existing_special_soaring_cache_wire_equivalence(self):
        words = words_after(ROOT / "Items/special_soaring.asm", "SpecialSoaring_Caches")
        self.assertEqual(len(words), 50)
        for start in (0, 25):
            with self.subTest(area=words[start]):
                self.assertEqual(emit_fixture(words[start:start + 25]), struct.pack("<25H", *words[start:start + 25]))

    def test_no_current_geography_is_silently_bound(self):
        source = PLACEMENTS.read_text()
        self.assertRegex(source, r"(?m)^!KALYXO_BOAT_ENDPOINTS_BOUND = 0$")
        calls = re.findall(r"^  %BoatNativeCache\(([^)]+)\)", source, re.M)
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertEqual([v.strip() for v in call.split(",")], ["$FFFF"] * 18)
        for name in ("DocksFacing", "IslandFacing", "DocksOpenTile", "IslandOpenTile", "DocksWaterTile", "IslandWaterTile"):
            self.assertRegex(source, rf"(?m)^!Boat_{name} = \$FFFF$")


def recovery_machine(source=None, endpoint=0, changes=None, resolved_index=0x04C0):
    """Execute actual recovery/admission/clear ASM through the existing model.

    Only the resident-index calculation and native drawing have ABI stubs;
    these tests prove recovery admission and captured-word publication intent,
    not arithmetic CPU behavior, stripe upload, collision or native rendering.
    """
    spec = importlib.util.spec_from_file_location("ferry_cart_model", ROOT / "Tests/test_cart_shutter_local.py")
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    source = source or (ROOT / "Overworld/kalyxo_boat.asm").read_text()
    symbols = {}
    cursor = 0x7E1E70
    for name, size in re.findall(r"(?m)^(\w+):\s+skip (\d+)", (ROOT / "Core/symbols.asm").read_text().split("base off", 1)[0]):
        symbols[name] = cursor
        cursor += int(size)
    symbols["SavedWorld"] = int(re.search(r"(?m)^SavedWorld\s*=\s*\$([\dA-Fa-f]+)", (ROOT / "Core/sram.asm").read_text())[1], 16)
    symbols["!Boat_Magic"] = int(re.search(r"!Boat_Magic = \$([\dA-Fa-f]+)", (ROOT / "Core/symbols.asm").read_text())[1], 16)
    # Synthetic bound ROM records, separate from the unbound production data.
    symbols.update(Boat_OpenTiles=0x3AD900, Boat_ClosedTiles=0x3AD904,
                   Boat_CacheOffsets=0x3AD908, Boat_Caches=0x3ADA00)

    def lines(body, scope):
        body = re.sub(r"(?<![\w])\.(\w+)", rf".{scope}_\1", body)
        return [part.strip() for line in body.splitlines()
                for part in line.split(";", 1)[0].split(" : ") if part.strip()]

    body = source.split("Boat_TryBoard:\n{", 1)[1]
    start = body.index("  REP #$20")
    end = body.index("  .no_stale_scene") + len("  .no_stale_scene")
    program = lines(body[start:end], "entry") + ["RTL"]
    for name in ("Boat_RecoverInterrupted", "Boat_CanRecoverPlank", "Boat_Clear"):
        if name + ":\n{" in source:
            body = source.split(name + ":\n{", 1)[1].split("\n}", 1)[0]
            program += ["." + name] + lines(body, name)
    program += [".Boat_RecoveryIndex", "LDA.w #$" + f"{resolved_index:04X}", "RTS"]
    program += [".Boat_RestorePlank", "REP #$30", "LDA.l Boat_PlankIndex", "TAX",
                "LDA.l Boat_PlankTile", "STA.l $7E2000, X", "SEP #$30", "RTS"]
    lowered = []
    for line in program:
        line = re.sub(r"JSR (Boat_\w+)", r"JSR .\1", line)
        for name, address in sorted(symbols.items(), key=lambda p: -len(p[0])):
            line = re.sub(r"(?<!\w)" + re.escape(name) + r"(?!\w)", f"${address:06X}", line)
        lowered.append(line)
    code, labels = model.base.parse(lowered)
    memory = {0x1B: 0, 0x10: 9 if endpoint == 0 else 11,
              0x8A: 0x30 if endpoint == 0 else 0x98}
    values = {"Boat_Marker": symbols["!Boat_Magic"], "Boat_State": 2,
              "Boat_Endpoint": endpoint, "Boat_SourceModule": memory[0x10],
              "Boat_PlankChanged": 1, "Boat_PlankIndex": 0x04C0,
              "Boat_PlankTile": 0x0FC8}
    byte_fields = {"Boat_State", "Boat_Endpoint", "Boat_SourceModule", "Boat_PlankChanged"}
    for name, value in values.items():
        if name in byte_fields:
            memory[symbols[name]] = value
        else:
            model.word(memory, symbols[name], value)
    for address, value in ((symbols["Boat_OpenTiles"], 0x0FC8), (symbols["Boat_OpenTiles"] + 2, 0x0FC8),
                           (symbols["Boat_ClosedTiles"], 0x02CD), (symbols["Boat_ClosedTiles"] + 2, 0x02CD),
                           (symbols["Boat_CacheOffsets"], 0), (symbols["Boat_CacheOffsets"] + 2, 0x32),
                           (symbols["Boat_Caches"], 0x30), (symbols["Boat_Caches"] + 0x32, 0x98),
                           (0x7E24C0, 0x02CD)):
        model.word(memory, address, value)
    for name, value in (changes or {}).items():
        address = symbols.get(name, name)
        if name in byte_fields or address in (0x1B, 0x10, 0x8A, symbols["SavedWorld"]):
            memory[address] = value
        else:
            model.word(memory, address, value)
    machine = model.Machine(memory, p=0x20)
    assert machine.run(code, labels) == "RTL"
    return machine, symbols


class FerryInterruptedPlankRecovery(unittest.TestCase):
    def test_both_source_endpoints_restore_closed_plank_before_clearing(self):
        for endpoint in (0, 2):
            with self.subTest(endpoint=endpoint):
                machine, symbols = recovery_machine(endpoint=endpoint)
                self.assertEqual(machine.read(0x7E24C0, True), 0x0FC8)
                self.assertEqual(machine.read(symbols["Boat_Marker"], True), 0)
                self.assertEqual((machine.sp, machine.p & 0x30), (0x01FB, 0))

    def test_foreign_context_and_changed_preimages_never_publish_tile(self):
        refusals = [{0x1B: 1}, {"SavedWorld": 0x40}, {0x10: 11},
                    {0x10: 8, "Boat_SourceModule": 8}, {0x8A: 0x31},
                    {"Boat_Endpoint": 1}, {"Boat_Endpoint": 4},
                    {"Boat_PlankChanged": 0}, {"Boat_PlankChanged": 2},
                    {"Boat_State": 1}, {"Boat_State": 3}, {"Boat_State": 4},
                    {"Boat_PlankTile": 0x0FC9}, {0x7E24C0: 0x0350},
                    {0x7E24C0: 0x0FC8}, {"Boat_Marker": 0}]
        for changes in refusals:
            with self.subTest(changes=changes):
                machine, _ = recovery_machine(changes=changes)
                self.assertFalse(any(0x7E2000 <= address < 0x7E4000 for address in machine.writes))

    def test_reloaded_transform_stale_or_invalid_index_refuses(self):
        for captured, current in ((0x04C0, 0x04C2), (0x04C1, 0x04C1), (0x2000, 0x2000)):
            with self.subTest(captured=captured, current=current):
                machine, _ = recovery_machine(changes={"Boat_PlankIndex": captured}, resolved_index=current)
                self.assertFalse(any(0x7E2000 <= address < 0x7E4000 for address in machine.writes))


if __name__ == "__main__":
    unittest.main()
