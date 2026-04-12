"""Cartridge SRAM (.srm) helpers.

Source of truth for save algorithm/format: USDASM.

Key routines:
- SaveGameFile in `usdasm/bank_00.asm` (around $00894A):
  - Copies WRAMSAVE ($7EF000-$7EF4FF) into SRAM main + mirror
  - Computes the inverse checksum word at $7EF4FE (and writes it to SRAM)
    inverse = 0x5A5A - sum16(words over $7EF000..$7EF4FC)

Practical workflow:
- For fast iteration in a running emulator:
  - Patch WRAMSAVE (hot)
  - Optionally sync WRAMSAVE -> SRAM (persist)
- For importing/exporting `.srm`:
  - Read/write the SRAM memtype (0x2000 bytes)
  - Optionally sync a selected save slot SRAM -> WRAMSAVE (hot reload)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .save_data_io import SaveDataRegion


SRAM_SIZE = 0x2000

# Each save file is 0x500 bytes in SRAM (main copy), mirrored at +0x0F00.
SAVE_SLOT_SIZE = SaveDataRegion().size  # 0x500
SAVE_SLOT_MAIN_OFFSETS = (0x0000, 0x0500, 0x0A00)
SAVE_SLOT_MIRROR_DELTA = 0x0F00

# $701FFE lives in cart SRAM. In USDASM, it is used as an index into SaveFileOffsets.
SRAMOFF_ADDR_CPU = 0x701FFE
SRAMOFF_ADDR_SRAM = 0x1FFE


@dataclass(frozen=True)
class SaveSlotRef:
    slot: int  # 1..3
    main_base: int
    mirror_base: int


def _sum16_words_le(buf: bytes, end_exclusive: int) -> int:
    s = 0
    end_exclusive &= ~1
    for off in range(0, end_exclusive, 2):
        w = buf[off] | (buf[off + 1] << 8)
        s = (s + w) & 0xFFFF
    return s


def compute_inverse_checksum(save_block: bytes) -> int:
    """Compute inverse checksum per USDASM SaveGameFile."""
    if len(save_block) != SAVE_SLOT_SIZE:
        raise ValueError(f"Expected {SAVE_SLOT_SIZE} bytes, got {len(save_block)}")
    s = _sum16_words_le(save_block, 0x4FE)  # words over $7EF000..$7EF4FC
    return (0x5A5A - s) & 0xFFFF


def apply_inverse_checksum(save_block: bytes) -> bytes:
    """Return a copy of `save_block` with $7EF4FE updated to a consistent inverse checksum."""
    inv = compute_inverse_checksum(save_block)
    b = bytearray(save_block)
    b[0x4FE] = inv & 0xFF
    b[0x4FF] = (inv >> 8) & 0xFF
    return bytes(b)


def validate_inverse_checksum(save_block: bytes) -> bool:
    if len(save_block) != SAVE_SLOT_SIZE:
        return False
    stored = save_block[0x4FE] | (save_block[0x4FF] << 8)
    return stored == compute_inverse_checksum(save_block)


def read_cart_sram(bridge) -> bytes:
    data = bridge.read_block(0x0000, SRAM_SIZE, memtype="SRAM")
    if len(data) != SRAM_SIZE:
        raise ValueError(f"Failed to read SRAM: expected {SRAM_SIZE} bytes, got {len(data)}")
    return data


def write_cart_sram(bridge, blob: bytes, *, preserve_sramoff: bool = True) -> None:
    if len(blob) != SRAM_SIZE:
        raise ValueError(f"Invalid SRAM length: expected {SRAM_SIZE} bytes, got {len(blob)}")

    saved_sramoff = b""
    if preserve_sramoff:
        saved_sramoff = bridge.read_block(SRAMOFF_ADDR_SRAM, 2, memtype="SRAM")

    chunk = 0x100
    for off in range(0, SRAM_SIZE, chunk):
        part = blob[off : off + chunk]
        ok = bridge.write_block(off, part, memtype="SRAM")
        if not ok:
            raise RuntimeError(f"Failed to write SRAM at 0x{off:04X}")

    if preserve_sramoff and len(saved_sramoff) == 2:
        ok = bridge.write_block(SRAMOFF_ADDR_SRAM, saved_sramoff, memtype="SRAM")
        if not ok:
            raise RuntimeError("Failed to restore SRAMOFF")


def _slot_ref(slot: int) -> SaveSlotRef:
    if slot not in (1, 2, 3):
        raise ValueError("slot must be 1..3")
    main_base = SAVE_SLOT_MAIN_OFFSETS[slot - 1]
    return SaveSlotRef(slot=slot, main_base=main_base, mirror_base=main_base + SAVE_SLOT_MIRROR_DELTA)


def resolve_active_slot(bridge) -> int:
    """Return 1..3 based on $701FFE (SRAMOFF).

    In USDASM SaveGameFile:
      X = $701FFE
      Y = SaveFileOffsets[X]   (word table; indices 0,2,4)
    """
    try:
        raw = bridge.read_memory16(SRAMOFF_ADDR_CPU)
    except Exception:
        raw = 0

    # In ALTTP/OOS flow, $701FFE stores table index values 2/4/6 for slots 1/2/3.
    if raw in (2, 4, 6):
        return raw // 2

    # Some paths can leave SRAMOFF unset/zero; default to slot 1.
    if raw == 0:
        return 1

    # Fallback: treat it as file index (0..2) if small.
    if 0 <= raw <= 2:
        return raw + 1

    return 1


def read_slot_saveblock(bridge, slot: int, *, prefer_mirror: bool = False) -> bytes:
    ref = _slot_ref(slot)
    base = ref.mirror_base if prefer_mirror else ref.main_base
    blob = bridge.read_block(base, SAVE_SLOT_SIZE, memtype="SRAM")
    if len(blob) != SAVE_SLOT_SIZE:
        raise ValueError(f"Failed to read slot {slot} from SRAM (base 0x{base:04X})")
    return blob


def write_slot_saveblock(bridge, slot: int, blob: bytes, *, write_mirror: bool = True) -> None:
    if len(blob) != SAVE_SLOT_SIZE:
        raise ValueError(f"Expected {SAVE_SLOT_SIZE} bytes, got {len(blob)}")
    ref = _slot_ref(slot)
    ok = bridge.write_block(ref.main_base, blob, memtype="SRAM")
    if not ok:
        raise RuntimeError(f"Failed to write slot {slot} main SRAM (0x{ref.main_base:04X})")
    if write_mirror:
        ok = bridge.write_block(ref.mirror_base, blob, memtype="SRAM")
        if not ok:
            raise RuntimeError(f"Failed to write slot {slot} mirror SRAM (0x{ref.mirror_base:04X})")


def dump_srm_to_file(bridge, path: Path) -> None:
    blob = read_cart_sram(bridge)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)


def load_srm_from_file(bridge, path: Path, *, preserve_sramoff: bool = True) -> None:
    blob = Path(path).read_bytes()
    write_cart_sram(bridge, blob, preserve_sramoff=preserve_sramoff)

