#!/usr/bin/env python3
"""
Generate a hack manifest JSON for yaze editor integration.

Build pipeline context:
  - oos168.sfc  = dev ROM (yaze edits this — vanilla + room/sprite/palette data)
  - asar patches oos168.sfc → oos168x.sfc (patched ROM with ASM hack applied)
  - Yaze and asar share the dev ROM; this manifest defines the boundary

Extends the hooks scanner to produce a comprehensive manifest that tells yaze:
  - Which ROM addresses are patched by asar (hooks/org directives)
  - Which reachable banks are fully owned by the ASM hack (expanded banks)
  - Which live room-header/message ranges remain editor-managed
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

ASM ownership follows the literal incsrc graph rooted at Oracle_main.asm.
Ignored assets and archived experiments that are not assembled cannot claim
ROM ownership.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

# Shared source parsing (define evaluation, active-line filtering)
from asm_source import (
    DEFINE_ANY_ASSIGN_RE,
    _load_global_defines,
    _iter_active_lines,
)

# Hook scanner (Python source scan; see generate_hooks_json.py)
from generate_hooks_json import (
    scan_org_directives,
    scan_hooks,
    HookEntry,
    OrgDirective,
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

# Literal Asar source include. Paths may be quoted or bare; comments are
# stripped before matching so archived `; incsrc ...` lines stay unreachable.
INCSRC_RE = re.compile(
    r"^\s*incsrc\s+(?:\"([^\"]+)\"|'([^']+)'|([^\s;]+))",
    re.IGNORECASE,
)

MANIFEST_ENTRY_POINT = Path("Oracle_main.asm")
EXPANDED_MESSAGE_WRAPPER = Path("Core/message.asm")
EXPANDED_MESSAGE_ASM_INCLUDE = Path(
    "Core/Generated/expanded_messages.asm"
)
EXPANDED_MESSAGE_BUNDLE = Path("Data/dialogue/expanded_messages.json")
EXPANDED_MESSAGE_DATA_START = 0x2F8026
EXPANDED_MESSAGE_DATA_END = 0x2FFDFF
MINECART_TRACK_SOURCE = Path("Sprites/Objects/data/minecart_tracks.asm")
MINECART_TRACK_SOURCE_CONTRACT = {
    "format": "yaze-minecart-track-table",
    "version": 1,
    "path": MINECART_TRACK_SOURCE.as_posix(),
}
DUNGEON_ROOM_COUNT = 296
OBJECT_TABLE_POINTER_OPERAND_PC = 0x874C
SPRITE_TABLE_POINTER_OPERAND_PC = 0x4C298
POT_POINTER_TABLE_PC = 0xDB69
ROOM_HEADER_POINTER_PC = 0xB5DD
ROOM_HEADER_BANK_PC = 0xB5E7
ROOM_HEADER_SIZE = 14
DUNGEON_MESSAGE_IDS_PC = 0x3F61D
SPRITE_DATA_END_PC = 0x4EC9F
POT_DATA_START_PC = 0xDDE7
POT_DATA_END_PC = 0xE6B2
CUSTOM_COLLISION_POINTER_TABLE_PC = 0x128090
CUSTOM_COLLISION_DATA_START_PC = 0x128450
CUSTOM_COLLISION_DATA_END_PC = 0x12E000
CUSTOM_COLLISION_MAP_WIDTH = 64
CUSTOM_COLLISION_MAP_HEIGHT = 64
CUSTOM_COLLISION_MAP_TILES = (
    CUSTOM_COLLISION_MAP_WIDTH * CUSTOM_COLLISION_MAP_HEIGHT
)

OBJECT_DATA_REGIONS_PC = (
    (0x50000, 0x53730),
    (0xF878A, 0x100000),
    (0x1EB90, 0x20000),
    (0x138000, 0x140000),
    (0x148000, 0x150000),
)
OBJECT_ALLOCATION_REGIONS_PC = ((0x148000, 0x150000),)
CANONICAL_LOROM_ROM_END_PC = 0x3F0000

AUDITED_UNRESOLVED_ORG_CONTRACTS = {
    ("Core/message.asm", "!addr+1", 0x0E),
    ("Core/sprite_macros.asm", "$0DB080+!SPRID", 0x0D),
    ("Core/sprite_macros.asm", "$0DB173+!SPRID", 0x0D),
    ("Core/sprite_macros.asm", "$0DB266+!SPRID", 0x0D),
    ("Core/sprite_macros.asm", "$0DB359+!SPRID", 0x0D),
    ("Core/sprite_macros.asm", "$0DB44C+!SPRID", 0x0D),
    ("Core/sprite_macros.asm", "$0DB53F+!SPRID", 0x0D),
    ("Core/sprite_macros.asm", "$0DB632+!SPRID", 0x0D),
    ("Core/sprite_macros.asm", "$0DB725+!SPRID", 0x0D),
    ("Core/sprite_macros.asm", "$069283+(!SPRID*2)", 0x06),
    ("Core/sprite_macros.asm", "$06865B+(!SPRID*2)", 0x06),
    (
        "Core/sprite_macros.asm",
        "NewSprRoutinesLong+(!SPRID*3)",
        0x30,
    ),
    (
        "Core/sprite_macros.asm",
        "NewSprPrepRoutinesLong+(!SPRID*3)",
        0x30,
    ),
}


class ManifestGenerationError(RuntimeError):
    """Raised when source or ROM evidence cannot safely define ownership."""


def _parse_incsrc(line: str) -> Optional[str]:
    """Return a literal `incsrc` path from uncommented source text."""
    source = line.split(";", 1)[0]
    match = INCSRC_RE.match(source)
    if not match:
        return None
    return next(value for value in match.groups() if value is not None)


def _iter_active_incsrcs(
    lines: list[str],
    global_defines: dict[str, int],
) -> Iterable[tuple[int, str]]:
    """Yield literal includes whose enclosing Asar condition is active."""
    for line_index, line, _ in _iter_active_lines(lines, global_defines):
        include_text = _parse_incsrc(line)
        if include_text is not None:
            yield line_index + 1, include_text


def _is_case_exact_file(candidate: Path, root: Path) -> bool:
    """Return whether a candidate exists with repository-exact path casing."""
    normalized = Path(os.path.normpath(candidate))
    try:
        relative = normalized.relative_to(root)
    except ValueError:
        # Preserve the caller's existing outside-root diagnostic.
        return candidate.is_file()

    current = root
    for part in relative.parts:
        try:
            entries = {entry.name: entry for entry in current.iterdir()}
        except OSError:
            return False
        if part not in entries:
            return False
        current = entries[part]
    return current.is_file()


def collect_reachable_asm_sources(
    root: Path,
    entry_point: Path = MANIFEST_ENTRY_POINT,
    defines: Optional[dict[str, int]] = None,
) -> list[Path]:
    """Collect the transitive literal `incsrc` graph for the build entry.

    Asar sources in this repository use both paths relative to the including
    file and repo-root-relative paths. Follow every feasible conditional edge,
    treat literal includes as authoritative regardless of directory name, and
    fail closed when a reachable include or cross-file global-define state
    cannot be resolved safely.
    """
    resolved_root = root.resolve()
    entry = entry_point if entry_point.is_absolute() else resolved_root / entry_point
    entry = entry.resolve()
    if not entry.is_file():
        raise ManifestGenerationError(f"ASM entry point not found: {entry}")
    if not entry.is_relative_to(resolved_root):
        raise ManifestGenerationError(
            f"ASM entry point is outside repo root: {entry}"
        )

    active_defines = (
        _load_global_defines(resolved_root)
        if defines is None
        else dict(defines)
    )
    pending = [entry]
    reachable: set[Path] = set()
    while pending:
        asm_path = pending.pop()
        if asm_path in reachable:
            continue
        reachable.add(asm_path)

        try:
            lines = asm_path.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines()
        except OSError as exc:
            raise ManifestGenerationError(
                f"Unable to read reachable ASM source {asm_path}: {exc}"
            ) from exc

        for line_number, include_text in _iter_active_incsrcs(
            lines, active_defines
        ):
            include_path = Path(include_text)
            candidates = (
                asm_path.parent / include_path,
                resolved_root / include_path,
            )
            included = next(
                (candidate.resolve() for candidate in candidates
                 if _is_case_exact_file(candidate, resolved_root)),
                None,
            )
            if included is None:
                rel = asm_path.relative_to(resolved_root)
                raise ManifestGenerationError(
                    f"{rel}:{line_number}: unresolved incsrc "
                    f"{include_text!r}"
                )
            if not included.is_relative_to(resolved_root):
                rel = asm_path.relative_to(resolved_root)
                raise ManifestGenerationError(
                    f"{rel}:{line_number}: incsrc escapes repo root: "
                    f"{include_text!r}"
                )
            pending.append(included)

    canonical_define_sources = {
        "Util/macros.asm",
        "Config/module_flags.asm",
        "Config/feature_flags.asm",
    }
    for asm_path in sorted(reachable):
        rel = asm_path.relative_to(resolved_root).as_posix()
        if rel in canonical_define_sources:
            continue
        try:
            lines = asm_path.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines()
        except OSError as exc:
            raise ManifestGenerationError(
                f"Unable to validate reachable ASM source {asm_path}: {exc}"
            ) from exc
        for line_index, line, _ in _iter_active_lines(lines, active_defines):
            assignment = DEFINE_ANY_ASSIGN_RE.match(line.split(";", 1)[0])
            if assignment and assignment.group(1) in active_defines:
                raise ManifestGenerationError(
                    f"{rel}:{line_index + 1}: reachable source reassigns "
                    f"preloaded global define !{assignment.group(1)} outside "
                    "the canonical define files; include-order state cannot "
                    "be resolved safely"
                )

    return sorted(reachable)


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


def scan_bank_ownership(
    root: Path,
    asm_paths: Optional[Iterable[Path]] = None,
) -> list[dict]:
    """Detect owned banks from sources reachable by the build entry point."""
    root = root.resolve()
    bank_sources: dict[int, list[dict]] = {}

    candidate_paths = (
        collect_reachable_asm_sources(root)
        if asm_paths is None
        else asm_paths
    )
    source_paths = list(candidate_paths)
    for asm_path in source_paths:
        asm_path = asm_path.resolve()
        try:
            rel = str(asm_path.relative_to(root))
        except ValueError as exc:
            raise ManifestGenerationError(
                f"Reachable ASM source is outside repo root: {asm_path}"
            ) from exc
        try:
            text = asm_path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            raise ManifestGenerationError(
                f"Unable to read reachable ASM source {asm_path}: {exc}"
            ) from exc

        lines = text.splitlines()

        for i, line in enumerate(lines):
            # Check for org $XX8000+ (expanded bank entry points)
            m = ORG_BANK_RE.match(line)
            if m:
                source_addr = int(m.group(1), 16)
                addr = _physical_org_address(source_addr)
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
                            end_addr = _physical_org_address(
                                int(am.group(1), 16)
                            )
                            break
                        # Stop at next org in a different bank
                        next_org = ORG_BANK_RE.match(lines[j])
                        if next_org:
                            next_addr = _physical_org_address(
                                int(next_org.group(1), 16)
                            )
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
                source_bank = int(fm.group(1), 16)
                if source_bank in (0x7E, 0x7F):
                    bank = source_bank
                else:
                    bank = source_bank & 0x7F
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
        elif bank in (0x7E, 0x7F):
            ownership = "ram"
            ownership_note = "WRAM definitions (not ROM data)"
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
    wrapper_file = root / EXPANDED_MESSAGE_WRAPPER
    include_file = root / EXPANDED_MESSAGE_ASM_INCLUDE
    if not wrapper_file.exists() or not include_file.exists():
        return {}

    wrapper_text = wrapper_file.read_text(encoding="utf-8", errors="ignore")
    wrapper_lines = wrapper_text.splitlines()
    include_text = include_file.read_text(encoding="utf-8", errors="ignore")
    include_lines = include_text.splitlines()

    messages: list[dict] = []
    hook_address = None
    last_org_addr = None

    for line in wrapper_lines:
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

    for i, line in enumerate(include_lines):
        # Message bodies live in the generated include so Yaze can replace
        # them without touching the loader and hook wrapper.
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

    if not messages:
        return {}

    msg_ids = [m["id_dec"] for m in messages]
    # Clean up messages for output (remove id_dec helper)
    for m in messages:
        del m["id_dec"]

    return {
        "hook_address": hook_address,
        "data_bank": "0x2F",
        "data_start": f"0x{EXPANDED_MESSAGE_DATA_START:06X}",
        "data_end": f"0x{EXPANDED_MESSAGE_DATA_END:06X}",
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

def scan_room_tags(
    root: Path,
    defines: dict[str, int],
    asm_paths: Optional[Iterable[Path]] = None,
) -> list[dict]:
    """Extract room tag mappings from org $01CCxx directives."""
    root = root.resolve()
    tags: dict[int, dict] = {}

    candidate_paths = (
        collect_reachable_asm_sources(root)
        if asm_paths is None
        else asm_paths
    )
    source_paths = list(candidate_paths)
    for asm_path in source_paths:
        asm_path = asm_path.resolve()
        try:
            rel = str(asm_path.relative_to(root))
        except ValueError as exc:
            raise ManifestGenerationError(
                f"Reachable ASM source is outside repo root: {asm_path}"
            ) from exc
        try:
            lines = asm_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError as exc:
            raise ManifestGenerationError(
                f"Unable to read reachable ASM source {asm_path}: {exc}"
            ) from exc

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


# Explicit associations, independent of declaration order and address order.
# Enum prefixes (GameState_, MapIcon_, Spawn_) intentionally are not bitfields.
SRAM_BIT_OWNERS = {
    "Story_": "StoryProgress", "Story2_": "StoryProgress2",
    "Crystal_": "Crystals", "SideQuest_": "SideQuestProgress",
    "SideQuest2_": "SideQuestProgress2", "Pendant_": "Pendants",
    "Dream_": "Dreams", "Bean_": "MagicBeanProgress",
    "Scroll_": "DungeonScrolls", "CastleAmbush_": "CastleAmbushFlags",
    "Part00_": "Part00Flags", "EonOwl_": "EonOwlFlags",
}
SRAM_ALIAS_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*=\s*([A-Za-z_]\w*)\s*(?:;.*)?$")


def scan_sram_layout(root: Path) -> list[dict]:
    """Extract names and explicit bit owners, retaining aliases and subfields.

    Literal fields remain separate even when contained in a larger block.
    Same-address names are serialized as aliases, never silently overwritten.
    Symbol aliases are resolved after all definitions (including forward refs).
    This is metadata extraction, not proof that every declaration is allocated.
    """
    sram_file = root / "Core" / "sram.asm"
    if not sram_file.exists():
        return []
    variables: dict[str, SramVariable] = {}
    aliases: dict[str, tuple[str, str]] = {}
    bits = []
    for line in sram_file.read_text(encoding="utf-8").splitlines():
        comment = PURPOSE_COMMENT_RE.search(line)
        purpose = comment.group(1).strip() if comment else ""
        match = SRAM_VAR_RE.match(line)
        if match:
            name, address = match.groups()
            if name in variables:
                raise ManifestGenerationError(f"Duplicate SRAM definition: {name}")
            variables[name] = SramVariable(name, int(address, 16), purpose)
        elif match := SRAM_ALIAS_RE.match(line):
            aliases[match[1]] = (match[2], purpose)
        elif match := SRAM_BIT_RE.match(line):
            bits.append((match[1], int(match[2], 16), purpose))

    def resolve(name: str, trail: tuple[str, ...] = ()) -> Optional[SramVariable]:
        if name in variables:
            return variables[name]
        if name in trail:
            raise ManifestGenerationError(f"Cyclic SRAM alias: {' -> '.join((*trail, name))}")
        if name in aliases:
            return resolve(aliases[name][0], (*trail, name))
        return None

    for name, value, purpose in bits:
        owner_name = SRAM_BIT_OWNERS.get(name.split("_", 1)[0] + "_")
        if owner_name is None:
            continue
        owner = resolve(owner_name)
        if owner is None:
            raise ManifestGenerationError(f"Bit !{name} has missing SRAM owner {owner_name}")
        owner.bits.append({"name": f"!{name}", "value": f"0x{value:02X}", "purpose": purpose})

    by_address: dict[int, dict] = {}
    for var in variables.values():
        if var.address in by_address:
            entry = by_address[var.address]
            entry.setdefault("aliases", []).append({"name": var.name, "purpose": var.purpose})
            entry.setdefault("bits", []).extend(var.bits)
            continue
        entry = {"name": var.name, "address": f"0x{var.address:06X}"}
        if var.purpose:
            entry["purpose"] = var.purpose
        if var.bits:
            entry["bits"] = list(var.bits)
        by_address[var.address] = entry
    for name, (_, purpose) in aliases.items():
        var = resolve(name)
        if var is not None:
            by_address[var.address].setdefault("aliases", []).append({"name": name, "purpose": purpose})
    return [by_address[address] for address in sorted(by_address)]


# ---------------------------------------------------------------------------
# Protected region computation
# ---------------------------------------------------------------------------

def compute_protected_regions(hooks: list[HookEntry]) -> list[dict]:
    """Group hooks into contiguous protected address ranges."""
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

    # Group in PC space so legacy low-half mirrors and bank crossings produce
    # canonical, increasing LoROM half-open ranges in manifest v3.
    sorted_hooks = sorted(hooks, key=lambda hook: _snes_to_pc(hook.address))
    regions = []
    current_start = _snes_to_pc(sorted_hooks[0].address)
    current_end = current_start + (
        sorted_hooks[0].protected_size
        or SIZE_ESTIMATE.get(sorted_hooks[0].kind, 4)
    )
    current_hooks = [sorted_hooks[0]]

    for hook in sorted_hooks[1:]:
        hook_start = _snes_to_pc(hook.address)
        hook_end = hook_start + (
            hook.protected_size or SIZE_ESTIMATE.get(hook.kind, 4)
        )

        # Merge if within 16 bytes of the previous region (likely related)
        if hook_start <= current_end + 16:
            current_end = max(current_end, hook_end)
            current_hooks.append(hook)
        else:
            # Emit previous region
            regions.append({
                "start": f"0x{_pc_to_snes(current_start):06X}",
                "end": f"0x{_pc_to_snes(current_end):06X}",
                "size": current_end - current_start,
                "hook_count": len(current_hooks),
                "module": current_hooks[0].module,
            })
            current_start = hook_start
            current_end = hook_end
            current_hooks = [hook]

    # Emit last region
    regions.append({
        "start": f"0x{_pc_to_snes(current_start):06X}",
        "end": f"0x{_pc_to_snes(current_end):06X}",
        "size": current_end - current_start,
        "hook_count": len(current_hooks),
        "module": current_hooks[0].module,
    })

    return regions


# ---------------------------------------------------------------------------
# Exact editor-managed ROM ranges
# ---------------------------------------------------------------------------

def _canonical_lorom_address(address: int) -> int:
    """Return the canonical mapped LoROM mirror for a 24-bit address."""
    if not 0 <= address <= 0xFFFFFF:
        raise ManifestGenerationError(
            f"SNES address 0x{address:X} is outside 24-bit address space"
        )
    canonical = address & 0x7FFFFF
    bank = (canonical >> 16) & 0x7F
    if bank in (0x7E, 0x7F):
        raise ManifestGenerationError(
            f"SNES address 0x{address:06X} points to WRAM or its FastROM mirror"
        )
    if (canonical & 0xFFFF) < 0x8000:
        canonical |= 0x8000
    return canonical


def _snes_to_pc(address: int) -> int:
    """Convert a canonical LoROM address to an unheadered PC offset."""
    address = _canonical_lorom_address(address)
    return ((address & 0x7F0000) >> 1) | (address & 0x7FFF)


def _physical_org_address(address: int) -> int:
    """Map an Asar org to its physical LoROM bank/address.

    Asar sources may use FastROM mirrors such as $A0F000. Ownership must
    describe the underlying $20F000 bytes rather than claiming a second,
    whole mirror bank. WRAM orgs remain RAM metadata and are not ROM-mapped.
    """
    bank = (address >> 16) & 0xFF
    if bank in (0x7E, 0x7F):
        return address
    return _canonical_lorom_address(address)


def _strict_lorom_to_pc(address: int, description: str) -> int:
    """Convert a ROM-sourced pointer only when it is valid mapped LoROM."""
    if not 0 <= address <= 0xFFFFFF:
        raise ManifestGenerationError(
            f"{description} 0x{address:X} is outside 24-bit address space"
        )
    bank = (address >> 16) & 0xFF
    offset = address & 0xFFFF
    if bank in (0x7E, 0x7F, 0xFE, 0xFF):
        raise ManifestGenerationError(
            f"{description} 0x{address:06X} points to WRAM or its FastROM mirror"
        )
    if offset < 0x8000:
        raise ManifestGenerationError(
            f"{description} 0x{address:06X} is not a high-half LoROM pointer"
        )
    pc_address = ((bank & 0x7F) << 15) | (offset & 0x7FFF)
    if pc_address >= CANONICAL_LOROM_ROM_END_PC:
        raise ManifestGenerationError(
            f"{description} 0x{address:06X} maps into the WRAM-backed "
            "LoROM PC window"
        )
    return pc_address


def _pc_to_snes(address: int) -> int:
    """Convert an unheadered PC offset to a canonical LoROM address."""
    if not 0 <= address < CANONICAL_LOROM_ROM_END_PC:
        raise ManifestGenerationError(
            f"PC address 0x{address:X} is outside canonical ROM-backed LoROM"
        )
    snes = (
        ((address << 1) & 0x7F0000)
        | (address & 0x7FFF)
        | 0x8000
    )
    if _snes_to_pc(snes) != address:
        raise ManifestGenerationError(
            f"PC address 0x{address:X} does not round-trip through LoROM"
        )
    return snes


def _require_rom_span(
    data: bytes,
    address: int,
    size: int,
    description: str,
) -> None:
    if address < 0 or size < 0 or address + size > len(data):
        raise ManifestGenerationError(
            f"{description} PC span [0x{address:X}, "
            f"0x{address + size:X}) exceeds dev ROM size 0x{len(data):X}"
        )


def _read_u16(data: bytes, address: int, description: str) -> int:
    _require_rom_span(data, address, 2, description)
    return data[address] | (data[address + 1] << 8)


def _read_u8(data: bytes, address: int, description: str) -> int:
    _require_rom_span(data, address, 1, description)
    return data[address]


def _read_u24(data: bytes, address: int, description: str) -> int:
    _require_rom_span(data, address, 3, description)
    return (
        data[address]
        | (data[address + 1] << 8)
        | (data[address + 2] << 16)
    )


def _editor_range(start_pc: int, end_pc: int) -> dict[str, str]:
    if start_pc >= end_pc:
        raise ManifestGenerationError(
            f"Invalid editor-managed PC range "
            f"[0x{start_pc:X}, 0x{end_pc:X})"
        )
    return {
        "start": f"0x{_pc_to_snes(start_pc):06X}",
        "end": f"0x{_pc_to_snes(end_pc):06X}",
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
    pointer_pc: int, regions: tuple[tuple[int, int], ...]
) -> bool:
    return any(start <= pointer_pc < end for start, end in regions)


def _validate_disjoint_named_ranges(
    ranges: list[tuple[str, int, int]], description: str
) -> None:
    sorted_ranges = sorted(ranges, key=lambda item: (item[1], item[2]))
    for previous, current in zip(sorted_ranges, sorted_ranges[1:]):
        if current[1] < previous[2]:
            raise ManifestGenerationError(
                f"{description} overlap: {previous[0]} "
                f"[0x{previous[1]:X}, 0x{previous[2]:X}) conflicts with "
                f"{current[0]} [0x{current[1]:X}, 0x{current[2]:X})"
            )


def _dungeon_stream_parse_limit(
    pointer_pc: int,
    regions: tuple[tuple[int, int], ...],
) -> int:
    containing_end = next(
        (end for start, end in regions if start <= pointer_pc < end),
        None,
    )
    if containing_end is None:
        raise ManifestGenerationError(
            f"dungeon stream pointer PC 0x{pointer_pc:X} is outside its "
            "declared data regions"
        )
    bank_end = ((pointer_pc // 0x8000) + 1) * 0x8000
    return min(containing_end, bank_end)


def _find_dungeon_stream_end(
    data: bytes,
    stream_name: str,
    room_id: int,
    start_pc: int,
    limit_pc: int,
) -> int:
    """Return a format-valid stream's exclusive logical end."""

    def require(size: int, description: str) -> None:
        if size < 0 or cursor + size > limit_pc:
            raise ManifestGenerationError(
                f"{stream_name} stream for room 0x{room_id:03X} {description} "
                f"before parse limit PC 0x{limit_pc:X}"
            )
        _require_rom_span(data, cursor, size, description)

    cursor = start_pc
    if stream_name == "objects":
        require(2, "is missing its two-byte header")
        cursor += 2
        for list_id in range(2):
            while True:
                require(2, f"list {list_id} has no 0xFFFF terminator")
                if data[cursor : cursor + 2] == b"\xFF\xFF":
                    cursor += 2
                    break
                require(3, f"list {list_id} has a truncated record")
                cursor += 3

        in_doors = False
        while True:
            require(
                2,
                (
                    "door list has no 0xFFFF terminator"
                    if in_doors
                    else "list 2 has no door marker or terminator"
                ),
            )
            marker = data[cursor : cursor + 2]
            if marker == b"\xFF\xFF":
                return cursor + 2
            if not in_doors and marker == b"\xF0\xFF":
                cursor += 2
                in_doors = True
                continue
            if in_doors:
                cursor += 2
            else:
                require(3, "list 2 has a truncated record")
                cursor += 3

    if stream_name == "sprites":
        require(1, "is missing its sort byte")
        cursor += 1
        while True:
            require(1, "has no 0xFF terminator")
            if data[cursor] == 0xFF:
                return cursor + 1
            require(3, "has a truncated record")
            cursor += 3

    if stream_name == "pot_items":
        while True:
            require(2, "has no 0xFFFF terminator")
            if data[cursor : cursor + 2] == b"\xFF\xFF":
                return cursor + 2
            require(3, "has a truncated record")
            cursor += 3

    raise ManifestGenerationError(f"unsupported dungeon stream {stream_name}")


