"""Guard and isolation controls for Scripts/Rooms/sky_d8_room_writer.py.

Runs on a synthetic 2 MiB image that carries the recipe preimages at their real
offsets plus filler rooms, with pins computed for that image. No real ROM is
read or written; file-guard cases use temporary directories only.
"""
from contextlib import redirect_stdout
import copy
import errno
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sky_d8_room_writer", ROOT / "Scripts" / "Rooms" / "sky_d8_room_writer.py")
W = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = W
SPEC.loader.exec_module(W)

hx = W.hx
MIRROR = b"\x00\x00\x80"
CHEST_ROOMS = (0x10, 0x11, 0x20, 0x8021, 0x30)
SPRITE_TARGETS = {0x90: (0x04DFC2, "00081b18071426ff"),
                  0x91: (0x04DFCA, "000515840808d1170793141361ff"),
                  0x92: (0x04DFD8, "001a05a4160aa4ff")}


def put(rom, pc, data):
    rom[pc:pc + len(data)] = data


def put_object_stream(rom, room, pc, data, mirror=None):
    stream = W.parse_object_stream(bytes(data) + b"\0" * 4, 0, len(data))
    put(rom, pc, data)
    put(rom, W.OBJECT_TABLE_PC + room * 3, W.encode_long(pc, mirror))
    put(rom, W.DOOR_TABLE_PC + room * 3, W.encode_long(pc + stream.door_pc, mirror))


def build_recipe(fields=W.PINNED_RECIPE_FIELDS):
    recipe = {}
    for path, value in fields:
        node = recipe
        for key in path[:-1]:
            node = node.setdefault(key, {})
        node[path[-1]] = copy.deepcopy(value)
    return recipe


def build_rom():
    rom = bytearray(W.ROM_SIZE)
    put(rom, W.HEADER_ROOT_PC, hx(W.HEADER_ROOT))
    rom[W.HEADER_BANK_PC] = W.HEADER_BANK
    put(rom, W.OBJECT_ROOT_PC, hx(W.OBJECT_ROOT))
    for pc, data in W.DOOR_ROOT_OPERANDS + W.CHEST_CODE_GUARDS + W.ENTRANCE_CODE_GUARDS:
        put(rom, pc, hx(data))
    put(rom, W.SPRITE_ROOT_PC, hx(W.SPRITE_ROOT))

    headers = {0x90: "0005011600250000000c91000000", 0x91: "0005010a00000000000090920000",
               0x92: "0005010a00000000000091000000"}
    filler_obj, filler_spr, filler_pot = 0x051000, 0x04D600, 0x00DE00
    put(rom, 0x050000, hx("0000ffffffffffff"))
    put(rom, 0x04D502, hx("00ff"))
    put(rom, 0x00DDE7, hx("ffff"))
    for room in range(W.ROOM_COUNT):
        put(rom, 0x110000 + room * 2, (0x8280 + room * 14).to_bytes(2, "little"))
        put(rom, 0x110280 + room * 14,
            hx(headers[room]) if room in headers else bytes([room & 0xFF, room >> 8] + [1] * 12))

        if room in W.OBJECT_STREAMS:
            pc, _, _, old = W.OBJECT_STREAMS[room]
            put_object_stream(rom, room, pc, hx(old), MIRROR)
        elif room == 0x77:
            put_object_stream(rom, room, 0x148338 - 15, hx("0100 101005 ffff ffff f0ff 6000 ffff"))
        elif room in (0x02, 0x93):
            put_object_stream(rom, room, 0x050000, hx("0000ffffffffffff"), MIRROR)
        else:
            body = bytes([1, 0, room & 0x7F, 0x10, 0x05]) + hx("ffff ffff f0ff") + \
                bytes([0x60, room & 0x7F]) + hx("ffff")
            put_object_stream(rom, room, filler_obj, body, MIRROR)
            filler_obj += len(body)

        if room in SPRITE_TARGETS:
            pc, data = SPRITE_TARGETS[room]
            put(rom, pc, hx(data))
        elif room % 3:
            pc = 0x04D502
        else:
            pc = filler_spr
            put(rom, pc, bytes([0, room & 0x1F, 0x10, 0x40, 0xFF]))
            filler_spr += 5
        put(rom, W.SPRITE_TABLE_PC + room * 2, (pc & 0x7FFF | 0x8000).to_bytes(2, "little"))

        if room == 0x05:
            pc = 0x00E6A4
            put(rom, pc, hx("10000bffff"))
        elif room < 0x40 and room % 4 == 0:
            pc = filler_pot
            put(rom, pc, bytes([room, 0x10, 0x0B, 0xFF, 0xFF]))
            filler_pot += 5
        else:
            pc = 0x00DDE7
        put(rom, W.POT_TABLE_PC + room * 2, (pc & 0x7FFF | 0x8000).to_bytes(2, "little"))
    put(rom, 0x00E6A9, hx("0bffff0b641c0bffff"))
    put(rom, W.POT_PAD_SLOTS[0], hx("b0e6") * 23)

    for index in range(168):
        word = 0x0092 if index == 57 else CHEST_ROOMS[index % len(CHEST_ROOMS)]
        item = 0x1C if index == 57 else index & 0x7F
        put(rom, W.CHEST_TABLE_PC + index * 3, word.to_bytes(2, "little") + bytes([item]))
    put(rom, W.CHEST_SIZE_OPERAND_PC, hx("f801"))

    put(rom, 0x078050, hx("aaaa9000bbbb"))
    put(rom, 0x078E50, hx("1111d80d2222"))
    put(rom, 0x078C50, hx("3333100d4444"))
    put(rom, 0x078340, hx("55555555555555550d0c0d0d010001016666666666666666"))
    return rom


