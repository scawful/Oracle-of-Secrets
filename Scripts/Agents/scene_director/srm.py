"""Edit save-file fields in an 8192-byte battery SRM. Offline; no emulator.

Layout and checksum follow Scripts/Build/prepare_goron_checkpoint.py (vanilla ALTTP):
file N (1..3) is 0x500 bytes at (N-1)*0x500, its backup copy sits 0xF00 later, and the
16-bit little-endian word sum of a valid block is 0x5A5A (fix-up word at 0x4FE).
Addresses are the WRAM mirror of the save, $7EF000..$7EF4FD (Core/sram.asm), e.g.
$7EF360 rupees, $7EF362 displayed rupees, $7EF36C max health, $7EF36D health.

The input must already be valid (primary checksum 0x5A5A and backup == primary);
only the requested bytes and the checksum word change, in both copies.
"""
from __future__ import annotations

import hashlib

SRM_SIZE = 0x2000
BLOCK_SIZE = 0x500
BACKUP_OFFSET = 0xF00
CHECKSUM = 0x4FE
VALID_SUM = 0x5A5A
SAVE_BASE = 0x7EF000


class SrmError(ValueError):
    """Bad SRM image or bad write request."""


def word_sum(block) -> int:
    return sum(int.from_bytes(block[i:i + 2], "little") for i in range(0, len(block), 2)) & 0xFFFF


def block_offsets(file_no: int):
    if file_no not in (1, 2, 3):
        raise SrmError(f"file must be 1..3, got {file_no}")
    primary = (file_no - 1) * BLOCK_SIZE
    return primary, primary + BACKUP_OFFSET


def parse_set(text: str):
    """'7EF360:u16=87' or '0x7EF3B0=5' (u8 default) -> (addr, kind, value)."""
    try:
        target, value = text.split("=", 1)
        addr, _, kind = target.partition(":")
        addr, kind, value = int(addr, 16), (kind or "u8"), int(value, 0)
    except ValueError:
        raise SrmError(f"bad --set {text!r}; use ADDR[:u8|u16]=VALUE, e.g. 7EF360:u16=87") from None
    return addr, kind, value


def edit(data: bytes, file_no: int, writes) -> bytes:
    """Return a copy of `data` with `writes` [(addr, 'u8'|'u16', value)] applied to file N."""
    if len(data) != SRM_SIZE:
        raise SrmError(f"expected an {SRM_SIZE}-byte SRM, got {len(data)} bytes")
    primary, backup = block_offsets(file_no)
    block = bytearray(data[primary:primary + BLOCK_SIZE])
    if word_sum(block) != VALID_SUM:
        raise SrmError(f"file {file_no}: checksum {word_sum(block):#06x} != {VALID_SUM:#06x}; refusing to edit")
    if block != data[backup:backup + BLOCK_SIZE]:
        raise SrmError(f"file {file_no}: backup copy differs from the primary; refusing to edit")
    touched = set()
    for addr, kind, value in writes:
        size = {"u8": 1, "u16": 2}.get(kind)
        if size is None:
            raise SrmError(f"{addr:06X}: type must be u8 or u16, got {kind!r}")
        offset = addr - SAVE_BASE
        if not 0 <= offset <= CHECKSUM - size:
            raise SrmError(f"{addr:06X}: outside the save block $7EF000..$7EF4FD")
        if not 0 <= value < 1 << (8 * size):
            raise SrmError(f"{addr:06X}: value {value} does not fit {kind}")
        block[offset:offset + size] = value.to_bytes(size, "little")
        touched.update(range(offset, offset + size))
    block[CHECKSUM:CHECKSUM + 2] = b"\0\0"
    block[CHECKSUM:CHECKSUM + 2] = ((VALID_SUM - word_sum(block)) & 0xFFFF).to_bytes(2, "little")
    result = bytearray(data)
    for start in (primary, backup):
        result[start:start + BLOCK_SIZE] = block
    allowed = {start + o for start in (primary, backup) for o in touched | {CHECKSUM, CHECKSUM + 1}}
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(data, result))):
        raise AssertionError("unexpected SRM mutation")
    if word_sum(result[primary:primary + BLOCK_SIZE]) != VALID_SUM:
        raise AssertionError("edited checksum differs")
    return bytes(result)


def report(src: bytes, out: bytes, file_no: int, writes) -> dict:
    primary, _ = block_offsets(file_no)
    fields = []
    for addr, kind, value in writes:
        size = 1 if kind == "u8" else 2
        o = primary + addr - SAVE_BASE
        fields.append({"addr": f"{addr:06X}", "type": kind, "before": int.from_bytes(src[o:o + size], "little"),
                       "after": int.from_bytes(out[o:o + size], "little")})
    return {"file": file_no, "input_sha256": hashlib.sha256(src).hexdigest(),
            "output_sha256": hashlib.sha256(out).hexdigest(), "fields": fields,
            "changed_offsets": [f"{i:04X}" for i, (a, b) in enumerate(zip(src, out)) if a != b]}
