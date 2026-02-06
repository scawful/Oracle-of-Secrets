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
    "build", "bin", "obj", "Tools", "tools", "tests", "node_modules",
    "ZScreamNew",
}


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

def compute_protected_regions(hooks: list[HookEntry]) -> list[dict]:
    """Group hooks into contiguous protected address ranges."""
    if not hooks:
        return []

    # Sort hooks by address
    sorted_hooks = sorted(hooks, key=lambda h: h.address)

    # Estimate size of each hook (conservative: 4 bytes for JML/JSL, 1-8 for data/patch)
    SIZE_ESTIMATE = {
        "jsl": 4,
        "jml": 4,
        "jsr": 3,
        "jmp": 3,
        "data": 8,   # conservative
        "patch": 4,   # conservative
    }

    regions = []
    current_start = sorted_hooks[0].address
    current_end = current_start + SIZE_ESTIMATE.get(sorted_hooks[0].kind, 4)
    current_hooks = [sorted_hooks[0]]

    for hook in sorted_hooks[1:]:
        hook_end = hook.address + SIZE_ESTIMATE.get(hook.kind, 4)

        # Merge if within 16 bytes of the previous region (likely related)
        if hook.address <= current_end + 16:
            current_end = max(current_end, hook_end)
            current_hooks.append(hook)
        else:
            # Emit previous region
            regions.append({
                "start": f"0x{current_start:06X}",
                "end": f"0x{current_end:06X}",
                "size": current_end - current_start,
                "hook_count": len(current_hooks),
                "module": current_hooks[0].module,
            })
            current_start = hook.address
            current_end = hook_end
            current_hooks = [hook]

    # Emit last region
    regions.append({
        "start": f"0x{current_start:06X}",
        "end": f"0x{current_end:06X}",
        "size": current_end - current_start,
        "hook_count": len(current_hooks),
        "module": current_hooks[0].module,
    })

    return regions


# ---------------------------------------------------------------------------
# Main manifest generation
# ---------------------------------------------------------------------------

def generate_manifest(root: Path, rom_path: Optional[Path] = None) -> dict:
    """Generate the complete hack manifest."""
    import hashlib

    # Load defines for conditional compilation evaluation
    defines = _load_global_defines(root)

    # Scan hooks (reuse existing infrastructure)
    hooks = scan_hooks(root)

    # Build manifest sections
    manifest: dict = {
        "manifest_version": 2,
        "hack_name": "Oracle of Secrets",
        "hack_version": "dev",
        "generator": "generate_hack_manifest.py",
    }

    # Build pipeline model
    manifest["build_pipeline"] = {
        "description": "Yaze edits the dev ROM; asar patches it to produce the patched ROM. They share the same base file.",
        "dev_rom": "Roms/oos168.sfc",
        "patched_rom": "Roms/oos168x.sfc",
        "assembler": "asar",
        "entry_point": "Meadow_main.asm",
        "build_script": "scripts/build_rom.sh",
        "flow": [
            "1. Yaze edits dev ROM (room data, sprites, palettes, messages)",
            "2. asar reads dev ROM + ASM sources",
            "3. asar writes patched ROM with all org/freedata applied",
            "4. Patched ROM is the playable output",
        ],
        "key_insight": "Hook addresses in the dev ROM are overwritten by asar on every build. Yaze edits to these addresses are silently lost. The manifest identifies which addresses belong to which layer.",
    }

    # ROM metadata (patched ROM for verification, dev ROM for editing)
    rom_meta: dict = {}
    if rom_path and rom_path.exists():
        rom_meta["path"] = str(rom_path.relative_to(root)) if rom_path.is_relative_to(root) else str(rom_path)
        try:
            data = rom_path.read_bytes()
            rom_meta["sha1"] = hashlib.sha1(data).hexdigest()
            rom_meta["size"] = len(data)
        except Exception:
            pass
    # Also hash the dev ROM if it exists
    dev_rom_path = root / "Roms" / "oos168.sfc"
    if dev_rom_path.exists():
        try:
            dev_data = dev_rom_path.read_bytes()
            rom_meta["dev_rom_sha1"] = hashlib.sha1(dev_data).hexdigest()
            rom_meta["dev_rom_size"] = len(dev_data)
        except Exception:
            pass
    manifest["rom"] = rom_meta

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
            "description": "Expanded message system. Vanilla messages ($000-$18C) live in bank $0E of the dev ROM — yaze can edit these. Expanded messages ($18D+) live in bank $2F, owned by ASM. The hook at $0ED436 redirects message reads for expanded IDs. Yaze's message-write CLI can target expanded IDs if it knows the data region bounds.",
            "editing_guidance": {
                "vanilla_safe": "Message IDs $000-$18C can be edited in the dev ROM via yaze",
                "expanded_asm_owned": "Message IDs $18D+ are in bank $2F; edit via Core/message.asm or z3ed message-write CLI",
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate hack manifest for yaze editor integration"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Oracle repo root (default: repo root)",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("hack_manifest.json"),
        help="Output path (default: hack_manifest.json in repo root)",
    )
    parser.add_argument(
        "--rom",
        type=Path,
        default=Path("Roms/oos168x.sfc"),
        help="ROM path for metadata (optional)",
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
    if not rom_path.exists():
        rom_path = None

    manifest = generate_manifest(root, rom_path)

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