def manifest_for(rom):
    def snes(pc):
        return f"0x{W.pc_to_snes(pc):06X}"

    def regions(spans):
        return [{"start": snes(a), "end": snes(b)} for a, b in spans]

    return {
        "rom": {"dev_rom_sha1": hashlib.sha1(rom).hexdigest(), "dev_rom_size": W.ROM_SIZE},
        "dungeon_stream_regions": {
            "objects": {"pointer_table": "0x1F8000", "pointer_count": 296,
                        "pointer_encoding": "long24",
                        "data_regions": regions(W.OBJECT_DATA_REGIONS),
                        "allocation_regions": regions([W.OBJECT_ALLOC_REGION])},
            "sprites": {"pointer_table": "0x09D2B2", "pointer_bank": "0x09",
                        "data_regions": regions([W.SPRITE_REGION])},
            "pot_items": {"pointer_table": "0x01DB69", "pointer_bank": "0x01",
                          "data_regions": regions([W.POT_REGION])},
        },
        "protected_regions": {"regions": [{"start": "0x008000", "end": "0x008004"}]},
        "owned_banks": {"banks": [{"bank": "0x1E", "ownership": "asm_owned"},
                                  {"bank": "0x7E", "ownership": "ram"}]},
        "allocation_contracts": {"ledger": {"tables": [], "claims": []}},
        "graphics_sheet_regions": {"allocation_regions": [{"start": "0x238000",
                                                           "end": "0x248000"}]},
        "editor_managed_regions": {"regions": [{"start": "0x228280", "end": "0x2292B0"}]},
    }


def pins_for(rom, recipe_bytes):
    table = bytes(rom[W.CHEST_TABLE_PC:W.CHEST_TABLE_PC + W.CHEST_CAPACITY])
    return W.Pins(hashlib.sha256(rom).hexdigest(), hashlib.sha1(rom).hexdigest(),
                  hashlib.sha256(recipe_bytes).hexdigest(), hashlib.sha256(table).hexdigest())


def chest_rooms(rom):
    size = int.from_bytes(rom[W.CHEST_SIZE_OPERAND_PC:W.CHEST_SIZE_OPERAND_PC + 2], "little")
    rooms = {}
    for pc in range(W.CHEST_TABLE_PC, W.CHEST_TABLE_PC + size, 3):
        rooms.setdefault(rom[pc] | (rom[pc + 1] & 0x7F) << 8, []).append(bytes(rom[pc:pc + 3]))
    return rooms


class Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = bytes(build_rom())
        cls.recipe = json.dumps(build_recipe()).encode()

    def plan(self, rom=None, recipe=None, manifest=None, pins=None):
        rom = self.base if rom is None else bytes(rom)
        recipe = self.recipe if recipe is None else recipe
        manifest = manifest_for(rom) if manifest is None else manifest
        return W.build_plan(rom, recipe, manifest, pins or pins_for(rom, recipe))

    def refused(self, fragment, **kwargs):
        with self.assertRaises(W.PlanError) as ctx:
            self.plan(**kwargs)
        self.assertIn(fragment, str(ctx.exception))