def _derive_dungeon_stream_regions(data: bytes) -> dict:
    object_table_snes = _read_u24(
        data,
        OBJECT_TABLE_POINTER_OPERAND_PC,
        "object pointer-table operand",
    )
    object_table_pc = _strict_lorom_to_pc(
        object_table_snes, "Object pointer-table operand"
    )
    object_table_size = DUNGEON_ROOM_COUNT * 3
    _require_rom_span(data, object_table_pc, object_table_size, "object pointer table")
    _validate_regions(
        data,
        "objects",
        OBJECT_DATA_REGIONS_PC,
        OBJECT_ALLOCATION_REGIONS_PC,
    )
    for room_id in range(DUNGEON_ROOM_COUNT):
        object_pointer = _read_u24(
            data,
            object_table_pc + room_id * 3,
            f"object pointer for room 0x{room_id:03X}",
        )
        object_data_pc = _strict_lorom_to_pc(
            object_pointer, f"Object pointer for room 0x{room_id:03X}"
        )
        if not _pointer_pc_in_regions(object_data_pc, OBJECT_DATA_REGIONS_PC):
            raise ManifestGenerationError(
                f"object pointer for room 0x{room_id:03X} resolves to PC "
                f"0x{object_data_pc:X}, outside declared object data regions"
            )
        _find_dungeon_stream_end(
            data,
            "objects",
            room_id,
            object_data_pc,
            _dungeon_stream_parse_limit(
                object_data_pc, OBJECT_DATA_REGIONS_PC
            ),
        )

    sprite_table_low = _read_u16(
        data,
        SPRITE_TABLE_POINTER_OPERAND_PC,
        "sprite pointer-table operand",
    )
    sprite_table_snes = 0x090000 | sprite_table_low
    sprite_table_pc = _strict_lorom_to_pc(
        sprite_table_snes, "Sprite pointer-table operand"
    )
    sprite_table_size = DUNGEON_ROOM_COUNT * 2
    _require_rom_span(data, sprite_table_pc, sprite_table_size, "sprite pointer table")
    sprite_pointers_pc: list[int] = []
    for room_id in range(DUNGEON_ROOM_COUNT):
        pointer_low = _read_u16(
            data,
            sprite_table_pc + room_id * 2,
            f"sprite pointer for room 0x{room_id:03X}",
        )
        sprite_pointers_pc.append(
            _strict_lorom_to_pc(
                0x090000 | pointer_low,
                f"Sprite pointer for room 0x{room_id:03X}",
            )
        )
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
        _find_dungeon_stream_end(
            data,
            "sprites",
            room_id,
            pointer_pc,
            _dungeon_stream_parse_limit(pointer_pc, sprite_regions),
        )

    pot_table_size = DUNGEON_ROOM_COUNT * 2
    _require_rom_span(
        data, POT_POINTER_TABLE_PC, pot_table_size, "pot-item pointer table"
    )
    pot_pointers_pc: list[int] = []
    for room_id in range(DUNGEON_ROOM_COUNT):
        pointer_low = _read_u16(
            data,
            POT_POINTER_TABLE_PC + room_id * 2,
            f"pot-item pointer for room 0x{room_id:03X}",
        )
        if pointer_low < 0x8000:
            raise ManifestGenerationError(
                f"pot-item pointer for room 0x{room_id:03X} is unmapped "
                f"bank-$01 value 0x{pointer_low:04X}"
            )
        pot_pointers_pc.append(
            _strict_lorom_to_pc(
                0x010000 | pointer_low,
                f"Pot-item pointer for room 0x{room_id:03X}",
            )
        )
    pot_regions = ((POT_DATA_START_PC, POT_DATA_END_PC),)
    _validate_regions(data, "pot_items", pot_regions, pot_regions)
    for room_id, pointer_pc in enumerate(pot_pointers_pc):
        if not _pointer_pc_in_regions(pointer_pc, pot_regions):
            raise ManifestGenerationError(
                f"pot-item pointer for room 0x{room_id:03X} resolves to PC "
                f"0x{pointer_pc:X}, outside pot-item data region"
            )
        _find_dungeon_stream_end(
            data,
            "pot_items",
            room_id,
            pointer_pc,
            _dungeon_stream_parse_limit(pointer_pc, pot_regions),
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
            (
                "objects.pointer_source",
                OBJECT_TABLE_POINTER_OPERAND_PC,
                OBJECT_TABLE_POINTER_OPERAND_PC + 3,
            ),
            (
                "sprites.pointer_source",
                SPRITE_TABLE_POINTER_OPERAND_PC,
                SPRITE_TABLE_POINTER_OPERAND_PC + 2,
            ),
            (
                "objects.door_pointer_table",
                0xF83C0,
                0xF83C0 + DUNGEON_ROOM_COUNT * 3,
            ),
        )
    )
    _validate_disjoint_named_ranges(
        occupied_ranges, "dungeon stream pointer/data ranges"
    )
    _validate_disjoint_named_ranges(
        [
            (
                "objects.allocation_regions[0]",
                *OBJECT_ALLOCATION_REGIONS_PC[0],
            ),
            ("sprites.allocation_regions[0]", *sprite_regions[0]),
            ("pot_items.allocation_regions[0]", *pot_regions[0]),
        ],
        "dungeon stream allocation ranges",
    )

    return {
        "objects": {
            "pointer_table": f"0x{_pc_to_snes(object_table_pc):06X}",
            "pointer_count": DUNGEON_ROOM_COUNT,
            "pointer_encoding": "long24",
            "strategy": "copy_on_write",
            "data_regions": [
                _editor_range(start, end) for start, end in OBJECT_DATA_REGIONS_PC
            ],
            "allocation_regions": [
                _editor_range(start, end) for start, end in OBJECT_ALLOCATION_REGIONS_PC
            ],
        },
        "sprites": {
            "pointer_table": f"0x{_pc_to_snes(sprite_table_pc):06X}",
            "pointer_count": DUNGEON_ROOM_COUNT,
            "pointer_encoding": "bank16",
            "pointer_bank": "0x09",
            "strategy": "copy_on_write",
            "data_regions": [
                _editor_range(start, end) for start, end in sprite_regions
            ],
            "allocation_regions": [
                _editor_range(start, end) for start, end in sprite_regions
            ],
        },
        "pot_items": {
            "pointer_table": f"0x{_pc_to_snes(POT_POINTER_TABLE_PC):06X}",
            "pointer_count": DUNGEON_ROOM_COUNT,
            "pointer_encoding": "bank16",
            "pointer_bank": "0x01",
            "strategy": "repack_all",
            "data_regions": [_editor_range(start, end) for start, end in pot_regions],
            "allocation_regions": [
                _editor_range(start, end) for start, end in pot_regions
            ],
        },
    }


