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
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

# Import the existing hooks scanner infrastructure
from generate_hooks_json import (
    ELSE_DIRECTIVE_RE,
    ENDIF_DIRECTIVE_RE,
    IF_DIRECTIVE_RE,
    _eval_condition,
    filter_active_asm_sources,
    scan_hooks,
    _load_global_defines,
    _parse_define_assignment,
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
DUNGEON_ROOM_COUNT = 296
ROOM_HEADER_POINTER_PC = 0xB5DD
ROOM_HEADER_BANK_PC = 0xB5E7
ROOM_HEADER_SIZE = 14
DUNGEON_MESSAGE_IDS_PC = 0x3F61D


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
    defines = dict(global_defines)
    active = True
    stack: list[dict[str, object]] = []

    for line_number, line in enumerate(lines, start=1):
        directive = line.split(";", 1)[0].strip()
        match = IF_DIRECTIVE_RE.match(directive)
        if match:
            kind = match.group(1).lower()
            condition = _eval_condition(match.group(2).strip(), defines)
            condition_active = (
                bool(condition) if condition is not None else True
            )
            if kind == "if":
                parent_active = active
                branch_taken = parent_active and condition_active
                active = branch_taken
                stack.append({
                    "parent_active": parent_active,
                    "branch_taken": branch_taken,
                })
            elif stack:
                frame = stack[-1]
                parent_active = bool(frame["parent_active"])
                branch_taken = bool(frame["branch_taken"])
                active = (
                    parent_active
                    and not branch_taken
                    and condition_active
                )
                frame["branch_taken"] = branch_taken or active
            continue
        if ELSE_DIRECTIVE_RE.match(directive):
            if stack:
                frame = stack[-1]
                parent_active = bool(frame["parent_active"])
                branch_taken = bool(frame["branch_taken"])
                active = parent_active and not branch_taken
                frame["branch_taken"] = True
            continue
        if ENDIF_DIRECTIVE_RE.match(directive):
            if stack:
                frame = stack.pop()
                active = bool(frame["parent_active"])
            continue
        if not active:
            continue

        parsed_define = _parse_define_assignment(line)
        if parsed_define is not None:
            name, value = parsed_define
            defines[name] = value

        include_text = _parse_incsrc(line)
        if include_text is not None:
            yield line_number, include_text


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
    file and repo-root-relative paths. Follow only active conditional edges,
    gate disabled module roots before traversal, and fail closed if an active
    reachable include cannot be resolved.
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
            if not filter_active_asm_sources(
                resolved_root, [included], active_defines
            ):
                continue
            pending.append(included)

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
    source_paths = filter_active_asm_sources(root, candidate_paths)
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
    source_paths = filter_active_asm_sources(
        root, candidate_paths, defines
    )
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
    current_end = current_start + SIZE_ESTIMATE.get(sorted_hooks[0].kind, 4)
    current_hooks = [sorted_hooks[0]]

    for hook in sorted_hooks[1:]:
        hook_start = _snes_to_pc(hook.address)
        hook_end = hook_start + SIZE_ESTIMATE.get(hook.kind, 4)

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
    address &= 0x7FFFFF
    if (address & 0xFFFF) < 0x8000:
        address |= 0x8000
    return address


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
    if bank in (0x7E, 0x7F):
        raise ManifestGenerationError(
            f"{description} 0x{address:06X} points to WRAM"
        )
    if offset < 0x8000:
        raise ManifestGenerationError(
            f"{description} 0x{address:06X} is not a high-half LoROM pointer"
        )
    return ((bank & 0x7F) << 15) | (offset & 0x7FFF)


def _pc_to_snes(address: int) -> int:
    """Convert an unheadered PC offset to a canonical LoROM address."""
    if not 0 <= address < 0x400000:
        raise ManifestGenerationError(
            f"PC address 0x{address:X} is outside canonical LoROM"
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


def derive_editor_managed_regions(dev_rom_path: Path) -> list[dict]:
    """Derive exact room-header and message-ID ranges from the dev ROM."""
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
    _require_rom_span(
        data, ROOM_HEADER_BANK_PC, 1, "room-header pointer bank"
    )
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

    return [
        _editor_range(sorted_headers[0][0], sorted_headers[-1][1]),
        _editor_range(DUNGEON_MESSAGE_IDS_PC, messages_end_pc),
    ]


# ---------------------------------------------------------------------------
# Main manifest generation
# ---------------------------------------------------------------------------

def _resolve_repo_path(root: Path, path: Path) -> Path:
    """Resolve a CLI/API path relative to the Oracle repository root."""
    return (root / path).resolve() if not path.is_absolute() else path.resolve()


def _manifest_path(root: Path, path: Path) -> str:
    """Prefer portable repo-relative manifest paths when possible."""
    return (
        path.relative_to(root).as_posix()
        if path.is_relative_to(root)
        else str(path)
    )


def generate_manifest(
    root: Path,
    rom_path: Optional[Path] = None,
    dev_rom_path: Optional[Path] = None,
) -> dict:
    """Generate the complete hack manifest."""
    import hashlib

    root = root.resolve()
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

    reachable_sources = collect_reachable_asm_sources(root)

    # Load defines for conditional compilation evaluation
    defines = _load_global_defines(root)
    asm_sources = filter_active_asm_sources(
        root, reachable_sources, defines
    )

    # Scan only the source graph assembled from Oracle_main.asm. Local ignored
    # assets and archived experiments must not claim ROM ownership.
    hooks = scan_hooks(root, asm_sources)

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
        "dev_rom": _manifest_path(root, dev_rom_path),
        "patched_rom": (
            _manifest_path(root, rom_path)
            if rom_path is not None
            else "Roms/oos168x.sfc"
        ),
        "assembler": "asar",
        "entry_point": str(MANIFEST_ENTRY_POINT),
        "build_script": "Scripts/Build/build_rom.sh",
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
        rom_meta["path"] = _manifest_path(root, rom_path)
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

    if dev_rom_path.exists():
        manifest["editor_managed_regions"] = {
            "description": (
                "Exact room-header and per-room message-ID ranges derived "
                "from the editable dev ROM. Protected hooks still take "
                "precedence."
            ),
            "regions": derive_editor_managed_regions(dev_rom_path),
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
    banks = scan_bank_ownership(root, asm_sources)
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
                "canonical_bundle_path": str(EXPANDED_MESSAGE_BUNDLE),
                "generated_asm_include_path": str(
                    EXPANDED_MESSAGE_ASM_INCLUDE
                ),
            },
            **messages,
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

    rom_path = args.rom
    if rom_path is None:
        default_rom_path = root / "Roms" / "oos168x.sfc"
        rom_path = default_rom_path if default_rom_path.is_file() else None

    try:
        manifest = generate_manifest(root, rom_path, args.dev_rom)
    except ManifestGenerationError as exc:
        print(f"error: cannot generate hack manifest: {exc}", file=sys.stderr)
        return 1

    indent = None if args.compact else 2
    output.write_text(json.dumps(manifest, indent=indent) + "\n")

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