class PlanTests(Fixture):
    def test_plan_changes_only_target_rooms_and_entrance(self):
        out, report = self.plan()
        changed = report["isolation"]["changed_rooms"]
        self.assertEqual(changed["header"], ["0x90", "0x91", "0x92"])
        self.assertEqual(changed["objects"], ["0x90", "0x91", "0x92"])
        self.assertEqual(changed["sprites"], ["0x91"])
        self.assertEqual(changed["pots"], ["0x91"])
        self.assertEqual(report["allocations"]["object_stream_91"]["chosen"], "0x148338")
        self.assertEqual(out[0x148338:0x148338 + 77], hx(
            W.PINNED_RECIPE_FIELDS[[p for p, _ in W.PINNED_RECIPE_FIELDS].index(
                ("rooms", "0x91", "object_stream", "after_hex"))][1]))
        self.assertEqual(out[0x0F81B3:0x0F81B6], hx("3883a9"))
        doors = {r: out[W.DOOR_TABLE_PC + r * 3:W.DOOR_TABLE_PC + r * 3 + 3].hex()
                 for r in W.TARGET_ROOMS}
        self.assertEqual(doors, {0x90: "b1808a", 0x91: "7983a9", 0x92: "108a8a"})
        self.assertEqual(out[0x148338 + 0x3F:0x148338 + 0x41], hx("f0ff"))
        self.assertEqual(out[0x00E6B0:0x00E6B2], hx("ffff"))
        self.assertEqual(out[0x078050:0x078056], hx("aaaa9000bbbb"))
        self.assertEqual(out[0x078E50:0x078E56], hx("1111d8132222"))
        self.assertEqual(out[0x078C50:0x078C56], hx("333310134444"))
        self.assertEqual(out[0x078340:0x078358],
                         hx("5555555555555555" "1312131301000101" "6666666666666666"))

    def test_chest_order_preserved_except_room_92(self):
        out, _ = self.plan()
        before, after = chest_rooms(self.base), chest_rooms(out)
        self.assertEqual(before.pop(0x92), [hx("92001c")])
        self.assertNotIn(0x92, after)
        self.assertEqual(after, before)
        self.assertEqual(out[W.CHEST_SIZE_OPERAND_PC:W.CHEST_SIZE_OPERAND_PC + 2], hx("f501"))

    def test_isolation_refuses_unplanned_room_change(self):
        out, _ = self.plan()
        inv = W.build_inventory(self.base)
        before = {r: W.logical_room(self.base, inv, r) for r in range(W.ROOM_COUNT)}
        tampered = bytearray(out)
        sprite_pc = inv.spr_span[0x0C][0]
        tampered[sprite_pc + 2] ^= 1
        with self.assertRaises(W.PlanError) as ctx:
            W.room_changes(before, bytes(tampered), W.build_inventory(bytes(tampered)))
        self.assertIn("room 0x00C sprites changed", str(ctx.exception))

    def test_diff_outside_writes_refused(self):
        out, report = self.plan()
        allowed = [(int(a, 16), int(b, 16)) for a, b in report["allowed_ranges"]]
        tampered = bytearray(out)
        tampered[0x1FFFF0] ^= 0xFF
        with self.assertRaises(W.PlanError):
            W.verify_diff_within(self.base, bytes(tampered), allowed)

    def test_wrong_hash_truncated_and_headered_refused(self):
        pins = pins_for(self.base, self.recipe)
        other = bytearray(self.base)
        other[0x1FFFF0] ^= 1
        self.refused("not the pinned base", rom=other, pins=pins)
        self.refused("truncated", rom=self.base[:-1], pins=pins)
        self.refused("headered", rom=bytes(512) + self.base[:-512] + self.base[-512:], pins=pins)

    def test_preimage_mismatch_refused_even_when_base_hash_is_repinned(self):
        chest_pin = pins_for(self.base, self.recipe).chest_table_sha256
        cases = ((0x110A60 + 5, 0x01, "header_90"),
                 (0x050091 + 2, 0x01, "room 0x90 object stream"),
                 (W.CHEST_TABLE_PC + 10 * 3 + 2, 0x01, "chest table preimage"),
                 (0x078E52, 0x01, "entrance_29_ypos"),
                 (0x078348 + 7, 0x01, "entrance_29_edges"),
                 (0x148338 + 40, 0x01, "object allocation"),
                 (0x00E6A9 + 8, 0x01, "pot_stream_91"),
                 (W.OBJECT_TABLE_PC + 0x91 * 3 + 2, 0x80, "room 0x91 object pointer"),
                 (W.DOOR_TABLE_PC + 0x92 * 3 + 2, 0x80, "room 0x92 door pointer"))
        for pc, flip, fragment in cases:
            with self.subTest(fragment=fragment):
                rom = bytearray(self.base)
                rom[pc] ^= flip
                pins = W.Pins(**{**pins_for(rom, self.recipe).__dict__,
                                 "chest_table_sha256": chest_pin})
                self.refused(fragment, rom=rom, pins=pins)

    def test_recipe_mutation_cannot_expand_scope(self):
        fields = [(p, v) for p, v in W.PINNED_RECIPE_FIELDS]
        index = [p for p, _ in fields].index(("rooms", "0x91", "object_stream", "after_hex"))
        fields[index] = (fields[index][0], fields[index][1].replace("ffff ffff", "aaaaaa ffff ffff", 1))
        mutated = json.dumps(build_recipe(fields)).encode()
        self.refused("recipe field rooms.0x91.object_stream.after_hex", recipe=mutated)
        reformatted = json.dumps(build_recipe(), indent=1).encode()
        self.refused("not the reviewed recipe", recipe=reformatted,
                     pins=pins_for(self.base, self.recipe))
        schema = build_recipe()
        schema["schema"] = "z3ed-import/v1"
        self.refused("recipe field schema", recipe=json.dumps(schema).encode())

    def test_protected_manifest_range_blocks_write(self):
        manifest = manifest_for(self.base)
        manifest["protected_regions"]["regions"].append({"start": "0x01DC8B", "end": "0x01DC8C"})
        self.refused("pot_slot_91 hits protected range", manifest=manifest)