def derive_dungeon_stream_regions(dev_rom_path: Path) -> dict:
    """Derive guarded object, sprite, and pot-item layouts from a dev ROM."""
    try:
        data = dev_rom_path.read_bytes()
    except OSError as exc:
        raise ManifestGenerationError(
            f"Unable to read dev ROM {dev_rom_path}: {exc}"
        ) from exc
    return _derive_dungeon_stream_regions(data)


def _find_custom_collision_stream_end(data: bytes, room_id: int, start_pc: int) -> int:
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
        word = _read_u16(
            data,
            cursor,
            f"custom collision stream for room 0x{room_id:03X}",
        )
        cursor += 2
        if word == 0xFFFF:
            return cursor
        if word == 0xF0F0:
            single_tile_mode = True
            continue
        if single_tile_mode:
            if word >= CUSTOM_COLLISION_MAP_TILES:
                raise ManifestGenerationError(
                    f"custom collision single-tile offset 0x{word:04X} for "
                    f"room 0x{room_id:03X} is outside the 64x64 map"
                )
            require_stream_span(cursor, 1, "custom collision tile")
            cursor += 1
            continue

        require_stream_span(cursor, 2, "custom collision rectangle dimensions")
        width = _read_u8(
            data,
            cursor,
            f"custom collision width for room 0x{room_id:03X}",
        )
        height = _read_u8(
            data,
            cursor + 1,
            f"custom collision height for room 0x{room_id:03X}",
        )
        cursor += 2
        if width == 0 or height == 0:
            raise ManifestGenerationError(
                f"custom collision rectangle for room 0x{room_id:03X} has "
                f"zero dimension {width}x{height}"
            )
        row, column = divmod(word, CUSTOM_COLLISION_MAP_WIDTH)
        if (
            word >= CUSTOM_COLLISION_MAP_TILES
            or column + width > CUSTOM_COLLISION_MAP_WIDTH
            or row + height > CUSTOM_COLLISION_MAP_HEIGHT
        ):
            raise ManifestGenerationError(
                f"custom collision rectangle for room 0x{room_id:03X} at "
                f"offset 0x{word:04X} with size {width}x{height} exceeds "
                "the 64x64 map"
            )
        payload_size = width * height
        require_stream_span(cursor, payload_size, "custom collision rectangle")
        cursor += payload_size

    raise ManifestGenerationError(
        f"custom collision stream for room 0x{room_id:03X} is unterminated "
        f"before reserved WaterFill data at PC 0x{CUSTOM_COLLISION_DATA_END_PC:X}"
    )


