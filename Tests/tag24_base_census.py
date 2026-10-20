"""Read-only room tag $24 census of an Oracle ROM.

Resolves the relocated room-header table the way LoadRoomHeader does
(LDA.l RoomHeader_RoomToPointer,X at $01B5DC; bank immediate at $01B5E6),
reads tag1/tag2 (header +5/+6) for all 296 rooms, and checks the tag $24
vector and RoomTag_Holes2 body. The file is only read; its SHA-256 is
recorded before and after.

  python3 Tests/tag24_base_census.py --rom Roms/oos168.sfc [--expected-sha256 HEX]
  python3 Tests/tag24_base_census.py --rom Roms/oos168x.sfc --state patched
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOM_COUNT = 296
TAG = 0x24
HEADER_POINTER_OPCODE_PC = 0x00B5DC  # BF: LDA.l long,X
HEADER_BANK_OPCODE_PC = 0x00B5E6     # A9: LDA.b #imm
TAG24_VECTOR_PC = 0x00C2C5
HOLES2_PC = 0x00CC89
HOLES2_VECTOR = 0xCC89
HOLES2_BODY = bytes.fromhex("c23020cccd90f6a0050080d9")
GATEWAY = bytes.fromhex("5c00fd2c")  # JML $2CFD00 (RoomTag_SomariaSocketDoor)
EXPECTED_BODY = {"base": HOLES2_BODY, "patched": GATEWAY + HOLES2_BODY[4:]}


class CensusError(ValueError):
    pass


def lorom_pc(address):
    bank, offset = (address >> 16) & 0xFF, address & 0xFFFF
    if bank in (0x7E, 0x7F) or offset < 0x8000:
        raise CensusError(f"0x{address:06X} is not a ROM-backed LoROM address")
    return ((bank & 0x7F) << 15) | (offset & 0x7FFF)


def span(data, pc, size, what):
    if pc < 0 or pc + size > len(data):
        raise CensusError(f"{what} [0x{pc:X}, 0x{pc + size:X}) exceeds ROM size 0x{len(data):X}")
    return data[pc:pc + size]


def census(data, state="base"):
    """Return the tag $24 census for headerless ROM bytes; errors are listed, not raised."""
    report = {"state": state, "room_count": 0, "tag24_users": [], "errors": []}
    errors = report["errors"]
    try:
        if (span(data, HEADER_POINTER_OPCODE_PC, 1, "header pointer opcode")[0] != 0xBF
                or span(data, HEADER_BANK_OPCODE_PC, 1, "header bank opcode")[0] != 0xA9):
            raise CensusError("LoadRoomHeader resolver opcodes moved")
        table = int.from_bytes(span(data, HEADER_POINTER_OPCODE_PC + 1, 3, "header table"), "little")
        bank = span(data, HEADER_BANK_OPCODE_PC + 1, 1, "header bank")[0]
        table_pc = lorom_pc(table)
        report.update(header_table_snes=f"0x{table:06X}", header_table_pc=f"0x{table_pc:06X}",
                      header_bank=f"0x{bank:02X}")
        for room in range(ROOM_COUNT):
            word = int.from_bytes(span(data, table_pc + room * 2, 2, f"room 0x{room:03X} pointer"),
                                  "little")
            header = span(data, lorom_pc((bank << 16) | word), 7, f"room 0x{room:03X} header")
            for slot, value in (("tag1", header[5]), ("tag2", header[6])):
                if value == TAG:
                    report["tag24_users"].append({"room": f"0x{room:03X}", "slot": slot})
            report["room_count"] += 1
        vector = int.from_bytes(span(data, TAG24_VECTOR_PC, 2, "tag $24 vector"), "little")
        body = bytes(span(data, HOLES2_PC, len(HOLES2_BODY), "RoomTag_Holes2 body"))
    except CensusError as exc:
        errors.append(str(exc))
        return report
    report.update(vector=f"0x{vector:04X}", holes2_bytes=body.hex())
    if vector != HOLES2_VECTOR:
        errors.append(f"tag $24 vector is 0x{vector:04X}, expected 0x{HOLES2_VECTOR:04X}")
    if body != EXPECTED_BODY[state]:
        errors.append(f"RoomTag_Holes2 bytes {body.hex()} != {state} {EXPECTED_BODY[state].hex()}")
    if report["tag24_users"]:
        errors.append(f"{len(report['tag24_users'])} room header tag slot(s) use tag $24")
    return report


def audit_file(path, expected_sha256=None, state="base"):
    path = Path(path)
    data = path.read_bytes()
    report = {"rom": str(path), "sha256_before": hashlib.sha256(data).hexdigest()}
    report.update(census(data, state))
    report["sha256_after"] = hashlib.sha256(path.read_bytes()).hexdigest()
    if report["sha256_after"] != report["sha256_before"]:
        report["errors"].append("ROM changed during the read-only census")
    if expected_sha256 is not None:
        report["expected_sha256"] = expected_sha256.lower()
        if report["sha256_before"] != report["expected_sha256"]:
            report["errors"].append("ROM SHA-256 does not match --expected-sha256")
    report["ok"] = not report["errors"]
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--state", choices=sorted(EXPECTED_BODY), default="base")
    args = parser.parse_args(argv)
    report = audit_file(args.rom, args.expected_sha256, args.state)
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