class AliasAndAllocationTests(Fixture):
    def with_pointer(self, table, room, data):
        rom = bytearray(self.base)
        put(rom, table + room * len(data), data)
        return rom

    def test_object_alias_and_interior_pointer_refused(self):
        exact = self.with_pointer(W.OBJECT_TABLE_PC, 0x10, hx("bd898a"))
        self.refused("object stream of room 0x92 is shared with room 0x010", rom=exact)
        interior = self.with_pointer(W.OBJECT_TABLE_PC, 0x10, W.encode_long(0x050094))
        self.refused("object stream of room 0x90 is shared with room 0x010", rom=interior)
        door = self.with_pointer(W.DOOR_TABLE_PC, 0x10, W.encode_long(0x0509C0))
        self.refused("object stream of room 0x92 has a foreign pointer", rom=door)

    def test_allocation_refuses_pointer_into_free_tail(self):
        door = self.with_pointer(W.DOOR_TABLE_PC, 0x10, W.encode_long(0x148340))
        self.refused("targets unparsed bytes in the allocation region", rom=door)
        rom = bytearray(self.base)
        put(rom, 0x148350, hx("0000ffffffffffff"))
        put(rom, W.OBJECT_TABLE_PC + 0x10 * 3, W.encode_long(0x148350))
        self.refused("allocator chose 0x148358", rom=rom)

    def test_allocation_refuses_reserved_range(self):
        manifest = manifest_for(self.base)
        manifest["protected_regions"]["regions"].append({"start": "0x298340", "end": "0x298341"})
        self.refused("allocation overlaps reserved range", manifest=manifest)

    def test_sprite_interior_alias_refused(self):
        rom = self.with_pointer(W.SPRITE_TABLE_PC, 0x10, hx("cddf"))
        self.refused("sprite stream of room 0x91 is shared with room 0x010", rom=rom)

    def test_pot_space_overlap_refused(self):
        pointer = self.with_pointer(W.POT_TABLE_PC, 0x10, hx("aae6"))
        self.refused("pot stream of 0x010 overlaps", rom=pointer)
        rom = bytearray(self.base)
        put(rom, 0x00E6A7, hx("2000"))
        self.refused("pot stream of 0x005 overlaps", rom=rom)

    def test_padded_pot_pointer_must_target_sentinel(self):
        rom = bytearray(self.base)
        put(rom, W.POT_PAD_SLOTS[0] + 10, hx("aae6"))
        self.refused("padded pot pointer words", rom=rom)

    def test_room_92_needs_exactly_one_chest_record(self):
        rom = bytearray(self.base)
        put(rom, W.CHEST_TABLE_PC + 100 * 3, hx("920005"))
        self.refused("exactly the one Mitts chest", rom=rom)


