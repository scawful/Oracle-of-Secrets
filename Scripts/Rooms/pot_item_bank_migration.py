#!/usr/bin/env python3
"""Move the dungeon pot-item data from bank $01 to bank $5C (offline, one shot).

Vanilla RevealPotItem ($01:E6B2) is the only reader of the pot data:
  $01:E6C1  LDA.l RoomData_PotItems_Pointers,X   16-bit pointer, table $01:DB69
  $01:E6C7  LDA.w #$0001                         data bank (bytes A9 01 00)
The bank-$01 data region (PC 0xDDE7-0xE6B2) is full. This tool:
  1. copies every room's stream, byte for byte, to $5C:8000 upward
     (rooms that shared one pointer still share one pointer),
  2. rewrites the 296 table words at $01:DB69,
  3. points the 23 pad words (PC 0xDDB9-0xDDE7) at a reserved FFFF at $5C:FFFE,
  4. changes the loader operand at PC 0xE6C8 from $01 to $5C.
The old bank-$01 data bytes are left in place as a rollback copy.

Each room's record order is unchanged, so the per-room pot bits in SRAM
($7EF580) keep their meaning.

Default is a dry run: it reads --rom, plans, self-checks and prints a JSON
report. No ROM is written without --write; --report, when named, is the only
file a dry run creates.

Report status: "ok"; "refused" (nothing was written); "failed" (a file listed
under "written" was created or replaced before the error; exit code 1).

  dry run   pot_item_bank_migration.py --rom ROM
  new file  pot_item_bank_migration.py --rom ROM --expect-sha256 HASH \\
                --write --output NEW.sfc --rollback BEFORE.sfc
  in place  pot_item_bank_migration.py --rom ROM --expect-sha256 HASH \\
                --write --in-place --rollback BEFORE.sfc
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

TOOL = "pot_item_bank_migration/1"

ROOM_COUNT = 296
TABLE_PC = 0x00DB69                      # $01:DB69, 296 words
PAD_PC = TABLE_PC + ROOM_COUNT * 2       # 0x00DDB9, 23 vanilla pad words
PAD_COUNT = 23
OLD_BANK = 0x01
OLD_START_PC = 0x00DDE7                  # first stream byte in bank $01
OLD_END_PC = 0x00E6B2                    # RevealPotItem starts here
LOADER_PC = 0x00E6C7                     # LDA.w #$00bb
OPERAND_PC = LOADER_PC + 1
NEW_BANK = 0x5C
NEW_START_PC = 0x2E0000                  # $5C:8000
NEW_END_PC = 0x2E7FFE                    # end of the stream region (exclusive)
PAD_SENTINEL_PC = 0x2E7FFE               # $5C:FFFE, reserved FFFF for the pad words
BANK_END_PC = 0x2E8000
TERMINATOR = b"\xff\xff"

assert PAD_PC + PAD_COUNT * 2 == OLD_START_PC


class PlanError(RuntimeError):
    """The ROM does not match what this migration expects."""


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise PlanError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def word(rom: bytes, pc: int) -> int:
    return rom[pc] | rom[pc + 1] << 8


def lorom_pc(bank: int, address: int) -> int:
    expect(address >= 0x8000, f"pointer ${address:04X} is not a ROM address")
    return (bank & 0x7F) * 0x8000 + (address - 0x8000)


def lorom_address(pc: int) -> int:
    return 0x8000 + (pc & 0x7FFF)


def parse_stream(rom: bytes, start: int, limit: int, label: str) -> bytes:
    """The stream at `start`: 3-byte records, then the word $FFFF."""
    at = start
    while True:
        expect(at + 2 <= limit, f"{label}: pot list is unterminated before PC 0x{limit:06X}")
        if rom[at:at + 2] == TERMINATOR:
            return bytes(rom[start:at + 2])
        expect(at + 3 <= limit, f"{label}: pot record at PC 0x{at:06X} is cut off")
        at += 3


def room_streams(rom: bytes, bank: int, start: int, end: int) -> list[bytes]:
    """Every room's stream as the game reads it: table word + loader bank."""
    streams = []
    for room in range(ROOM_COUNT):
        pc = lorom_pc(bank, word(rom, TABLE_PC + room * 2))
        expect(start <= pc < end,
               f"room 0x{room:03X}: pot pointer PC 0x{pc:06X} is outside "
               f"0x{start:06X}-0x{end:06X}")
        streams.append(parse_stream(rom, pc, end, f"room 0x{room:03X}"))
    return streams


