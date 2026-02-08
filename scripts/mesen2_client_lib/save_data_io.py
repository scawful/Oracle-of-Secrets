"""Read/write the active savefile block (WRAM mirror of SRAM)."""

from __future__ import annotations

from dataclasses import dataclass

from .constants import SAVEFILE_WRAM_START, SAVEFILE_WRAM_SIZE


@dataclass(frozen=True)
class SaveDataRegion:
    start: int = SAVEFILE_WRAM_START
    size: int = SAVEFILE_WRAM_SIZE


def read_savefile_bytes(bridge, *, region: SaveDataRegion | None = None) -> bytes:
    region = region or SaveDataRegion()

    # Prefer the binary block read if the socket supports it.
    data = b""
    for memtype in (None, "WRAM"):
        try:
            data = bridge.read_block_binary(region.start, region.size, memtype=memtype)
        except Exception:
            data = b""
        if len(data) == region.size:
            break

    if len(data) != region.size:
        for memtype in (None, "WRAM"):
            try:
                data = bridge.read_block(region.start, region.size, memtype=memtype)
            except Exception:
                data = b""
            if len(data) == region.size:
                break

    if len(data) != region.size:
        raise ValueError(f"Failed to read save data: expected {region.size} bytes, got {len(data)}")
    return data


def write_savefile_bytes(bridge, data: bytes, *, region: SaveDataRegion | None = None) -> None:
    region = region or SaveDataRegion()
    if len(data) != region.size:
        raise ValueError(f"Invalid save data length: expected {region.size} bytes, got {len(data)}")

    # Chunk writes: keep socket payloads small/reliable.
    chunk = 0x100
    for off in range(0, region.size, chunk):
        part = data[off : off + chunk]
        # Some socket builds reject explicit memtype="WRAM" for READ/WRITEBLOCK.
        ok = bridge.write_block(region.start + off, part, memtype=None)
        if not ok:
            raise RuntimeError(f"Failed to write save data at 0x{region.start + off:06X}")