class PublishTests(unittest.TestCase):
    DATA = bytes(range(64))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.final = self.dir / "final.bin"

    def tearDown(self):
        self.tmp.cleanup()

    def leftovers(self):
        return sorted(p.name for p in self.dir.iterdir() if p.name != self.final.name)

    def test_success_publishes_only_complete_bytes(self):
        W.publish_exclusive(self.final, self.DATA, 0o444)
        info = os.lstat(self.final)
        self.assertEqual(self.final.read_bytes(), self.DATA)
        self.assertEqual((stat.S_IMODE(info.st_mode), info.st_nlink), (0o444, 1))
        self.assertEqual(self.leftovers(), [])

    def test_partial_write_failure_leaves_final_absent(self):
        real_write, calls = os.write, []

        def partial(fd, data):
            calls.append(fd)
            if len(calls) > 1:
                raise OSError(errno.EIO, "injected write failure")
            return real_write(fd, bytes(data[:4]))

        with mock.patch.object(W.os, "write", partial), self.assertRaises(OSError):
            W.publish_exclusive(self.final, self.DATA, 0o644)
        self.assertFalse(os.path.lexists(self.final))
        self.assertEqual(self.leftovers(), [])

    def test_fsync_failure_leaves_final_absent(self):
        with mock.patch.object(W.os, "fsync", side_effect=OSError(errno.EIO, "injected")), \
                self.assertRaises(OSError):
            W.publish_exclusive(self.final, self.DATA, 0o644)
        self.assertFalse(os.path.lexists(self.final))
        self.assertEqual(self.leftovers(), [])

    def test_destination_appearing_before_publish_is_not_clobbered(self):
        real_fsync = os.fsync

        def intrude(fd):
            if not self.final.exists():
                self.final.write_bytes(b"intruder")
            real_fsync(fd)

        with mock.patch.object(W.os, "fsync", intrude), self.assertRaises(FileExistsError):
            W.publish_exclusive(self.final, self.DATA, 0o644)
        self.assertEqual(self.final.read_bytes(), b"intruder")
        self.assertEqual(self.leftovers(), [])

    def test_only_owned_temp_is_removed(self):
        def swap_then_fail(src, dst):
            os.unlink(src)
            Path(src).write_bytes(b"foreign")
            raise OSError(errno.EIO, "injected link failure")

        with mock.patch.object(W.os, "link", swap_then_fail), self.assertRaises(OSError):
            W.publish_exclusive(self.final, self.DATA, 0o644)
        self.assertFalse(os.path.lexists(self.final))
        [foreign] = self.leftovers()
        self.assertEqual((self.dir / foreign).read_bytes(), b"foreign")