def build_plan(rom: bytes) -> tuple[bytes, dict[str, Any]]:
    """Return (migrated image, report). Raises PlanError on any mismatch."""
    expect(len(rom) >= BANK_END_PC,
           f"ROM is 0x{len(rom):X} bytes; bank ${NEW_BANK:02X} needs 0x{BANK_END_PC:X}")
    loader = bytes(rom[LOADER_PC:LOADER_PC + 3])
    expect(loader != bytes((0xA9, NEW_BANK, 0x00)),
           f"already migrated: loader at PC 0x{LOADER_PC:X} names bank ${NEW_BANK:02X}")
    expect(loader == bytes((0xA9, OLD_BANK, 0x00)),
           f"loader at PC 0x{LOADER_PC:X} is {loader.hex().upper()}, expected A90100")
    target = rom[NEW_START_PC:BANK_END_PC]
    used = sum(1 for value in target if value not in (0x00, 0xFF))
    expect(used == 0, f"bank ${NEW_BANK:02X} is not empty: {used} bytes are not 00/FF")

    before = room_streams(rom, OLD_BANK, OLD_START_PC, OLD_END_PC)
    old_pcs = [lorom_pc(OLD_BANK, word(rom, TABLE_PC + room * 2))
               for room in range(ROOM_COUNT)]
    for slot in range(PAD_COUNT):
        pad_pc = lorom_pc(OLD_BANK, word(rom, PAD_PC + slot * 2))
        expect(OLD_START_PC <= pad_pc and pad_pc + 2 <= OLD_END_PC
               and rom[pad_pc:pad_pc + 2] == TERMINATOR,
               f"pad word {slot} (PC 0x{PAD_PC + slot * 2:06X}) does not point at "
               "an FFFF inside the bank-$01 pot region")

    # One copy per distinct old pointer, in old address order. Rooms that
    # shared a pointer keep sharing; overlapping tails become separate copies.
    out = bytearray(rom)
    new_pc_by_old: dict[int, int] = {}
    cursor = NEW_START_PC
    for old_pc in sorted(set(old_pcs)):
        stream = before[old_pcs.index(old_pc)]
        expect(cursor + len(stream) <= NEW_END_PC,
               f"bank ${NEW_BANK:02X} stream region is too small")
        out[cursor:cursor + len(stream)] = stream
        new_pc_by_old[old_pc] = cursor
        cursor += len(stream)
    out[PAD_SENTINEL_PC:PAD_SENTINEL_PC + 2] = TERMINATOR
    for room, old_pc in enumerate(old_pcs):
        address = lorom_address(new_pc_by_old[old_pc])
        out[TABLE_PC + room * 2:TABLE_PC + room * 2 + 2] = address.to_bytes(2, "little")
    pad_word = lorom_address(PAD_SENTINEL_PC).to_bytes(2, "little")
    for slot in range(PAD_COUNT):
        out[PAD_PC + slot * 2:PAD_PC + slot * 2 + 2] = pad_word
    out[OPERAND_PC] = NEW_BANK
    out = bytes(out)

    # Self-check on the result, read the way the game reads it.
    expect(len(out) == len(rom), "image size changed")
    expect(out[LOADER_PC:LOADER_PC + 3] == bytes((0xA9, NEW_BANK, 0x00)), "loader not set")
    after = room_streams(out, out[OPERAND_PC], NEW_START_PC, NEW_END_PC)
    for room in range(ROOM_COUNT):
        expect(after[room] == before[room], f"room 0x{room:03X}: stream bytes changed")
    for room in range(ROOM_COUNT):
        first = old_pcs.index(old_pcs[room])
        expect(word(out, TABLE_PC + room * 2) == word(out, TABLE_PC + first * 2),
               f"room 0x{room:03X}: shared pointer was split")
    expect(len({word(out, TABLE_PC + room * 2) for room in range(ROOM_COUNT)})
           == len(new_pc_by_old), "distinct pointers were merged")
    allowed = ((TABLE_PC, OLD_START_PC), (OPERAND_PC, OPERAND_PC + 1),
               (NEW_START_PC, BANK_END_PC))
    stray = [pc for pc in range(len(rom)) if rom[pc] != out[pc]
             and not any(lo <= pc < hi for lo, hi in allowed)]
    expect(not stray, f"{len(stray)} bytes changed outside the table, operand and "
                      f"bank ${NEW_BANK:02X}; first PC 0x{stray[0] if stray else 0:06X}")
    expect(out[OLD_START_PC:OLD_END_PC] == rom[OLD_START_PC:OLD_END_PC],
           "old bank-$01 data region changed")

    used_bytes = cursor - NEW_START_PC
    report = {
        "source": {"sha256": sha256(rom), "size": len(rom)},
        "output_sha256": sha256(out),
        "rooms": ROOM_COUNT,
        "rooms_with_pots": sum(1 for stream in before if len(stream) > 2),
        "pot_records": sum((len(stream) - 2) // 3 for stream in before),
        "distinct_streams": len(new_pc_by_old),
        "old_region": {"pc": [f"0x{OLD_START_PC:06X}", f"0x{OLD_END_PC:06X}"],
                       "bytes_used": sum(len(before[old_pcs.index(pc)])
                                         for pc in new_pc_by_old)},
        "new_region": {"pc": [f"0x{NEW_START_PC:06X}", f"0x{NEW_END_PC:06X}"],
                       "snes": [f"${NEW_BANK:02X}:8000", f"${NEW_BANK:02X}:FFFE"],
                       "bytes_used": used_bytes,
                       "bytes_free": NEW_END_PC - NEW_START_PC - used_bytes},
        "pad_sentinel_pc": f"0x{PAD_SENTINEL_PC:06X}",
        "loader": {"pc": f"0x{LOADER_PC:06X}", "before": loader.hex().upper(),
                   "after": out[LOADER_PC:LOADER_PC + 3].hex().upper()},
        "changed_bytes": sum(1 for a, b in zip(rom, out) if a != b),
        "checks": {"room_streams_identical": ROOM_COUNT,
                   "shared_pointers_kept": True,
                   "bytes_changed_outside_allowed_ranges": 0,
                   "old_region_untouched": True},
    }
    return out, report


def publish_exclusive(path: Path, data: bytes, mode: int) -> None:
    """Create `path` (must not exist), write, fsync."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    os.chmod(path, mode)


def new_target(path: Path, label: str, taken: Sequence[Path]) -> Path:
    resolved = path.resolve()
    expect(not path.is_symlink() and not resolved.exists(), f"{label} {path} already exists")
    expect(resolved.parent.is_dir(), f"{label} directory {resolved.parent} does not exist")
    expect(resolved not in taken, f"{label} {path} names a file already in use")
    return resolved


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", type=Path, required=True, help="ROM to migrate")
    ap.add_argument("--expect-sha256", help="refuse unless --rom has this sha256 "
                                            "(required with --write)")
    ap.add_argument("--write", action="store_true", help="write the result (default: dry run)")
    ap.add_argument("--output", type=Path, help="new migrated ROM path (with --write)")
    ap.add_argument("--in-place", action="store_true",
                    help="with --write: replace --rom itself (needs --rollback)")
    ap.add_argument("--rollback", type=Path, help="new copy of the input ROM (with --write)")
    ap.add_argument("--report", type=Path, help="new JSON report path (default: stdout only)")
    args = ap.parse_args(argv)

    report: dict[str, Any] = {"tool": TOOL, "mode": "write" if args.write else "dry-run"}
    report_path = None
    written: dict[str, str] = {}
    try:
        input_path = args.rom.resolve()
        expect(input_path.is_file(), f"--rom {args.rom} is not a file")
        rom = input_path.read_bytes()
        input_sha = sha256(rom)
        if args.expect_sha256 is not None:
            expect(input_sha == args.expect_sha256.lower(),
                   f"--rom sha256 is {input_sha}, expected {args.expect_sha256.lower()}")
        taken = [input_path]
        output = rollback = None
        if args.report is not None:
            report_path = new_target(args.report, "report", taken)
            taken.append(report_path)
        if args.write:
            expect(args.expect_sha256 is not None, "--write needs --expect-sha256")
            expect(args.in_place != (args.output is not None),
                   "--write needs exactly one of --output or --in-place")
            expect(not args.in_place or args.rollback is not None,
                   "--in-place needs --rollback")
            if args.output is not None:
                output = new_target(args.output, "output", taken)
                taken.append(output)
            if args.rollback is not None:
                rollback = new_target(args.rollback, "rollback", taken)
        else:
            expect(args.output is None and args.rollback is None and not args.in_place,
                   "--output/--rollback/--in-place are only accepted with --write")

        out, plan = build_plan(rom)
        report.update(plan)
        report["source"]["path"] = str(input_path)

        if args.write:
            if rollback is not None:
                publish_exclusive(rollback, rom, 0o444)
                written["rollback"] = str(rollback)
                expect(sha256(rollback.read_bytes()) == input_sha, "rollback readback differs")
            expect(sha256(input_path.read_bytes()) == input_sha,
                   "input ROM changed during the run; nothing was replaced")
            if args.in_place:
                staged = input_path.with_name(input_path.name + f".pot-bank-{os.getpid()}.tmp")
                publish_exclusive(staged, out, input_path.stat().st_mode & 0o777)
                try:
                    expect(sha256(staged.read_bytes()) == plan["output_sha256"],
                           "staged readback differs")
                    expect(sha256(input_path.read_bytes()) == input_sha,
                           "input ROM changed during the run; nothing was replaced")
                    os.replace(staged, input_path)
                except BaseException:
                    staged.unlink(missing_ok=True)
                    raise
                target = input_path
            else:
                publish_exclusive(output, out, 0o644)
                target = output
            written["output"] = str(target)
            expect(sha256(target.read_bytes()) == plan["output_sha256"],
                   "output readback differs")
            written["output_readback_sha256"] = plan["output_sha256"]
            report["written"] = written
        else:
            expect(sha256(input_path.read_bytes()) == input_sha,
                   "input ROM changed during the run")
        report["status"] = "ok"
        code = 0
    except (PlanError, OSError, ValueError) as exc:
        # "refused" promises that nothing was written. Once the rollback copy or
        # the output exists, say so and list it.
        report["status"] = "failed" if written else "refused"
        report["error"] = str(exc)
        if written:
            report["written"] = written
        code = 1

    text = json.dumps(report, indent=2) + "\n"
    if report_path is not None and code == 0:
        try:
            publish_exclusive(report_path, text.encode(), 0o644)
        except (PlanError, OSError) as exc:
            report["report_error"] = str(exc)
            text = json.dumps(report, indent=2) + "\n"
            code = 1
    sys.stdout.write(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