def derive_editor_managed_regions(dev_rom_path: Path) -> list[dict]:
    """Derive exact dungeon metadata and collision ranges from the dev ROM."""
    try:
        data = dev_rom_path.read_bytes()
    except OSError as exc:
        raise ManifestGenerationError(
            f"Unable to read dev ROM {dev_rom_path}: {exc}"
        ) from exc

    header_table_snes = _read_u24(
        data, ROOM_HEADER_POINTER_PC, "room-header pointer-table operand"
    )
    header_table_pc = _strict_lorom_to_pc(
        header_table_snes, "Room-header pointer-table operand"
    )
    _require_rom_span(
        data,
        header_table_pc,
        DUNGEON_ROOM_COUNT * 2,
        "room-header pointer table",
    )
    _require_rom_span(data, ROOM_HEADER_BANK_PC, 1, "room-header pointer bank")
    header_bank = data[ROOM_HEADER_BANK_PC]

    header_ranges: list[tuple[int, int]] = []
    for room_id in range(DUNGEON_ROOM_COUNT):
        pointer_pc = header_table_pc + room_id * 2
        header_offset = _read_u16(
            data,
            pointer_pc,
            f"room-header pointer for room 0x{room_id:03X}",
        )
        header_address = (header_bank << 16) | header_offset
        header_pc = _strict_lorom_to_pc(
            header_address,
            f"Room-header pointer for room 0x{room_id:03X}",
        )
        _require_rom_span(
            data,
            header_pc,
            ROOM_HEADER_SIZE,
            f"room header 0x{room_id:03X}",
        )
        header_ranges.append((header_pc, header_pc + ROOM_HEADER_SIZE))

    sorted_headers = sorted(header_ranges)
    if len(set(sorted_headers)) != DUNGEON_ROOM_COUNT:
        raise ManifestGenerationError(
            "Room-header pointers are not unique across all 296 rooms"
        )
    for previous, current in zip(sorted_headers, sorted_headers[1:]):
        if current[0] != previous[1]:
            raise ManifestGenerationError(
                "Room headers are not one contiguous 296-record range: "
                f"[0x{previous[0]:X}, 0x{previous[1]:X}) is followed by "
                f"[0x{current[0]:X}, 0x{current[1]:X})"
            )

    messages_end_pc = DUNGEON_MESSAGE_IDS_PC + DUNGEON_ROOM_COUNT * 2
    _require_rom_span(
        data,
        DUNGEON_MESSAGE_IDS_PC,
        DUNGEON_ROOM_COUNT * 2,
        "dungeon room message IDs",
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
        raw_pointer = _read_u24(
            data,
            CUSTOM_COLLISION_POINTER_TABLE_PC + room_id * 3,
            f"custom-collision pointer for room 0x{room_id:03X}",
        )
        if raw_pointer == 0:
            continue
        collision_pc = _strict_lorom_to_pc(
            raw_pointer,
            f"Custom-collision pointer for room 0x{room_id:03X}",
        )
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
        ("dungeon_message_ids", DUNGEON_MESSAGE_IDS_PC, messages_end_pc),
        ("room_headers", sorted_headers[0][0], sorted_headers[-1][1]),
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

    return [
        _editor_range(start, end)
        for _, start, end in sorted(named_regions, key=lambda item: item[1])
    ]


def _validate_expanded_hooks_disjoint_from_editor_regions(
    hooks: list[HookEntry], editor_regions: list[dict]
) -> None:
    """Reject expanded hooks that may extend into editor-owned bytes.

    HookEntry records only a start address, not an exact source-backed end.
    Within one physical LoROM bank, a hook beginning before an editor range's
    exclusive end is therefore unsafe even when it starts just before the
    range. A hook at or after the exclusive end remains disjoint.
    """
    editor_pc_ranges = [
        (
            _strict_lorom_to_pc(int(region["start"], 16), "Editor range start"),
            _strict_lorom_to_pc(int(region["end"], 16), "Editor range end"),
            region,
        )
        for region in editor_regions
    ]
    for hook in hooks:
        physical = _physical_org_address(hook.address)
        bank = (physical >> 16) & 0xFF
        if bank in (0x7E, 0x7F) or bank < 0x1E:
            continue
        hook_start = _strict_lorom_to_pc(
            physical, f"Expanded hook {hook.source}"
        )
        for region_start, region_end, region in editor_pc_ranges:
            hook_bank_start = (hook_start // 0x8000) * 0x8000
            hook_bank_end = hook_bank_start + 0x8000
            region_segment_start = max(region_start, hook_bank_start)
            region_segment_end = min(region_end, hook_bank_end)
            if (
                region_segment_start < region_segment_end
                and hook_start < region_segment_end
            ):
                raise ManifestGenerationError(
                    f"expanded hook {hook.source} at 0x{physical:06X} "
                    f"starts before editor-managed range {region['start']}-"
                    f"{region['end']} ends in the same physical LoROM bank; "
                    "its exact end is unknown, so protected hooks must take "
                    "precedence"
                )


def _validate_unresolved_org_proofs(
    directives: list[OrgDirective], editor_regions: list[dict]
) -> None:
    """Require source-local bank proof for every active unresolved org."""
    editor_banks: set[int] = set()
    for region in editor_regions:
        start_pc = _strict_lorom_to_pc(
            int(region["start"], 16), "Editor range start"
        )
        end_pc = _strict_lorom_to_pc(
            int(region["end"], 16), "Editor range end"
        )
        for bank in range(start_pc // 0x8000, (end_pc - 1) // 0x8000 + 1):
            editor_banks.add(bank)

    for directive in directives:
        if directive.address is not None:
            continue
        if directive.proof_bank is None:
            raise ManifestGenerationError(
                f"{directive.source}: unresolved active org expression "
                f"{directive.expression!r} has no @manifest-org-bank proof"
            )
        if re.search(r"<[^>]+>", directive.expression):
            raise ManifestGenerationError(
                f"{directive.source}: unresolved active org expression "
                f"{directive.expression!r} contains a macro placeholder; "
                "a single @manifest-org-bank proof cannot cover every "
                "invocation"
            )
        physical_bank = directive.proof_bank & 0x7F
        if physical_bank in (0x7E, 0x7F):
            raise ManifestGenerationError(
                f"{directive.source}: unresolved active org expression "
                f"{directive.expression!r} claims WRAM bank proof "
                f"0x{directive.proof_bank:02X}"
            )
        if directive.anchor_banks and (
            len(directive.anchor_banks) != 1
            or physical_bank != directive.anchor_banks[0]
        ):
            anchors = ", ".join(
                f"0x{bank:02X}" for bank in directive.anchor_banks
            )
            raise ManifestGenerationError(
                f"{directive.source}: unresolved active org expression "
                f"{directive.expression!r} has address-literal bank anchor(s) "
                f"{anchors}, contradicting @manifest-org-bank proof "
                f"0x{directive.proof_bank:02X}"
            )
        if physical_bank in editor_banks:
            raise ManifestGenerationError(
                f"{directive.source}: unresolved active org expression "
                f"{directive.expression!r} may affect editor-managed physical "
                f"LoROM bank 0x{physical_bank:02X}"
            )
        source_path = directive.source.rsplit(":", 1)[0]
        contract = (
            source_path,
            directive.expression,
            directive.proof_bank,
        )
        if contract not in AUDITED_UNRESOLVED_ORG_CONTRACTS:
            raise ManifestGenerationError(
                f"{directive.source}: unresolved active org expression "
                f"{directive.expression!r} is not an audited source/expression/"
                "bank contract"
            )


# ---------------------------------------------------------------------------
# Exact hook source (z3asm hooks.json)
# ---------------------------------------------------------------------------

HOOK_FILE_VERSION = 1
EXACT_HOOK_KINDS = frozenset({"jsl", "jml", "jsr", "jmp", "data", "patch"})
HOOK_ADDRESS_RE = re.compile(r"^0x[0-9A-Fa-f]{1,6}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
# Banks whose every byte is already ASM-owned through owned_banks. Exact spans
# in any other bank (vanilla, shared, unclassified) go into protected_regions.
OWNED_BANK_TYPES = ("asm_owned", "asm_expansion")


@dataclass(frozen=True)
class ExactSpan:
    """One assembler write: half-open PC range plus its hook record."""

    start_pc: int
    end_pc: int
    hook: HookEntry


def _is_strict_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def load_exact_hooks(
    hooks_path: Path, patched_rom_path: Path
) -> tuple[list[ExactSpan], dict]:
    """Load z3asm hooks.json and prove it belongs to the patched ROM.

    Rejects the file unless its recorded output-ROM SHA-256 and size match
    `patched_rom_path` exactly, and every entry is a mapped, in-ROM,
    positive-size span with a supported kind.
    """
    if not hooks_path.is_file():
        raise ManifestGenerationError(f"Hook file not found: {hooks_path}")
    raw = hooks_path.read_bytes()
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ManifestGenerationError(
            f"Hook file {hooks_path} is not valid JSON: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise ManifestGenerationError(f"Hook file {hooks_path} is not an object")
    version = data.get("version")
    if not _is_strict_int(version) or version != HOOK_FILE_VERSION:
        raise ManifestGenerationError(
            f"Hook file {hooks_path} has unsupported version {version!r}; "
            f"expected {HOOK_FILE_VERSION}"
        )

    rom_meta = data.get("rom")
    recorded_sha = rom_meta.get("sha256") if isinstance(rom_meta, dict) else None
    recorded_size = rom_meta.get("size") if isinstance(rom_meta, dict) else None
    if not isinstance(recorded_sha, str) or not SHA256_RE.match(recorded_sha):
        raise ManifestGenerationError(
            f"Hook file {hooks_path} has no valid rom.sha256; rebuild z3asm "
            "with output-hash emission and reassemble"
        )
    if not _is_strict_int(recorded_size):
        raise ManifestGenerationError(
            f"Hook file {hooks_path} has no valid rom.size"
        )
    rom_bytes = patched_rom_path.read_bytes()
    actual_sha = hashlib.sha256(rom_bytes).hexdigest()
    if recorded_sha != actual_sha or recorded_size != len(rom_bytes):
        raise ManifestGenerationError(
            f"Hook file {hooks_path} belongs to a different ROM: it records "
            f"sha256 {recorded_sha[:16]} size {recorded_size}, but patched "
            f"ROM {patched_rom_path} has sha256 {actual_sha[:16]} size "
            f"{len(rom_bytes)}"
        )

    entries = data.get("hooks")
    if not isinstance(entries, list):
        raise ManifestGenerationError(f"Hook file {hooks_path} has no hooks list")
    rom_end = min(len(rom_bytes), CANONICAL_LOROM_ROM_END_PC)
    spans: list[ExactSpan] = []
    for index, entry in enumerate(entries):
        where = f"Hook file {hooks_path} entry {index}"
        if not isinstance(entry, dict):
            raise ManifestGenerationError(f"{where} is not an object")
        address_text = entry.get("address")
        if not isinstance(address_text, str) or not HOOK_ADDRESS_RE.match(
            address_text
        ):
            raise ManifestGenerationError(
                f"{where} has invalid address {address_text!r}"
            )
        address = int(address_text, 16)
        size = entry.get("size")
        if not _is_strict_int(size) or size <= 0:
            raise ManifestGenerationError(f"{where} has invalid size {size!r}")
        kind = entry.get("kind")
        if kind not in EXACT_HOOK_KINDS:
            raise ManifestGenerationError(f"{where} has invalid kind {kind!r}")
        start_pc = _strict_lorom_to_pc(address, f"{where} address")
        end_pc = start_pc + size
        if end_pc > rom_end:
            raise ManifestGenerationError(
                f"{where} span [0x{start_pc:X}, 0x{end_pc:X}) ends past the "
                f"patched ROM (0x{rom_end:X})"
            )
        hook = HookEntry(
            address=address,
            name=str(entry.get("name", f"hook_{address:06X}")),
            kind=kind,
            target=entry.get("target"),
            source=str(entry.get("source", "")),
            note=str(entry.get("note", "")),
            module=str(entry.get("module", "")),
            skip_abi=bool(entry.get("skip_abi", False)),
            abi_class=str(entry.get("abi_class", "")),
            expected_m=entry.get("expected_m"),
            expected_x=entry.get("expected_x"),
            expected_exit_m=entry.get("expected_exit_m"),
            expected_exit_x=entry.get("expected_exit_x"),
            protected_size=size,
        )
        spans.append(ExactSpan(start_pc, end_pc, hook))

    provenance = {
        "hooks_sha256": hashlib.sha256(raw).hexdigest(),
        "patched_rom_sha256": actual_sha,
        "patched_rom_size": len(rom_bytes),
    }
    return spans, provenance


def compute_exact_protected_regions(spans: list[ExactSpan]) -> list[dict]:
    """Union exact spans; merge only spans that overlap or touch.

    A one-byte gap between two writes stays unprotected (editable).
    """
    regions: list[dict] = []
    for span in sorted(spans, key=lambda item: (item.start_pc, item.end_pc)):
        if regions and span.start_pc <= regions[-1]["_end_pc"]:
            current = regions[-1]
            current["_end_pc"] = max(current["_end_pc"], span.end_pc)
            current["hook_count"] += 1
            continue
        regions.append(
            {
                "_start_pc": span.start_pc,
                "_end_pc": span.end_pc,
                "hook_count": 1,
                "module": span.hook.module,
            }
        )
    return [
        {
            "start": f"0x{_pc_to_snes(region['_start_pc']):06X}",
            "end": f"0x{_pc_to_snes(region['_end_pc']):06X}",
            "size": region["_end_pc"] - region["_start_pc"],
            "hook_count": region["hook_count"],
            "module": region["module"],
        }
        for region in regions
    ]


def _span_banks(start_pc: int, end_pc: int) -> set[int]:
    return set(range(start_pc // 0x8000, (end_pc - 1) // 0x8000 + 1))


def _yaze_editable_pc_ranges(
    editor_regions: list[dict], stream_regions: dict
) -> list[tuple[str, int, int]]:
    """PC ranges Yaze may write: editor-managed data, stream data/allocation
    regions, and the three stream pointer tables."""
    ranges: list[tuple[str, int, int]] = []
    for region in editor_regions:
        ranges.append(
            (
                "editor_managed_regions",
                _strict_lorom_to_pc(int(region["start"], 16), "Editor range start"),
                _strict_lorom_to_pc(int(region["end"], 16), "Editor range end"),
            )
        )
    for stream_name, stream in stream_regions.items():
        for key in ("data_regions", "allocation_regions"):
            for region in stream.get(key, []):
                ranges.append(
                    (
                        f"dungeon_stream_regions.{stream_name}.{key}",
                        _strict_lorom_to_pc(
                            int(region["start"], 16), f"{stream_name} {key} start"
                        ),
                        _strict_lorom_to_pc(
                            int(region["end"], 16), f"{stream_name} {key} end"
                        ),
                    )
                )
        table = stream.get("pointer_table")
        if table is not None:
            entry_size = 3 if stream.get("pointer_encoding") == "long24" else 2
            table_pc = _strict_lorom_to_pc(
                int(table, 16), f"{stream_name} pointer table"
            )
            ranges.append(
                (
                    f"dungeon_stream_regions.{stream_name}.pointer_table",
                    table_pc,
                    table_pc + int(stream["pointer_count"]) * entry_size,
                )
            )
    return ranges


def _validate_exact_spans_disjoint_from_editable(
    spans: list[ExactSpan], editable: list[tuple[str, int, int]]
) -> None:
    """Reject any assembler write that touches a range Yaze edits.

    Uses exact byte spans in every bank, including spans that cross banks.
    """
    for span in spans:
        for name, start, end in editable:
            if span.start_pc < end and start < span.end_pc:
                raise ManifestGenerationError(
                    f"assembler write {span.hook.source or span.hook.name} at "
                    f"PC [0x{span.start_pc:X}, 0x{span.end_pc:X}) overlaps "
                    f"Yaze-editable {name} [0x{start:X}, 0x{end:X})"
                )


# ---------------------------------------------------------------------------
# Main manifest generation
# ---------------------------------------------------------------------------

def _resolve_repo_path(root: Path, path: Path) -> Path:
    """Resolve a CLI/API path relative to the Oracle repository root."""
    return (root / path).resolve() if not path.is_absolute() else path.resolve()


def _manifest_path(
    manifest_root: Path,
    path: Path,
    *,
    require_relative: bool = False,
) -> str:
    """Express a filesystem path in the manifest's declared namespace."""
    resolved_root = manifest_root.resolve()
    resolved_path = path.resolve()
    if resolved_path.is_relative_to(resolved_root):
        return resolved_path.relative_to(resolved_root).as_posix()
    if require_relative:
        raise ManifestGenerationError(
            f"Manifest path escapes declared root {resolved_root}: "
            f"{resolved_path}"
        )
    return str(resolved_path)


def _source_manifest_path(
    root: Path,
    manifest_root: Path,
    path: Path,
    *,
    require_relative: bool,
) -> str:
    """Map a repository-relative source into the manifest namespace."""
    return _manifest_path(
        manifest_root,
        root / path,
        require_relative=require_relative,
    )


def _rebase_source_locations(value: object, source_prefix: Path) -> None:
    """Rebase `path:line` provenance strings beneath a bundle source prefix."""
    if source_prefix == Path("."):
        return
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "source" and isinstance(child, str):
                source_path, separator, line = child.rpartition(":")
                if separator and line.isdigit():
                    value[key] = (
                        f"{(source_prefix / source_path).as_posix()}:{line}"
                    )
                    continue
            _rebase_source_locations(child, source_prefix)
    elif isinstance(value, list):
        for child in value:
            _rebase_source_locations(child, source_prefix)


def generate_manifest(
    root: Path,
    rom_path: Optional[Path] = None,
    dev_rom_path: Optional[Path] = None,
    hooks_path: Optional[Path] = None,
    manifest_root: Optional[Path] = None,
) -> dict:
    """Generate the complete hack manifest.

    Hook source:
    - `hooks_path` set: exact mode. Load z3asm hooks.json, require its
      recorded output hash to match `rom_path`, and protect exact spans.
    - `hooks_path` None: python-scan mode (asar compatibility). Scan reachable
      sources and protect estimated spans, as before.
    """
    root = root.resolve()
    explicit_manifest_root = manifest_root is not None
    manifest_root = _resolve_repo_path(
        root,
        manifest_root or root,
    )
    if explicit_manifest_root and not root.is_relative_to(manifest_root):
        raise ManifestGenerationError(
            f"Repository root {root} is outside manifest root "
            f"{manifest_root}"
        )
    source_prefix = root.relative_to(manifest_root)
    exact_mode = hooks_path is not None
    if exact_mode and rom_path is None:
        raise ManifestGenerationError(
            "Exact hook mode requires the patched ROM (--rom) that the hooks "
            "were emitted for"
        )
    if rom_path is not None:
        rom_path = _resolve_repo_path(root, rom_path)
        if not rom_path.is_file():
            raise ManifestGenerationError(
                f"Patched ROM not found: {rom_path}"
            )

    explicit_dev_rom = dev_rom_path is not None
    dev_rom_path = _resolve_repo_path(
        root,
        dev_rom_path or Path("Roms/oos168.sfc"),
    )
    if explicit_dev_rom and not dev_rom_path.is_file():
        raise ManifestGenerationError(
            f"Editable dev ROM not found: {dev_rom_path}"
        )
    if exact_mode and not dev_rom_path.is_file():
        raise ManifestGenerationError(
            f"Exact hook mode requires the editable dev ROM: {dev_rom_path}"
        )

    reachable_sources = collect_reachable_asm_sources(root)

    # Load defines for conditional compilation evaluation
    defines = _load_global_defines(root)
    asm_sources = reachable_sources

    exact_spans: list[ExactSpan] = []
    if exact_mode:
        hooks_path = _resolve_repo_path(root, hooks_path)
        exact_spans, exact_provenance = load_exact_hooks(hooks_path, rom_path)
        hooks = [span.hook for span in exact_spans]
        hook_source = {
            "mode": "z3asm-hooks",
            "exact": True,
            "path": _manifest_path(root, hooks_path),
            "sha256": exact_provenance["hooks_sha256"],
            "patched_rom_sha256": exact_provenance["patched_rom_sha256"],
            "patched_rom_size": exact_provenance["patched_rom_size"],
            "note": "Producer-verified: hooks.json records the SHA-256 of the patched ROM it was emitted with. Yaze does not read or enforce this block.",
        }
    else:
        # Scan only the source graph assembled from Oracle_main.asm. Local
        # ignored assets and archived experiments must not claim ROM ownership.
        hooks = scan_hooks(root, asm_sources)
        hook_source = {
            "mode": "python-scan",
            "exact": False,
            "generator": "generate_hooks_json.scan_hooks",
            "note": "Source scan with estimated hook sizes (asar compatibility). Protected regions are approximate.",
        }

    # Build manifest sections
    manifest: dict = {
        "manifest_version": 3,
        "hack_name": "Oracle of Secrets",
        "hack_version": "dev",
        "generator": "generate_hack_manifest.py",
    }

    # Build pipeline model
    manifest["build_pipeline"] = {
        "description": "Yaze edits the dev ROM; asar patches it to produce the patched ROM. They share the same base file.",
        "dev_rom": _manifest_path(
            manifest_root,
            dev_rom_path,
            require_relative=explicit_manifest_root,
        ),
        "patched_rom": (
            _manifest_path(
                manifest_root,
                rom_path,
                require_relative=explicit_manifest_root,
            )
            if rom_path is not None
            else _source_manifest_path(
                root,
                manifest_root,
                Path("Roms/oos168x.sfc"),
                require_relative=explicit_manifest_root,
            )
        ),
        "assembler": "z3asm" if exact_mode else "asar",
        "entry_point": _source_manifest_path(
            root,
            manifest_root,
            MANIFEST_ENTRY_POINT,
            require_relative=explicit_manifest_root,
        ),
        "build_script": _source_manifest_path(
            root,
            manifest_root,
            Path("Scripts/Build/build_rom.sh"),
            require_relative=explicit_manifest_root,
        ),
        "flow": [
            "1. Yaze edits dev ROM data and tracked source artifacts, including the canonical expanded-message bundle and generated include",
            "2. asar reads the dev ROM and tracked ASM sources",
            "3. asar writes patched ROM with all org/freedata applied",
            "4. Patched ROM is the playable output",
        ],
        "key_insight": "Hook addresses in the dev ROM are overwritten by asar on every build. Yaze edits to these addresses are silently lost. The manifest identifies which addresses belong to which layer.",
    }

    # ROM metadata (patched ROM for verification, dev ROM for editing)
    rom_meta: dict = {}
    if rom_path and rom_path.exists():
        rom_meta["path"] = _manifest_path(
            manifest_root,
            rom_path,
            require_relative=explicit_manifest_root,
        )
        try:
            data = rom_path.read_bytes()
            rom_meta["sha1"] = hashlib.sha1(data).hexdigest()
            rom_meta["size"] = len(data)
        except OSError as exc:
            raise ManifestGenerationError(
                f"Unable to read patched ROM {rom_path}: {exc}"
            ) from exc

    # Also hash the exact editable ROM selected by the build, if it exists.
    if dev_rom_path.exists():
        try:
            dev_data = dev_rom_path.read_bytes()
            rom_meta["dev_rom_sha1"] = hashlib.sha1(dev_data).hexdigest()
            rom_meta["dev_rom_size"] = len(dev_data)
        except OSError as exc:
            raise ManifestGenerationError(
                f"Unable to read editable dev ROM {dev_rom_path}: {exc}"
            ) from exc
    manifest["rom"] = rom_meta
    manifest["hook_source"] = hook_source

    if dev_rom_path.exists():
        manifest["dungeon_stream_regions"] = derive_dungeon_stream_regions(
            dev_rom_path
        )
        editor_regions = derive_editor_managed_regions(dev_rom_path)
        if exact_mode:
            # Exact spans: check every byte, in every bank, against every
            # range Yaze writes.
            _validate_exact_spans_disjoint_from_editable(
                exact_spans,
                _yaze_editable_pc_ranges(
                    editor_regions, manifest["dungeon_stream_regions"]
                ),
            )
        else:
            # Estimated spans: start-address rule for expanded hooks.
            _validate_expanded_hooks_disjoint_from_editor_regions(
                hooks, editor_regions
            )
        _validate_unresolved_org_proofs(
            scan_org_directives(root, asm_sources), editor_regions
        )
        manifest["editor_managed_regions"] = {
            "description": (
                "Exact yaze-owned dungeon metadata and custom-collision "
                "ranges derived from the editable dev ROM. The WaterFill "
                "tail beginning at $25:E000 remains ASM-owned, and protected "
                "hooks still take precedence."
            ),
            "regions": editor_regions,
        }

    # Protected regions — these are hook addresses in VANILLA banks.
    # Asar overwrites these on build, so yaze edits here are lost.
    # Separate from owned_banks which are entirely ASM-owned.
    vanilla_hooks = [
        h
        for h in hooks
        if ((_physical_org_address(h.address) >> 16) & 0xFF) < 0x1E
    ]
    expanded_hooks = [
        h
        for h in hooks
        if ((_physical_org_address(h.address) >> 16) & 0xFF) >= 0x1E
    ]
    # Bank ownership — expanded banks with ownership classification
    banks = scan_bank_ownership(root, asm_sources)
    if exact_mode:
        owned_bank_numbers = {
            int(bank["bank"], 16)
            for bank in banks
            if bank.get("ownership") in OWNED_BANK_TYPES
        }
        protected_spans = [
            span
            for span in exact_spans
            if not _span_banks(span.start_pc, span.end_pc) <= owned_bank_numbers
        ]
        protected = compute_exact_protected_regions(protected_spans)
        protected_description = (
            "Exact byte spans the assembler writes on every build, in vanilla "
            "banks ($00-$1D) and in shared or unclassified expanded banks. "
            "Spans merge only when they overlap or touch; unwritten gaps stay "
            "editable. Banks marked asm_owned/asm_expansion are covered by "
            "owned_banks instead."
        )
    else:
        protected = (
            compute_protected_regions(vanilla_hooks) if vanilla_hooks else []
        )
        protected_description = "Hook addresses within vanilla ROM banks ($00-$1D). Asar patches these on every build, so yaze edits at these addresses are silently overwritten. Yaze should either skip these during save or warn the user."
    # Graphics-only free space for yaze sheet relocation (scawful approved
    # 2026-09-26). Bank $23 (PC 0x118000-0x11FFFF, 32 KB of 0x00) is not owned,
    # not protected, and asar writes nothing there. yaze allows only these three
    # keys; "end" is exclusive; it must stay disjoint from dungeon_stream_regions.
    manifest["graphics_sheet_regions"] = {
        "description": "Graphics-only free space: bank $23 (PC 0x118000-0x11FFFF), 32 KB of 0x00, not owned or protected; asar writes nothing there.",
        "allocation_regions": [{"start": "0x238000", "end": "0x248000"}],
        "reserved_sheets": ["0x7B", "0x7C"],
    }

    manifest["protected_regions"] = {
        "description": protected_description,
        "exact": exact_mode,
        "count": len(protected),
        "vanilla_hook_count": len(vanilla_hooks),
        "expanded_hook_count": len(expanded_hooks),
        "total_hooks": len(hooks),
        "regions": protected,
    }

    manifest["owned_banks"] = {
        "description": "Expanded ROM banks with ownership classification. 'asm_owned' banks are fully owned by ASM. 'shared' banks (e.g., $28 ZSCustomOverworld) contain data that yaze writes AND ASM patches on top — yaze can edit these but must rebuild after. 'asm_expansion' banks only exist in the patched ROM.",
        "ownership_types": {
            "asm_owned": "Fully owned by ASM hack — yaze should not write here",
            "shared": "Both yaze and ASM write — yaze edits base data, ASM patches hooks on top. Must rebuild after yaze save.",
            "asm_expansion": "ROM expansion bank — only exists in patched ROM, not in dev ROM",
            "ram": "WRAM variable definitions (not ROM data)",
        },
        "banks": banks,
    }

    # Message layout — the expanded message data lives in bank $2F (ASM-owned),
    # but the vanilla message region ($0E) is shared: yaze can edit vanilla messages
    # in the dev ROM, and the ASM expansion hook redirects reads for IDs >= $18D.
    messages = scan_message_layout(root)
    if messages:
        manifest["messages"] = {
            "description": "Expanded message system. Vanilla messages ($000-$18C) live in bank $0E of the dev ROM — yaze can edit these. Expanded messages ($18D+) live in ASM-owned bank $2F. Direct editor or CLI writes to expanded ROM data are not durable because the next ASM rebuild replaces bank $2F. Use the canonical source bundle and generated include instead.",
            "editing_guidance": {
                "vanilla_safe": "Message IDs $000-$18C can be edited in the dev ROM via yaze",
                "expanded_asm_owned": "Message IDs $18D+ are in ASM-owned bank $2F. Update Data/dialogue/expanded_messages.json and regenerate Core/Generated/expanded_messages.asm through Yaze source sync, rebuild with Scripts/Build/build_rom.sh 168, then reopen or reload Roms/oos168x.sfc for inspection. Do not edit the patched ROM directly.",
                "hook_address": "$0ED436 (do not overwrite — asar patches this)",
            },
            "source": {
                "format": "yaze-message-bundle",
                "version": 1,
                "canonical_bundle_path": _source_manifest_path(
                    root,
                    manifest_root,
                    EXPANDED_MESSAGE_BUNDLE,
                    require_relative=explicit_manifest_root,
                ),
                "generated_asm_include_path": _source_manifest_path(
                    root,
                    manifest_root,
                    EXPANDED_MESSAGE_ASM_INCLUDE,
                    require_relative=explicit_manifest_root,
                ),
            },
            **messages,
        }

    manifest["minecart_tracks"] = {
        "source": {
            **MINECART_TRACK_SOURCE_CONTRACT,
            "path": _source_manifest_path(
                root,
                manifest_root,
                MINECART_TRACK_SOURCE,
                require_relative=explicit_manifest_root,
            ),
        },
    }

    # Room tags — the dispatch table at $01CC00-$01CC5A is in vanilla bank $01.
    # Asar patches specific 4-byte slots (JML instructions). Yaze's room editor
    # assigns tag IDs to rooms; this manifest tells yaze what each tag ID means.
    room_tags = scan_room_tags(root, defines, asm_sources)
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
        "config_file": _source_manifest_path(
            root,
            manifest_root,
            Path("Config/feature_flags.asm"),
            require_relative=explicit_manifest_root,
        ),
        "flags": flags,
    }

    # SRAM layout — custom variable definitions that yaze can use for
    # the RAM panel, save state inspector, and debugging overlays.
    sram = scan_sram_layout(root)
    manifest["sram"] = {
        "description": "Custom SRAM variable definitions from Core/sram.asm. These extend the vanilla ALTTP save file layout. Yaze can display variable names in the RAM panel and save state inspector instead of raw hex addresses.",
        "source_file": _source_manifest_path(
            root,
            manifest_root,
            Path("Core/sram.asm"),
            require_relative=explicit_manifest_root,
        ),
        "variable_count": len(sram),
        "variables": sram,
    }

    # Ownership evidence is additive metadata, never an editor-write grant.
    ledger_path = root / "Config/allocation_ownership.json"
    if ledger_path.is_file():
        from allocation_contracts import AllocationError, read_ledger, validate_draft
        try:
            ledger = read_ledger(ledger_path)
            draft_path = root / "Config/overworld_layout_192.draft.json"
            draft = json.loads(draft_path.read_text())
            draft_status = validate_draft(draft, current_tables=ledger['tables'])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ManifestGenerationError(f"Allocation metadata invalid: {exc}") from exc
        manifest["allocation_contracts"] = {
            "schema_version": 1,
            "evidence_status": "requires_validate_allocation_contracts",
            "allocation_available": False,
            "ledger_sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
            "ledger": ledger,
            "draft_sha256": hashlib.sha256(draft_path.read_bytes()).hexdigest(),
            "draft": draft,
            "draft_validation": draft_status,
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

    _rebase_source_locations(manifest, source_prefix)
    return manifest


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
        help=(
            "Patched ROM path for metadata "
            "(default: Roms/oos168x.sfc when present)"
        ),
    )
    parser.add_argument(
        "--dev-rom",
        type=Path,
        help=(
            "Editable base ROM selected by the build "
            "(default: Roms/oos168.sfc)"
        ),
    )
    parser.add_argument(
        "--manifest-root",
        type=Path,
        help=(
            "Filesystem root used for every path in the manifest. When set, "
            "all ROM and source paths must remain beneath this root."
        ),
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
    # Hook source: exactly one is required; no implicit hooks.json reuse.
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--hooks",
        type=Path,
        help=(
            "z3asm hooks.json emitted with the patched ROM. Exact mode: its "
            "rom.sha256 must match --rom, which is then required."
        ),
    )
    source.add_argument(
        "--hook-source",
        choices=("python-scan",),
        help="Scan sources for hooks with estimated sizes (asar builds).",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    output = (root / args.output).resolve() if not args.output.is_absolute() else args.output

    rom_path = args.rom
    if args.hooks is not None and rom_path is None:
        print(
            "error: --hooks requires --rom (the patched ROM the hooks were "
            "emitted with)",
            file=sys.stderr,
        )
        return 2
    if rom_path is None:
        default_rom_path = root / "Roms" / "oos168x.sfc"
        rom_path = default_rom_path if default_rom_path.is_file() else None

    try:
        manifest = generate_manifest(
            root,
            rom_path,
            args.dev_rom,
            hooks_path=args.hooks,
            manifest_root=args.manifest_root,
        )
    except ManifestGenerationError as exc:
        print(f"error: cannot generate hack manifest: {exc}", file=sys.stderr)
        return 1

    # Write atomically: a failed or interrupted run keeps the previous file.
    indent = None if args.compact else 2
    temp_output = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    try:
        temp_output.write_text(json.dumps(manifest, indent=indent) + "\n")
        os.replace(temp_output, output)
    finally:
        if temp_output.exists():
            temp_output.unlink()

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