class FileGuardTests(Fixture):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name).resolve()
        self.rom = self.dir / "base.bin"
        self.rom.write_bytes(self.base)
        self.recipe_path = self.dir / "recipe.json"
        self.recipe_path.write_bytes(self.recipe)
        self.manifest = self.dir / "manifest.json"
        self.manifest.write_text(json.dumps(manifest_for(self.base)))
        self.shared = self.dir / "shared"
        (self.shared / "Roms").mkdir(parents=True)
        self.pins = pins_for(self.base, self.recipe)

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, *extra):
        argv = ["--rom", str(self.rom), "--recipe", str(self.recipe_path),
                "--manifest", str(self.manifest), *map(str, extra)]
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = W.main(argv, pins=self.pins, protected_dirs=(self.shared,))
        text = buf.getvalue()
        return code, json.loads(text) if text else None

    def snapshot(self):
        return {p: p.read_bytes() for p in sorted(self.dir.rglob("*")) if p.is_file()}

    def test_dry_run_writes_nothing(self):
        before = self.snapshot()
        code, report = self.run_main()
        self.assertEqual((code, report["status"], report["mode"]), (0, "ok", "dry-run"))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(report["source"]["sha256_after_run"], self.pins.base_sha256)

    def test_write_creates_verified_output_and_rollback_once(self):
        out, rollback = self.dir / "out.sfc", self.dir / "rollback.sfc"
        code, report = self.run_main("--write", "--output", out, "--rollback", rollback)
        self.assertEqual(code, 0, report)
        self.assertEqual(hashlib.sha256(out.read_bytes()).hexdigest(), report["output_sha256"])
        self.assertEqual(rollback.read_bytes(), self.base)
        self.assertEqual(self.rom.read_bytes(), self.base)
        self.assertFalse(os.stat(rollback).st_mode & stat.S_IWUSR)
        written = self.snapshot()
        code, report = self.run_main("--write", "--output", out, "--rollback", self.dir / "r2")
        self.assertEqual((code, report["status"]), (1, "refused"))
        self.assertIn("already exists", report["error"])
        self.assertEqual(self.snapshot(), written)

    def assert_refused(self, fragment, *extra):
        before = self.snapshot()
        code, report = self.run_main(*extra)
        self.assertEqual((code, report["status"]), (1, "refused"))
        self.assertIn(fragment, report["error"])
        self.assertEqual(self.snapshot(), before)

    def test_shared_and_symlinked_destinations_refused(self):
        rollback = self.dir / "rb.sfc"
        self.assert_refused("protected directory", "--write", "--output",
                            self.shared / "Roms" / "out.sfc", "--rollback", rollback)
        link = self.dir / "link"
        link.symlink_to(self.shared / "Roms")
        self.assert_refused("protected directory", "--write", "--output", link / "out.sfc",
                            "--rollback", rollback)
        self.assert_refused("protected directory", "--write", "--output", self.dir / "o.sfc",
                            "--rollback", link / "rb.sfc")
        self.assert_refused("protected directory", "--report", link / "r.json")

    def test_existing_hardlink_alias_and_input_targets_refused(self):
        hard = self.dir / "hard.sfc"
        os.link(self.rom, hard)
        rollback = self.dir / "rb.sfc"
        self.assert_refused("already exists", "--write", "--output", hard, "--rollback", rollback)
        self.assert_refused("already exists", "--write", "--output", self.rom, "--rollback", rollback)
        dangling = self.dir / "dangling.sfc"
        dangling.symlink_to(self.dir / "missing.sfc")
        self.assert_refused("already exists", "--write", "--output", dangling, "--rollback", rollback)
        existing = self.dir / "existing.sfc"
        existing.write_bytes(b"keep")
        self.assert_refused("already exists", "--write", "--output", self.dir / "o.sfc",
                            "--rollback", existing)
        same = self.dir / "same.sfc"
        self.assert_refused("aliases", "--write", "--output", same, "--rollback", same)
        self.assert_refused("already exists", "--report", self.recipe_path.with_suffix(".json"))

    def test_output_publish_failure_keeps_complete_rollback_only(self):
        out, rollback = self.dir / "out.sfc", self.dir / "rollback.sfc"
        real_link, calls = os.link, []

        def fail_second(src, dst):
            calls.append(dst)
            if len(calls) > 1:
                raise OSError(errno.EIO, "injected output publish failure")
            return real_link(src, dst)

        with mock.patch.object(W.os, "link", fail_second):
            code, report = self.run_main("--write", "--output", out, "--rollback", rollback)
        self.assertEqual((code, report["status"]), (1, "refused"))
        self.assertFalse(os.path.lexists(out))
        self.assertEqual(rollback.read_bytes(), self.base)
        self.assertFalse(os.stat(rollback).st_mode & stat.S_IWUSR)
        self.assertEqual(self.rom.read_bytes(), self.base)
        self.assertEqual([p for p in self.dir.iterdir() if p.name.endswith(".tmp")], [])

    def test_report_file_is_created_once(self):
        path = self.dir / "report.json"
        code, printed = self.run_main("--report", path)
        self.assertEqual((code, printed), (0, None))
        first = path.read_bytes()
        self.assertEqual(json.loads(first)["status"], "ok")
        self.assert_refused("already exists", "--report", path)
        self.assertEqual(path.read_bytes(), first)

    def test_write_flags_must_be_explicit(self):
        self.assert_refused("--write needs --output and --rollback", "--write",
                            "--output", self.dir / "o.sfc")
        self.assert_refused("only accepted with --write", "--output", self.dir / "o.sfc")


if __name__ == "__main__":
    unittest.main()
