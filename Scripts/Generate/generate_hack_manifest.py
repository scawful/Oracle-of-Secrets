#!/usr/bin/env python3
"""
Generate a hack manifest JSON for yaze editor integration.

Build pipeline context:
  - oos168.sfc  = dev ROM (yaze edits this — vanilla + room/sprite/palette data)
  - asar patches oos168.sfc → oos168x.sfc (patched ROM with ASM hack applied)
  - Yaze and asar share the dev ROM; this manifest defines the boundary

Extends the hooks scanner to produce a comprehensive manifest that tells yaze:
  - Which ROM addresses are patched by asar (hooks/org directives)
  - Which banks are fully owned by the ASM hack (expanded banks)
  - Expanded message layout and boundaries
  - Room tag mappings with semantics and feature flags
  - Feature flag state (compile-time toggles)
  - Custom SRAM variable definitions

Yaze can load this manifest to:
  - Avoid saving to hook addresses (asar overwrites them anyway)
  - Skip owned banks entirely during save (asar layer owns these)
  - Understand which vanilla data regions are safe to edit
  - Display room tag labels and message IDs in editors
  - Sync feature flags with project settings
  - Show SRAM variable names in the RAM panel / state inspector

Address classification for yaze:
  - "vanilla_safe": Yaze can freely edit (room data, palettes, sprites in vanilla banks)
  - "hook_patched": Asar patches this address; yaze edits are overwritten on build
  - "asm_owned": Entire bank owned by hack; yaze should never write here
  - "shared": Both yaze and asar may reference (e.g., room headers ASM reads)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Import the existing hooks scanner infrastructure
from generate_hooks_json import (
    scan_hooks,
    _load_global_defines,
    HookEntry,
)

# ---------------------------------------------------------------------------
# Additional regex patterns for manifest-specific scanning
# ---------------------------------------------------------------------------

# Captures: org $XXYYYY where XX >= $1E (expanded banks)
ORG_BANK_RE = re.compile(r"^\s*org\s+\$([0-9A-Fa-f]{6})\b")

# Captures: freedata bank $XX
FREEDATA_BANK_RE = re.compile(
    r"^\s*freedata\s+(?:clean\s+)?bank\s+\$([0-9A-Fa-f]{1,2})\b", re.IGNORECASE
)

# Captures SRAM variable definitions: Name = $7EFxxx
SRAM_VAR_RE = re.compile(
    r"^\s*([A-Za-z_]\w+)\s*=\s*\$(7EF[0-9A-Fa-f]{3})\b"
)

# Captures SRAM bit constants: !Name = $XX
SRAM_BIT_RE = re.compile(
    r"^\s*!([A-Za-z_]\w+)\s*=\s*\$([0-9A-Fa-f]{2})\b"
)

# Room tag org pattern: org $01CCxx
ROOM_TAG_RE = re.compile(r"^\s*org\s+\$01CC([0-9A-Fa-f]{2})\b")

# Feature flag pattern: !ENABLE_xxx = N
FEATURE_FLAG_RE = re.compile(
    r"^\s*!(ENABLE_\w+)\s*=\s*(\d+)\b"
)

# Message label pattern: Message_XXX:
MESSAGE_LABEL_RE = re.compile(r"^\s*Message_([0-9A-Fa-f]{2,3}):")

# Comment annotation for room tags: ; @hook ... name=X
HOOK_NAME_RE = re.compile(r"name=(\S+)")

# assert pc() <= $XXXXXX — end of bank assertion
ASSERT_PC_RE = re.compile(r"assert\s+pc\(\)\s*<=\s*\$([0-9A-Fa-f]{6})")

# Comment with purpose annotation
PURPOSE_COMMENT_RE = re.compile(r";\s*(.+)$")

SKIP_DIRS = {
    ".git", ".context", ".claude", ".cursor",
    "Roms", "Docs", "docs",
    "build", "bin", "obj", "Tools", "tools", "Tests", "tests", "node_modules",
    "ZScreamNew",
}

DUNGEON_ROOM_COUNT = 296
OBJECT_TABLE_POINTER_OPERAND_PC = 0x874C
SPRITE_TABLE_POINTER_OPERAND_PC = 0x4C298
POT_POINTER_TABLE_PC = 0xDB69
ROOM_HEADER_TABLE_POINTER_OPERAND_PC = 0xB5DD
ROOM_HEADER_BANK_OPERAND_PC = 0xB5E7
DUNGEON_MESSAGE_IDS_PC = 0x3F61D

ROOM_HEADER_SIZE = 14
SPRITE_DATA_END_PC = 0x4EC9F
POT_DATA_END_PC = 0xE6B2
CUSTOM_COLLISION_POINTER_TABLE_PC = 0x128090
CUSTOM_COLLISION_DATA_START_PC = 0x128450
CUSTOM_COLLISION_DATA_END_PC = 0x12E000

OBJECT_DATA_REGIONS_PC = (
    (0x50000, 0x53730),
    (0xF878A, 0x100000),
    (0x1EB90, 0x20000),
    (0x138000, 0x140000),
    (0x148000, 0x150000),
)
OBJECT_ALLOCATION_REGIONS_PC = ((0x148000, 0x150000),)


class ManifestGenerationError(RuntimeError):
    """Raised when live ROM data cannot safely produce manifest metadata."""


def _should_skip(path: Path) -> bool:
    for part in path.parts:
        if part in SKIP_DIRS:
            return True
    return False


# ---------------------------------------------------------------------------
# Bank ownership detection
# ---------------------------------------------------------------------------

@dataclass
class BankRegion:
    bank: int
    start: int  # SNES address
    end: Optional[int]  # SNES address (from assert or next org)
    source: str
    purpose: str = ""


def scan_bank_ownership(root: Path) -> list[dict]:
    """Detect which banks are owned by the hack via org directives."""
    bank_sources: dict[int, list[dict]] = {}

    for asm_path in root.rglob("*.asm"):
        if _should_skip(asm_path):
            continue
        try:
            text = asm_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        rel = str(asm_path.relative_to(root))
        lines = text.splitlines()

        for i, line in enumerate(lines):
            # Check for org $XX8000+ (expanded bank entry points)
            m = ORG_BANK_RE.match(line)
            if m:
                addr = int(m.group(1), 16)
                bank = (addr >> 16) & 0xFF
                # Only track expanded banks (>= $1E, avoiding vanilla $00-$1D)
                if bank >= 0x1E:
                    purpose = ""
                    # Check preceding comment for purpose (truncate to 80 chars)
                    if i > 0:
                        pm = PURPOSE_COMMENT_RE.search(lines[i - 1])
                        if pm:
                            text = pm.group(1).strip()
                            # Skip separator lines and @hook annotations
                            if not text.startswith(("===", "---", "@hook", "***")):
                                purpose = text[:80]

                    # Look for assert pc() <= $XXXXXX to find end bound
                    end_addr = None
                    for j in range(i + 1, min(i + 2000, len(lines))):
                        am = ASSERT_PC_RE.search(lines[j])
                        if am:
                            end_addr = int(am.group(1), 16)
                            break
                        # Stop at next org in a different bank
                        next_org = ORG_BANK_RE.match(lines[j])
                        if next_org:
                            next_addr = int(next_org.group(1), 16)
                            next_bank = (next_addr >> 16) & 0xFF
                            if next_bank != bank:
                                break

                    entry = {
                        "start": f"0x{addr:06X}",
                        "source": f"{rel}:{i + 1}",
                        "purpose": purpose,
                    }
                    if end_addr:
                        entry["end"] = f"0x{end_addr:06X}"

                    bank_sources.setdefault(bank, []).append(entry)

            # Check for freedata bank $XX
            fm = FREEDATA_BANK_RE.match(line)
            if fm:
                bank = int(fm.group(1), 16)
                if bank >= 0x1E:
                    entry = {
                        "start": f"0x{bank:02X}8000",
                        "source": f"{rel}:{i + 1}",
                        "purpose": "freedata (asar auto-allocated)",
                    }
                    bank_sources.setdefault(bank, []).append(entry)

    # Known shared banks: yaze writes base data, ASM re-patches parts.
    # These need special handling — yaze can write, but must re-run asar after.
    SHARED_BANKS = {
        0x28: "ZSCustomOverworld (yaze writes overworld data, ASM patches hooks on top)",
        0x20: "Overworld map data (shared between yaze overworld editor and ASM)",
    }

    # Banks that are NOT in the dev ROM at all (asar creates them via ROM expansion)
    # These exist only in the patched ROM.
    EXPANSION_BANKS = set(range(0x30, 0x43))  # $30-$42 are ROM expansion

    # Flatten into a sorted list with ownership classification
    result = []
    for bank in sorted(bank_sources):
        regions = bank_sources[bank]
        if bank in SHARED_BANKS:
            ownership = "shared"
            ownership_note = SHARED_BANKS[bank]
        elif bank in EXPANSION_BANKS:
            ownership = "asm_expansion"
            ownership_note = "ROM expansion bank — does not exist in dev ROM, created by asar"
        elif bank == 0x7E:
            ownership = "ram"
            ownership_note = "WRAM definitions (not ROM data)"
        elif bank >= 0x80:
            ownership = "mirror"
            ownership_note = "HiROM mirror of vanilla bank"
        else:
            ownership = "asm_owned"
            ownership_note = "Fully owned by ASM hack"

        entry: dict = {
            "bank": f"0x{bank:02X}",
            "bank_start": f"0x{bank:02X}8000",
            "bank_end": f"0x{bank:02X}FFFF",
            "ownership": ownership,
            "ownership_note": ownership_note,
            "regions": regions,
        }
        result.append(entry)
    return result


# ---------------------------------------------------------------------------
# Message layout detection
# ---------------------------------------------------------------------------

def scan_message_layout(root: Path) -> dict:
    """Extract expanded message range and individual message IDs."""
    msg_file = root / "Core" / "message.asm"
    if not msg_file.exists():
        return {}

    text = msg_file.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    messages: list[dict] = []
    data_start = None
    data_end = None
    hook_address = None
    last_org_addr = None

    for i, line in enumerate(lines):
        # Track org directives so we can associate inline `JML MessageExpand`.
        m = ORG_BANK_RE.match(line)
        if m:
            addr = int(m.group(1), 16)
            last_org_addr = addr
            # Known canonical hook location (LoROM): $0ED436
            if addr == 0x0ED436:
                hook_address = f"0x{addr:06X}"

        # If the hook is written as `org $0ED436` followed by `JML MessageExpand`,
        # bind the hook address to the most recent org in bank $0E.
        if "JML MessageExpand" in line and last_org_addr is not None:
            if ((last_org_addr >> 16) & 0xFF) == 0x0E:
                hook_address = f"0x{last_org_addr:06X}"

        # Find message labels
        ml = MESSAGE_LABEL_RE.match(line)
        if ml:
            msg_id = int(ml.group(1), 16)
            # Read comment for purpose
            purpose = ""
            cm = PURPOSE_COMMENT_RE.search(line)
            if cm:
                purpose = cm.group(1).strip()
            messages.append({
                "id": f"0x{msg_id:03X}",
                "id_dec": msg_id,
                "label": f"Message_{msg_id:03X}",
                "purpose": purpose,
                "line": i + 1,
            })

        # Find data start (MessageExpandedData label)
        if "MessageExpandedData:" in line:
            # The data region starts at this label's PC,
            # which is shortly after org $2F8000
            data_start = "MessageExpandedData"

        # Find assert at end of message bank
        am = ASSERT_PC_RE.search(line)
        if am:
            data_end = f"0x{int(am.group(1), 16):06X}"

    if not messages:
        return {}

    msg_ids = [m["id_dec"] for m in messages]
    # Clean up messages for output (remove id_dec helper)
    for m in messages:
        del m["id_dec"]

    return {
        "hook_address": hook_address,
        "data_bank": "0x2F",
        "data_start": "0x2F8000",
        "data_end": data_end,
        "expanded_range": {
            "first": f"0x{min(msg_ids):03X}",
            "last": f"0x{max(msg_ids):03X}",
            "count": len(messages),
        },
        "vanilla_count": 397,
        "messages": messages,
    }


# ---------------------------------------------------------------------------
# Room tag extraction
# ---------------------------------------------------------------------------

def scan_room_tags(root: Path, defines: dict[str, int]) -> list[dict]:
    """Extract room tag mappings from org $01CCxx directives."""
    tags: dict[int, dict] = {}

    for asm_path in root.rglob("*.asm"):
        if _should_skip(asm_path):
            continue
        try:
            lines = asm_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue

        rel = str(asm_path.relative_to(root))

        # Track if/endif nesting for feature-gated tags
        in_gated_block = False
        gate_flag = None

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Track feature flag guards
            if stripped.startswith("if "):
                fm = re.search(r"!(ENABLE_\w+)\s*==\s*1", stripped)
                if fm:
                    in_gated_block = True
                    gate_flag = fm.group(1)
            elif stripped.startswith("endif"):
                in_gated_block = False
                gate_flag = None

            m = ROOM_TAG_RE.match(line)
            if not m:
                continue

            offset = int(m.group(1), 16)
            addr = 0x01CC00 + offset
            # Tag ID = offset / 4 + 0x33
            tag_id = offset // 4 + 0x33

            # Extract hook name from @hook annotation
            name = f"Tag_0x{tag_id:02X}"
            nm = HOOK_NAME_RE.search(line)
            if nm:
                name = nm.group(1)

            # Extract purpose from comment
            purpose = ""
            # Check current line and preceding line
            for check_line in [line, lines[i - 1] if i > 0 else ""]:
                cm = PURPOSE_COMMENT_RE.search(check_line)
                if cm:
                    text = cm.group(1).strip()
                    # Skip pure @hook annotations
                    if text.startswith("@hook"):
                        continue
                    # Strip trailing @hook annotation from inline comments
                    if "; @hook" in check_line:
                        text = text.split("@hook")[0].strip().rstrip(";").strip()
                    if text:
                        purpose = text
                        break

            entry = {
                "tag_id": f"0x{tag_id:02X}",
                "address": f"0x{addr:06X}",
                "name": name,
                "source": f"{rel}:{i + 1}",
            }
            if purpose:
                entry["purpose"] = purpose
            if in_gated_block and gate_flag:
                flag_value = defines.get(gate_flag, 0)
                entry["feature_flag"] = f"!{gate_flag}"
                entry["enabled"] = flag_value == 1

            # Keep highest-detail entry per tag
            if tag_id not in tags or len(entry) > len(tags[tag_id]):
                tags[tag_id] = entry

    return [tags[k] for k in sorted(tags)]


# ---------------------------------------------------------------------------
# Feature flag extraction
# ---------------------------------------------------------------------------

def scan_feature_flags(root: Path) -> list[dict]:
    """Extract feature flags from macros.asm and feature_flags.asm."""
    flags: dict[str, dict] = {}

    for rel in ("Util/macros.asm", "Config/feature_flags.asm"):
        path = root / rel
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for i, line in enumerate(lines):
            m = FEATURE_FLAG_RE.match(line)
            if not m:
                continue
            name = m.group(1)
            value = int(m.group(2))
            # feature_flags.asm overrides macros.asm (read second)
            flags[name] = {
                "name": f"!{name}",
                "value": value,
                "enabled": value == 1,
                "source": f"{rel}:{i + 1}",
            }

    return [flags[k] for k in sorted(flags)]


# ---------------------------------------------------------------------------
# SRAM variable extraction
# ---------------------------------------------------------------------------

@dataclass
class SramVariable:
    name: str
    address: int
    purpose: str = ""
    bits: list = field(default_factory=list)


def scan_sram_layout(root: Path) -> list[dict]:
    """Extract custom SRAM variable definitions from Core/sram.asm."""
    sram_file = root / "Core" / "sram.asm"
    if not sram_file.exists():
        return []

    lines = sram_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    variables: dict[int, SramVariable] = {}
    current_section = ""

    for i, line in enumerate(lines):
        # Track section headers
        if line.strip().startswith("; ---"):
            # Next non-empty, non-separator line is the section name
            for j in range(i + 1, min(i + 3, len(lines))):
                sec_line = lines[j].strip()
                if sec_line.startswith(";") and not sec_line.startswith("; ---"):
                    current_section = sec_line.lstrip("; ").strip()
                    break

        # Match SRAM variable definitions
        m = SRAM_VAR_RE.match(line)
        if m:
            name = m.group(1)
            addr = int(m.group(2), 16)
            # Extract inline comment for purpose
            purpose = ""
            cm = PURPOSE_COMMENT_RE.search(line)
            if cm:
                purpose = cm.group(1).strip()

            variables[addr] = SramVariable(
                name=name,
                address=addr,
                purpose=purpose,
            )

        # Match bit constants and attach to the most recent section's variable
        bm = SRAM_BIT_RE.match(line)
        if bm:
            bit_name = bm.group(1)
            bit_value = int(bm.group(2), 16)
            purpose = ""
            cm = PURPOSE_COMMENT_RE.search(line)
            if cm:
                purpose = cm.group(1).strip()

            # Find the variable this bit belongs to by section context
            # Heuristic: bits defined after a variable belong to the nearest
            # preceding variable in the same section
            # We'll attach to the last-defined variable
            if variables:
                last_var = max(variables.values(), key=lambda v: v.address)
                # Only attach if this looks like it belongs (same naming prefix)
                last_var.bits.append({
                    "name": f"!{bit_name}",
                    "value": f"0x{bit_value:02X}",
                    "purpose": purpose,
                })

    # Convert to output format, sorted by address
    result = []
    for addr in sorted(variables):
        var = variables[addr]
        entry: dict = {
            "name": var.name,
            "address": f"0x{var.address:06X}",
        }
        if var.purpose:
            entry["purpose"] = var.purpose
        if var.bits:
            entry["bits"] = var.bits
        result.append(entry)

    return result


# ---------------------------------------------------------------------------
# Protected region computation
# ---------------------------------------------------------------------------

def _pc_to_snes(pc_address: int) -> int:
    """Convert an unheadered PC offset to a canonical LoROM SNES address."""
    if not 0 <= pc_address < 0x400000:
        raise ManifestGenerationError(
            f"PC address 0x{pc_address:X} is outside canonical LoROM"
        )
    snes_address = (
        ((pc_address << 1) & 0x7F0000)
        | (pc_address & 0x7FFF)
        | 0x8000
    )
    if _snes_to_pc(snes_address) != pc_address:
        raise ManifestGenerationError(
            f"PC address 0x{pc_address:X} does not round-trip through LoROM"
        )
    return snes_address


def _snes_to_pc(snes_address: int) -> int:
    """Convert a mapped LoROM SNES address to an unheadered PC offset."""
    if not 0 <= snes_address <= 0xFFFFFF:
        raise ManifestGenerationError(
            f"SNES address 0x{snes_address:X} is outside 24-bit address space"
        )
    canonical = snes_address & 0x7FFFFF
    bank = (canonical >> 16) & 0x7F
    if bank in (0x7E, 0x7F) or (canonical & 0xFFFF) < 0x8000:
        raise ManifestGenerationError(
            f"SNES address 0x{snes_address:06X} is not mapped LoROM"
        )
    return ((canonical & 0x7F0000) >> 1) | (canonical & 0x7FFF)


def _canonicalize_hook_address(snes_address: int) -> int:
    """Map legacy/mirrored hook syntax to a canonical mapped LoROM address."""
    if not 0 <= snes_address <= 0xFFFFFF:
        raise ManifestGenerationError(
            f"hook address 0x{snes_address:X} is outside 24-bit address space"
        )
    canonical = snes_address & 0x7FFFFF
    bank = (canonical >> 16) & 0x7F
    if bank in (0x7E, 0x7F):
        raise ManifestGenerationError(
            f"hook address 0x{snes_address:06X} resolves to WRAM"
        )
    pc_address = (
        ((canonical & 0x7F0000) >> 1)
        | (canonical & 0x7FFF)
    )
    return _pc_to_snes(pc_address)


def compute_protected_regions(hooks: list[HookEntry]) -> list[dict]:
    """Group hooks into contiguous canonical LoROM protected ranges."""
    if not hooks:
        return []

    # Estimate size of each hook (conservative: 4 bytes for JML/JSL, 1-8 for data/patch)
    SIZE_ESTIMATE = {
        "jsl": 4,
        "jml": 4,
        "jsr": 3,
        "jmp": 3,
        "data": 8,   # conservative
        "patch": 4,   # conservative
    }

    # Manifest v3 requires mapped canonical LoROM endpoints. Some legacy Asar
    # sources use a low-half spelling (notably $1E7F21); normalize through the
    # underlying PC offset before sorting and merging.
    hook_spans = []
    for hook in hooks:
        canonical_start = _canonicalize_hook_address(hook.address)
        start_pc = _snes_to_pc(canonical_start)
        end_pc = start_pc + SIZE_ESTIMATE.get(hook.kind, 4)
        hook_spans.append((start_pc, end_pc, hook))
    hook_spans.sort(key=lambda item: item[0])

    regions = []
    current_start_pc, current_end_pc, first_hook = hook_spans[0]
    current_hooks = [first_hook]

    for hook_start_pc, hook_end_pc, hook in hook_spans[1:]:
        # Merge if within 16 physical ROM bytes of the previous region.
        if hook_start_pc <= current_end_pc + 16:
            current_end_pc = max(current_end_pc, hook_end_pc)
            current_hooks.append(hook)
        else:
            regions.append({
                "start": f"0x{_pc_to_snes(current_start_pc):06X}",
                "end": f"0x{_pc_to_snes(current_end_pc):06X}",
                "size": current_end_pc - current_start_pc,
                "hook_count": len(current_hooks),
                "module": current_hooks[0].module,
            })
            current_start_pc = hook_start_pc
            current_end_pc = hook_end_pc
            current_hooks = [hook]

    regions.append({
        "start": f"0x{_pc_to_snes(current_start_pc):06X}",
        "end": f"0x{_pc_to_snes(current_end_pc):06X}",
        "size": current_end_pc - current_start_pc,
        "hook_count": len(current_hooks),
        "module": current_hooks[0].module,
    })

    return regions


# ---------------------------------------------------------------------------
# Live dungeon layout extraction
# ---------------------------------------------------------------------------

def _require_rom_span(data: bytes, pc_address: int, size: int, label: str) -> None:
    if pc_address < 0 or size < 0 or pc_address + size > len(data):
        raise ManifestGenerationError(
            f"{label} PC span [0x{pc_address:X}, 0x{pc_address + size:X}) "
            f"exceeds editable ROM size 0x{len(data):X}"
        )


def _read_u8(data: bytes, pc_address: int, label: str) -> int:
    _require_rom_span(data, pc_address, 1, label)
    return data[pc_address]


def _read_u16_le(data: bytes, pc_address: int, label: str) -> int:
    _require_rom_span(data, pc_address, 2, label)
    return data[pc_address] | (data[pc_address + 1] << 8)


def _read_u24_le(data: bytes, pc_address: int, label: str) -> int:
    _require_rom_span(data, pc_address, 3, label)
    return (
        data[pc_address]
        | (data[pc_address + 1] << 8)
        | (data[pc_address + 2] << 16)
    )


def _snes_hex(address: int) -> str:
    return f"0x{address:06X}"


def _pc_range_json(start: int, end: int) -> dict[str, str]:
    if start >= end:
        raise ManifestGenerationError(
            f"invalid empty/reversed PC range [0x{start:X}, 0x{end:X})"
        )
    return {
        "start": _snes_hex(_pc_to_snes(start)),
        "end": _snes_hex(_pc_to_snes(end)),
    }


def _range_contains(outer: tuple[int, int], inner: tuple[int, int]) -> bool:
    return outer[0] <= inner[0] and inner[1] <= outer[1]


def _validate_regions(
    data: bytes,
    stream_name: str,
    data_regions: tuple[tuple[int, int], ...],
    allocation_regions: tuple[tuple[int, int], ...],
) -> None:
    if not data_regions or not allocation_regions:
        raise ManifestGenerationError(
            f"{stream_name} data/allocation regions must be non-empty"
        )

    sorted_data = sorted(data_regions)
    for index, (start, end) in enumerate(sorted_data):
        if start >= end:
            raise ManifestGenerationError(
                f"{stream_name} data region {index} is empty or reversed"
            )
        _require_rom_span(
            data, start, end - start, f"{stream_name} data region {index}"
        )
        _pc_to_snes(start)
        _pc_to_snes(end)
        if index and start < sorted_data[index - 1][1]:
            raise ManifestGenerationError(
                f"{stream_name} data regions overlap at PC 0x{start:X}"
            )

    sorted_allocations = sorted(allocation_regions)
    for index, allocation in enumerate(sorted_allocations):
        start, end = allocation
        if start >= end:
            raise ManifestGenerationError(
                f"{stream_name} allocation region {index} is empty or reversed"
            )
        if not any(_range_contains(region, allocation) for region in data_regions):
            raise ManifestGenerationError(
                f"{stream_name} allocation [0x{start:X}, 0x{end:X}) is not "
                "contained in a data region"
            )
        if index and start < sorted_allocations[index - 1][1]:
            raise ManifestGenerationError(
                f"{stream_name} allocation regions overlap at PC 0x{start:X}"
            )


def _pointer_pc_in_regions(
    pointer_pc: int,
    regions: tuple[tuple[int, int], ...],
) -> bool:
    return any(start <= pointer_pc < end for start, end in regions)


def _validate_disjoint_named_ranges(
    ranges: list[tuple[str, int, int]],
    description: str,
) -> None:
    sorted_ranges = sorted(ranges, key=lambda item: (item[1], item[2]))
    for previous, current in zip(sorted_ranges, sorted_ranges[1:]):
        if current[1] < previous[2]:
            raise ManifestGenerationError(
                f"{description} overlap: {previous[0]} "
                f"[0x{previous[1]:X}, 0x{previous[2]:X}) conflicts with "
                f"{current[0]} [0x{current[1]:X}, 0x{current[2]:X})"
            )


def _derive_dungeon_stream_regions(data: bytes) -> dict:
    # Objects use a 24-bit pointer table whose address is itself stored in a
    # long operand. Every live pointer must remain inside a known OOS pool.
    object_table_raw = _read_u24_le(
        data,
        OBJECT_TABLE_POINTER_OPERAND_PC,
        "object pointer-table operand",
    )
    object_table_pc = _snes_to_pc(object_table_raw)
    object_table_snes = _pc_to_snes(object_table_pc)
    object_table_size = DUNGEON_ROOM_COUNT * 3
    _require_rom_span(
        data, object_table_pc, object_table_size, "object pointer table"
    )
    _validate_regions(
        data,
        "objects",
        OBJECT_DATA_REGIONS_PC,
        OBJECT_ALLOCATION_REGIONS_PC,
    )
    for room_id in range(DUNGEON_ROOM_COUNT):
        pointer_pc = object_table_pc + room_id * 3
        object_pointer = _read_u24_le(
            data, pointer_pc, f"object pointer for room 0x{room_id:03X}"
        )
        object_data_pc = _snes_to_pc(object_pointer)
        if not _pointer_pc_in_regions(object_data_pc, OBJECT_DATA_REGIONS_PC):
            raise ManifestGenerationError(
                f"object pointer for room 0x{room_id:03X} resolves to PC "
                f"0x{object_data_pc:X}, outside declared object data regions"
            )

    # Sprites use two-byte pointers fixed to bank $09.
    sprite_table_low = _read_u16_le(
        data,
        SPRITE_TABLE_POINTER_OPERAND_PC,
        "sprite pointer-table operand",
    )
    sprite_table_snes = 0x090000 | sprite_table_low
    sprite_table_pc = _snes_to_pc(sprite_table_snes)
    sprite_table_size = DUNGEON_ROOM_COUNT * 2
    _require_rom_span(
        data, sprite_table_pc, sprite_table_size, "sprite pointer table"
    )
    sprite_pointers_pc: list[int] = []
    for room_id in range(DUNGEON_ROOM_COUNT):
        pointer_low = _read_u16_le(
            data,
            sprite_table_pc + room_id * 2,
            f"sprite pointer for room 0x{room_id:03X}",
        )
        sprite_pointers_pc.append(_snes_to_pc(0x090000 | pointer_low))
    sprite_data_start_pc = sprite_table_pc + sprite_table_size
    minimum_sprite_pointer_pc = min(sprite_pointers_pc)
    if minimum_sprite_pointer_pc < sprite_data_start_pc:
        raise ManifestGenerationError(
            f"minimum sprite pointer PC 0x{minimum_sprite_pointer_pc:X} "
            f"precedes pointer-table end PC 0x{sprite_data_start_pc:X}"
        )
    sprite_regions = ((sprite_data_start_pc, SPRITE_DATA_END_PC),)
    _validate_regions(data, "sprites", sprite_regions, sprite_regions)
    for room_id, pointer_pc in enumerate(sprite_pointers_pc):
        if not _pointer_pc_in_regions(pointer_pc, sprite_regions):
            raise ManifestGenerationError(
                f"sprite pointer for room 0x{room_id:03X} resolves to PC "
                f"0x{pointer_pc:X}, outside sprite data region"
            )

    # Pot-item pointers are a fixed table of bank-$01 words. Yaze inventories
    # all 296 entries, so an unmapped word must fail here rather than produce a
    # manifest that its allocator cannot consume.
    pot_table_size = DUNGEON_ROOM_COUNT * 2
    _require_rom_span(
        data, POT_POINTER_TABLE_PC, pot_table_size, "pot-item pointer table"
    )
    pot_pointers_pc: list[int] = []
    for room_id in range(DUNGEON_ROOM_COUNT):
        pointer_low = _read_u16_le(
            data,
            POT_POINTER_TABLE_PC + room_id * 2,
            f"pot-item pointer for room 0x{room_id:03X}",
        )
        if pointer_low < 0x8000:
            raise ManifestGenerationError(
                f"pot-item pointer for room 0x{room_id:03X} is unmapped "
                f"bank-$01 value 0x{pointer_low:04X}"
            )
        pot_pointers_pc.append(_snes_to_pc(0x010000 | pointer_low))
    pot_data_start_pc = min(pot_pointers_pc)
    pot_regions = ((pot_data_start_pc, POT_DATA_END_PC),)
    _validate_regions(data, "pot_items", pot_regions, pot_regions)
    for room_id, pointer_pc in enumerate(pot_pointers_pc):
        if not _pointer_pc_in_regions(pointer_pc, pot_regions):
            raise ManifestGenerationError(
                f"pot-item pointer for room 0x{room_id:03X} resolves to PC "
                f"0x{pointer_pc:X}, outside pot-item data region"
            )

    stream_data_regions = {
        "objects": OBJECT_DATA_REGIONS_PC,
        "sprites": sprite_regions,
        "pot_items": pot_regions,
    }
    pointer_tables = {
        "objects": (object_table_pc, object_table_pc + object_table_size),
        "sprites": (sprite_table_pc, sprite_table_pc + sprite_table_size),
        "pot_items": (
            POT_POINTER_TABLE_PC,
            POT_POINTER_TABLE_PC + pot_table_size,
        ),
    }
    occupied_ranges = [
        (f"{name}.pointer_table", start, end)
        for name, (start, end) in pointer_tables.items()
    ]
    occupied_ranges.extend(
        (f"{name}.data_regions[{index}]", start, end)
        for name, ranges in stream_data_regions.items()
        for index, (start, end) in enumerate(ranges)
    )
    occupied_ranges.extend(
        (
            ("objects.pointer_source", OBJECT_TABLE_POINTER_OPERAND_PC,
             OBJECT_TABLE_POINTER_OPERAND_PC + 3),
            ("sprites.pointer_source", SPRITE_TABLE_POINTER_OPERAND_PC,
             SPRITE_TABLE_POINTER_OPERAND_PC + 2),
            ("objects.door_pointer_table", 0xF83C0,
             0xF83C0 + DUNGEON_ROOM_COUNT * 3),
        )
    )
    _validate_disjoint_named_ranges(
        occupied_ranges, "dungeon stream pointer/data ranges"
    )
    _validate_disjoint_named_ranges(
        [
            ("objects.allocation_regions[0]", *OBJECT_ALLOCATION_REGIONS_PC[0]),
            ("sprites.allocation_regions[0]", *sprite_regions[0]),
            ("pot_items.allocation_regions[0]", *pot_regions[0]),
        ],
        "dungeon stream allocation ranges",
    )

    return {
        "objects": {
            "pointer_table": _snes_hex(object_table_snes),
            "pointer_count": DUNGEON_ROOM_COUNT,
            "pointer_encoding": "long24",
            "strategy": "copy_on_write",
            "data_regions": [
                _pc_range_json(start, end)
                for start, end in OBJECT_DATA_REGIONS_PC
            ],
            "allocation_regions": [
                _pc_range_json(start, end)
                for start, end in OBJECT_ALLOCATION_REGIONS_PC
            ],
        },
        "sprites": {
            "pointer_table": _snes_hex(_pc_to_snes(sprite_table_pc)),
            "pointer_count": DUNGEON_ROOM_COUNT,
            "pointer_encoding": "bank16",
            "pointer_bank": "0x09",
            "strategy": "copy_on_write",
            "data_regions": [
                _pc_range_json(start, end) for start, end in sprite_regions
            ],
            "allocation_regions": [
                _pc_range_json(start, end) for start, end in sprite_regions
            ],
        },
        "pot_items": {
            "pointer_table": _snes_hex(_pc_to_snes(POT_POINTER_TABLE_PC)),
            "pointer_count": DUNGEON_ROOM_COUNT,
            "pointer_encoding": "bank16",
            "pointer_bank": "0x01",
            "strategy": "repack_all",
            "data_regions": [
                _pc_range_json(start, end) for start, end in pot_regions
            ],
            "allocation_regions": [
                _pc_range_json(start, end) for start, end in pot_regions
            ],
        },
    }


def _find_custom_collision_stream_end(
    data: bytes, room_id: int, start_pc: int
) -> int:
    """Return the exclusive end of one validated custom-collision stream."""
    def require_stream_span(cursor: int, size: int, label: str) -> None:
        if (
            cursor < CUSTOM_COLLISION_DATA_START_PC
            or size < 0
            or cursor + size > CUSTOM_COLLISION_DATA_END_PC
        ):
            raise ManifestGenerationError(
                f"{label} for room 0x{room_id:03X} crosses reserved "
                f"WaterFill data at PC 0x{CUSTOM_COLLISION_DATA_END_PC:X}"
            )
        _require_rom_span(data, cursor, size, label)

    cursor = start_pc
    single_tile_mode = False
    while cursor < CUSTOM_COLLISION_DATA_END_PC:
        require_stream_span(cursor, 2, "custom collision stream word")
        word = _read_u16_le(
            data, cursor, f"custom collision stream for room 0x{room_id:03X}"
        )
        cursor += 2
        if word == 0xFFFF:
            return cursor
        if word == 0xF0F0:
            single_tile_mode = True
            continue
        if single_tile_mode:
            require_stream_span(cursor, 1, "custom collision tile")
            cursor += 1
            continue

        require_stream_span(cursor, 2, "custom collision rectangle dimensions")
        width = _read_u8(
            data, cursor, f"custom collision width for room 0x{room_id:03X}"
        )
        height = _read_u8(
            data,
            cursor + 1,
            f"custom collision height for room 0x{room_id:03X}",
        )
        cursor += 2
        payload_size = width * height
        require_stream_span(cursor, payload_size, "custom collision rectangle")
        cursor += payload_size

    raise ManifestGenerationError(
        f"custom collision stream for room 0x{room_id:03X} is unterminated "
        f"before reserved WaterFill data at PC 0x{CUSTOM_COLLISION_DATA_END_PC:X}"
    )


def _derive_editor_managed_regions(data: bytes) -> dict:
    """Derive exact dungeon metadata/collision ranges that yaze owns."""
    header_table_raw = _read_u24_le(
        data,
        ROOM_HEADER_TABLE_POINTER_OPERAND_PC,
        "room-header pointer-table operand",
    )
    header_table_pc = _snes_to_pc(header_table_raw)
    header_table_size = DUNGEON_ROOM_COUNT * 2
    _require_rom_span(
        data, header_table_pc, header_table_size, "room-header pointer table"
    )
    header_bank = _read_u8(
        data, ROOM_HEADER_BANK_OPERAND_PC, "room-header data bank operand"
    )
    header_starts_pc: list[int] = []
    for room_id in range(DUNGEON_ROOM_COUNT):
        pointer_low = _read_u16_le(
            data,
            header_table_pc + room_id * 2,
            f"room-header pointer for room 0x{room_id:03X}",
        )
        if pointer_low < 0x8000:
            raise ManifestGenerationError(
                f"room-header pointer for room 0x{room_id:03X} is unmapped "
                f"value 0x{pointer_low:04X}"
            )
        header_pc = _snes_to_pc((header_bank << 16) | pointer_low)
        _require_rom_span(
            data,
            header_pc,
            ROOM_HEADER_SIZE,
            f"room header for room 0x{room_id:03X}",
        )
        header_starts_pc.append(header_pc)
    room_header_region = (
        min(header_starts_pc),
        max(start + ROOM_HEADER_SIZE for start in header_starts_pc),
    )

    message_ids_region = (
        DUNGEON_MESSAGE_IDS_PC,
        DUNGEON_MESSAGE_IDS_PC + DUNGEON_ROOM_COUNT * 2,
    )
    _require_rom_span(
        data,
        message_ids_region[0],
        message_ids_region[1] - message_ids_region[0],
        "dungeon message-ID table",
    )

    collision_pointer_table_end = (
        CUSTOM_COLLISION_POINTER_TABLE_PC + DUNGEON_ROOM_COUNT * 3
    )
    _require_rom_span(
        data,
        CUSTOM_COLLISION_POINTER_TABLE_PC,
        collision_pointer_table_end - CUSTOM_COLLISION_POINTER_TABLE_PC,
        "custom-collision pointer table",
    )
    _require_rom_span(
        data,
        CUSTOM_COLLISION_DATA_START_PC,
        CUSTOM_COLLISION_DATA_END_PC - CUSTOM_COLLISION_DATA_START_PC,
        "custom-collision data region",
    )
    for room_id in range(DUNGEON_ROOM_COUNT):
        raw_pointer = _read_u24_le(
            data,
            CUSTOM_COLLISION_POINTER_TABLE_PC + room_id * 3,
            f"custom-collision pointer for room 0x{room_id:03X}",
        )
        if raw_pointer == 0:
            continue
        collision_pc = _snes_to_pc(raw_pointer)
        if not (
            CUSTOM_COLLISION_DATA_START_PC
            <= collision_pc
            < CUSTOM_COLLISION_DATA_END_PC
        ):
            raise ManifestGenerationError(
                f"custom-collision pointer for room 0x{room_id:03X} resolves "
                f"to PC 0x{collision_pc:X}, outside the editor-owned region"
            )
        _find_custom_collision_stream_end(data, room_id, collision_pc)

    named_regions = [
        ("dungeon_message_ids", *message_ids_region),
        ("room_headers", *room_header_region),
        (
            "custom_collision_pointers",
            CUSTOM_COLLISION_POINTER_TABLE_PC,
            collision_pointer_table_end,
        ),
        (
            "custom_collision_data",
            CUSTOM_COLLISION_DATA_START_PC,
            CUSTOM_COLLISION_DATA_END_PC,
        ),
    ]
    _validate_disjoint_named_ranges(named_regions, "editor-managed regions")

    return {
        "description": (
            "Exact yaze-owned dungeon metadata and custom-collision ranges. "
            "The WaterFill tail beginning at $25:E000 remains ASM-owned."
        ),
        "regions": [
            _pc_range_json(start, end)
            for _, start, end in sorted(named_regions, key=lambda item: item[1])
        ],
    }


# ---------------------------------------------------------------------------
# Main manifest generation
# ---------------------------------------------------------------------------

def _manifest_path(root: Path, path: Path) -> str:
    """Return a portable repo-relative path when possible."""
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    if resolved_path.is_relative_to(resolved_root):
        return str(resolved_path.relative_to(resolved_root))
    return str(resolved_path)


def generate_manifest(
    root: Path,
    rom_path: Optional[Path] = None,
    patched_rom_path: Optional[Path] = None,
) -> dict:
    """Generate the complete hack manifest."""
    import hashlib

    # Load defines for conditional compilation evaluation
    defines = _load_global_defines(root)

    # Scan hooks (reuse existing infrastructure)
    hooks = scan_hooks(root)

    # Build manifest sections
    manifest: dict = {
        "manifest_version": 3,
        "hack_name": "Oracle of Secrets",
        "hack_version": "dev",
        "generator": "generate_hack_manifest.py",
    }

    editable_rom_path = rom_path or (root / "Roms" / "oos168.sfc")
    selected_patched_rom_path = (
        patched_rom_path or (root / "Roms" / "oos168x.sfc")
    )

    # Build pipeline model
    manifest["build_pipeline"] = {
        "description": "Yaze edits the dev ROM; asar patches it to produce the patched ROM. They share the same base file.",
        "dev_rom": _manifest_path(root, editable_rom_path),
        "patched_rom": _manifest_path(root, selected_patched_rom_path),
        "assembler": "asar",
        "entry_point": "Oracle_main.asm",
        "build_script": "Scripts/Build/build_rom.sh",
        "flow": [
            "1. Yaze edits dev ROM (room data, sprites, palettes, messages)",
            "2. asar reads dev ROM + ASM sources",
            "3. asar writes patched ROM with all org/freedata applied",
            "4. Patched ROM is the playable output",
        ],
        "key_insight": "Hook addresses in the dev ROM are overwritten by asar on every build. Yaze edits to these addresses are silently lost. The manifest identifies which addresses belong to which layer.",
    }

    # ROM metadata always identifies the editable base. The patched output is
    # build-only and is deliberately not accepted as the project hash.
    rom_meta: dict = {}
    editable_rom_data: Optional[bytes] = None
    if rom_path is not None:
        if not rom_path.is_file():
            raise ManifestGenerationError(
                f"editable ROM does not exist: {rom_path}"
            )
        try:
            editable_rom_data = rom_path.read_bytes()
        except OSError as exc:
            raise ManifestGenerationError(
                f"unable to read editable ROM {rom_path}: {exc}"
            ) from exc
        editable_sha1 = hashlib.sha1(editable_rom_data).hexdigest()
        rom_meta = {
            "path": _manifest_path(root, rom_path),
            "sha1": editable_sha1,
            "size": len(editable_rom_data),
            "dev_rom_sha1": editable_sha1,
            "dev_rom_size": len(editable_rom_data),
        }
    manifest["rom"] = rom_meta

    # Allocation metadata and v3 editor exemptions are derived from the live
    # editable ROM, never from the Asar-patched output.
    if editable_rom_data is not None:
        manifest["dungeon_stream_regions"] = _derive_dungeon_stream_regions(
            editable_rom_data
        )
        manifest["editor_managed_regions"] = _derive_editor_managed_regions(
            editable_rom_data
        )

    # Protected regions — these are hook addresses in VANILLA banks.
    # Asar overwrites these on build, so yaze edits here are lost.
    # Separate from owned_banks which are entirely ASM-owned.
    vanilla_hooks = [h for h in hooks if h.address < 0x1E8000]
    expanded_hooks = [h for h in hooks if h.address >= 0x1E8000]
    protected = compute_protected_regions(vanilla_hooks) if vanilla_hooks else []
    manifest["protected_regions"] = {
        "description": "Hook addresses within vanilla ROM banks ($00-$1D). Asar patches these on every build, so yaze edits at these addresses are silently overwritten. Yaze should either skip these during save or warn the user.",
        "count": len(protected),
        "vanilla_hook_count": len(vanilla_hooks),
        "expanded_hook_count": len(expanded_hooks),
        "total_hooks": len(hooks),
        "regions": protected,
    }

    # Bank ownership — expanded banks with ownership classification
    banks = scan_bank_ownership(root)
    manifest["owned_banks"] = {
        "description": "Expanded ROM banks with ownership classification. 'asm_owned' banks are fully owned by ASM. 'shared' banks (e.g., $28 ZSCustomOverworld) contain data that yaze writes AND ASM patches on top — yaze can edit these but must rebuild after. 'asm_expansion' banks only exist in the patched ROM.",
        "ownership_types": {
            "asm_owned": "Fully owned by ASM hack — yaze should not write here",
            "shared": "Both yaze and ASM write — yaze edits base data, ASM patches hooks on top. Must rebuild after yaze save.",
            "asm_expansion": "ROM expansion bank — only exists in patched ROM, not in dev ROM",
            "ram": "WRAM variable definitions (not ROM data)",
            "mirror": "HiROM mirror — ASM patches vanilla bank via mirror address",
        },
        "banks": banks,
    }

    # Message layout — the expanded message data lives in bank $2F (ASM-owned),
    # but the vanilla message region ($0E) is shared: yaze can edit vanilla messages
    # in the dev ROM, and the ASM expansion hook redirects reads for IDs >= $18D.
    messages = scan_message_layout(root)
    if messages:
        manifest["messages"] = {
            "description": "Expanded message system. Vanilla messages ($000-$18C) live in bank $0E of the dev ROM — yaze can edit these. Expanded messages ($18D+) live in bank $2F, owned by ASM. The hook at $0ED436 redirects message reads for expanded IDs. Direct editor or CLI writes to expanded IDs are not durable because the next ASM rebuild replaces bank $2F.",
            "editing_guidance": {
                "vanilla_safe": "Message IDs $000-$18C can be edited in the dev ROM via yaze",
                "expanded_asm_owned": "Message IDs $18D+ are in ASM-owned bank $2F; edit Core/message.asm, rebuild with Scripts/Build/build_rom.sh 168, then reopen or reload Roms/oos168x.sfc for inspection. Do not edit the patched ROM directly.",
                "hook_address": "$0ED436 (do not overwrite — asar patches this)",
            },
            **messages,
        }

    # Room tags — the dispatch table at $01CC00-$01CC5A is in vanilla bank $01.
    # Asar patches specific 4-byte slots (JML instructions). Yaze's room editor
    # assigns tag IDs to rooms; this manifest tells yaze what each tag ID means.
    room_tags = scan_room_tags(root, defines)
    manifest["room_tags"] = {
        "description": "Custom room tag dispatch table entries in bank $01. Asar patches 4-byte JML slots at these addresses. Yaze assigns tag IDs to rooms via room headers — this manifest provides labels and semantics so the editor can show meaningful names instead of raw tag numbers.",
        "dispatch_table_start": "0x01CC00",
        "dispatch_table_end": "0x01CC5A",
        "return_address": "0x01CC5A",
        "available_slots": ["0x36"],
        "tags": room_tags,
    }

    # Feature flags — compile-time toggles that affect which hooks are active.
    # Yaze could display these in the project settings panel and optionally
    # generate Config/feature_flags.asm when toggled.
    flags = scan_feature_flags(root)
    manifest["feature_flags"] = {
        "description": "Compile-time feature toggles in Config/feature_flags.asm. These control which ASM hooks are active. Yaze can display them in the project settings and optionally write updated flag values before triggering a rebuild.",
        "config_file": "Config/feature_flags.asm",
        "flags": flags,
    }

    # SRAM layout — custom variable definitions that yaze can use for
    # the RAM panel, save state inspector, and debugging overlays.
    sram = scan_sram_layout(root)
    manifest["sram"] = {
        "description": "Custom SRAM variable definitions from Core/sram.asm. These extend the vanilla ALTTP save file layout. Yaze can display variable names in the RAM panel and save state inspector instead of raw hex addresses.",
        "source_file": "Core/sram.asm",
        "variable_count": len(sram),
        "variables": sram,
    }

    # Summary statistics
    manifest["summary"] = {
        "total_hooks": len(hooks),
        "protected_region_count": len(protected),
        "owned_bank_count": len(banks),
        "expanded_message_count": messages.get("expanded_range", {}).get("count", 0),
        "room_tag_count": len(room_tags),
        "feature_flag_count": len(flags),
        "sram_variable_count": len(sram),
    }

    return manifest


def _write_manifest_atomic(output: Path, content: str) -> None:
    """Replace the generated manifest without exposing a partial JSON file."""
    import os
    import tempfile

    output.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        dir=output.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, 0o644)
        os.replace(temporary_path, output)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate hack manifest for yaze editor integration"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Oracle repo root (default: repo root)",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("Roms/hack_manifest.json"),
        help="Output path (default: Roms/hack_manifest.json)",
    )
    parser.add_argument(
        "--rom",
        type=Path,
        default=Path("Roms/oos168.sfc"),
        help="Editable/base ROM used for metadata and live dungeon layout",
    )
    parser.add_argument(
        "--patched-rom",
        type=Path,
        default=Path("Roms/oos168x.sfc"),
        help="Patched build output path recorded in build_pipeline",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        default=True,
        help="Pretty-print JSON (default: true)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Compact JSON output (no indentation)",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    output = (root / args.output).resolve() if not args.output.is_absolute() else args.output

    rom_path = (root / args.rom).resolve() if not args.rom.is_absolute() else args.rom
    patched_rom_path = (
        (root / args.patched_rom).resolve()
        if not args.patched_rom.is_absolute()
        else args.patched_rom
    )

    try:
        manifest = generate_manifest(root, rom_path, patched_rom_path)
    except ManifestGenerationError as exc:
        print(f"error: cannot generate hack manifest: {exc}", file=sys.stderr)
        return 1

    indent = None if args.compact else 2
    _write_manifest_atomic(output, json.dumps(manifest, indent=indent) + "\n")

    summary = manifest["summary"]
    print(f"Hack manifest written to {output}")
    print(f"  Hooks: {summary['total_hooks']}")
    print(f"  Protected regions: {summary['protected_region_count']}")
    print(f"  Owned banks: {summary['owned_bank_count']}")
    print(f"  Messages: {summary['expanded_message_count']}")
    print(f"  Room tags: {summary['room_tag_count']}")
    print(f"  Feature flags: {summary['feature_flag_count']}")
    print(f"  SRAM variables: {summary['sram_variable_count']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
