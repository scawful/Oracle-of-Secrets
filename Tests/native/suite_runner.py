#!/usr/bin/env python3
"""Data-driven Mesen2 runtime suite for Oracle of Secrets.

One JSON manifest names the scenarios. This runner turns them into the same
DiagnosticReport shape `z3ed oracle-doctor` uses (`finding_key`, `jump_target`,
baseline ratchet) and, unless `--dry-run`, plays them through
`Scripts/Agents/native_session.py` so the heavy lock is held for the whole run.

Scenario kinds dispatch through `HANDLERS`. Each handler is a short sequence of
`Runtime` calls. `MesenRuntime` is the only object that opens Mesen2.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import sys
import tempfile
import time
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOL = "oos-runtime-suite"
KINDS = (
    "save_quit_matrix",
    "entrance_roundtrip",
    "warp_landing",
    "vblank_budget",
    "dialogue_trigger",
)
SEVERITIES = ("info", "warning", "error", "critical")
JUMP_KINDS = ("overworld", "dungeon", "message")
FORMS = ("link", "gbc")
TRANSPORTS = ("whirlpool", "bird", "portal")
MECHANICS = ("epona", "korl", "deku", "zora", "gust")
# FileSelect_IsSlotGbcEligible: GameState < !GameState_FaroreRescued.
FARORE_RESCUED = 0x03
# GameboyLinkPalette+4, the second color copied to $7EC604 for an Abyss slot.
GBC_PREVIEW_WORD = 0x237E
GBC_PREVIEW_ADDR = 0x7EC604
PLAYABLE = (0x07, 0x09, 0x0B)
REPORT_KEYS = (
    "tool",
    "suite_name",
    "rom_sha256",
    "total_scenarios",
    "passed",
    "failed",
    "baselined",
    "total_findings",
    "error_count",
    "warning_count",
    "findings",
    "new_findings",
    "baselined_findings",
    "resolved_findings",
)
FINDING_KEYS = (
    "id",
    "finding_key",
    "severity",
    "suite",
    "message",
    "location",
    "jump_target",
    "fixable",
)
CARD_FIELDS = ("id", "title", "badge", "summary")

MODULE = 0x7E0010
SUB = 0x7E0011
BRIGHT = 0x7E0013
INDOORS = 0x7E001B
LINK_Y = 0x7E0020
LINK_X = 0x7E0022
LINK_STATE = 0x7E005D
AREA = 0x7E008A
ROOM = 0x7E00A0
LINK_GFX = 0x7E00BC
SWIMMING = 0x7E0345
MASK = 0x7E02B2
CHOICE = 0x7E1CE8
MESSAGE = 0x7E1CF0
GAME_STATE = 0x7EF3C5
SAVED_WORLD = 0x7EF3CA
SRAM_BASE = 0x7EF000

DEFAULT_SEED = Path.home() / "src/hobby/oracle-of-secrets-scratch/claude-d8-boss-20261116/fixture.srm"
MESEN_CLIENT = Path("/Users/scawful/src/hobby/mesen2-oos/tools/oos_client")


def parse_int(value) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"not an integer: {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise ValueError(f"not an integer: {value!r}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# ---------------------------------------------------------------- PNG frames


def _paeth(left: int, up: int, up_left: int) -> int:
    estimate = left + up - up_left
    distances = (abs(estimate - left), abs(estimate - up), abs(estimate - up_left))
    if distances[0] <= distances[1] and distances[0] <= distances[2]:
        return left
    if distances[1] <= distances[2]:
        return up
    return up_left


def decode_png(blob: bytes) -> tuple[int, int, list[bytes]]:
    """Return width, height, and tightly packed RGB rows. 8-bit gray/RGB/RGBA."""
    if not blob.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("screenshot is not a PNG")
    pos = 8
    ihdr = None
    idat = []
    while pos + 8 <= len(blob):
        length = struct.unpack(">I", blob[pos:pos + 4])[0]
        tag = blob[pos + 4:pos + 8]
        data = blob[pos + 8:pos + 8 + length]
        pos += 12 + length
        if tag == b"IHDR":
            ihdr = data
        elif tag == b"IDAT":
            idat.append(data)
        elif tag == b"IEND":
            break
    if ihdr is None or not idat:
        raise ValueError("PNG is missing IHDR or IDAT")
    width, height, bit, color, _comp, _filt, inter = struct.unpack(">IIBBBBB", ihdr)
    if inter or bit != 8 or color not in (0, 2, 6):
        raise ValueError(f"unsupported PNG {width}x{height} color {color}")
    channels = {0: 1, 2: 3, 6: 4}[color]
    raw = zlib.decompress(b"".join(idat))
    stride = width * channels
    rows: list[bytes] = []
    cursor = 0
    previous = bytearray(stride)
    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        row = bytearray(raw[cursor:cursor + stride])
        cursor += stride
        for x in range(stride):
            left = row[x - channels] if x >= channels else 0
            up = previous[x]
            up_left = previous[x - channels] if x >= channels else 0
            if filter_type == 0:
                extra = 0
            elif filter_type == 1:
                extra = left
            elif filter_type == 2:
                extra = up
            elif filter_type == 3:
                extra = (left + up) // 2
            elif filter_type == 4:
                extra = _paeth(left, up, up_left)
            else:
                raise ValueError(f"bad PNG filter {filter_type}")
            row[x] = (row[x] + extra) & 0xFF
        previous = row
        rgb = bytearray()
        for x in range(0, stride, channels):
            pixel = row[x:x + 3] if channels > 1 else bytes((row[x], row[x], row[x]))
            rgb += pixel
        rows.append(bytes(rgb))
    return width, height, rows


def encode_png(width: int, height: int, rgb: bytes) -> bytes:
    if len(rgb) != width * height * 3:
        raise ValueError("RGB buffer does not match the frame size")

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    raw = b"".join(b"\x00" + rgb[y * width * 3:(y + 1) * width * 3] for y in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def frame_png(blob: bytes, width: int = 256, height: int = 224) -> bytes:
    """Nearest-neighbor a screenshot to the SNES 256×224 frame."""
    src_w, src_h, rows = decode_png(blob)
    if (src_w, src_h) == (width, height):
        return encode_png(width, height, b"".join(rows))
    out = bytearray()
    for y in range(height):
        src = rows[min(src_h - 1, y * src_h // height)]
        for x in range(width):
            sx = min(src_w - 1, x * src_w // width)
            out += src[sx * 3:sx * 3 + 3]
    return encode_png(width, height, bytes(out))


def leading_black_scanlines(blob: bytes, threshold: int = 12) -> tuple[int, bool]:
    """Leading fully-dark rows, and whether the whole frame is dark."""
    _w, height, rows = decode_png(blob)
    count = 0
    for row in rows:
        if all(channel <= threshold for channel in row):
            count += 1
        else:
            break
    return count, height > 0 and count == height


# ---------------------------------------------------------------- checkpoints / SRAM


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def checkpoint_table(path: Path) -> dict[str, dict]:
    document = load_json(path)
    table = {}
    for entry in document.get("checkpoints", []):
        if isinstance(entry, dict) and entry.get("id"):
            table[entry["id"]] = entry
    return table


def resolve_writes(table: dict[str, dict], checkpoint_id: str) -> list[dict]:
    """Oldest `after` ancestor first, matching Data/debug/checkpoints.json."""
    order: list[dict] = []
    seen: set[str] = set()

    def walk(name: str) -> None:
        if name in seen:
            return
        entry = table.get(name)
        if entry is None:
            raise KeyError(name)
        parent = entry.get("after")
        if parent:
            walk(parent)
        seen.add(name)
        order.append(entry)

    walk(checkpoint_id)
    writes: list[dict] = []
    for entry in order:
        writes.extend(entry.get("writes") or [])
    return writes


def apply_write_list(memory: dict[int, int], writes: list[dict]) -> None:
    for item in writes:
        addr = parse_int(item["addr"])
        current = memory.get(addr, 0)
        if "value" in item:
            current = parse_int(item["value"])
        if "set_bits" in item:
            current |= parse_int(item["set_bits"])
        if "clear_bits" in item:
            current &= ~parse_int(item["clear_bits"])
        memory[addr] = current & 0xFF


def seal_checksum(slot: bytearray) -> None:
    """Adjust the last word so the 0x500-byte slot sums to the ALTTP 0x5A5A sentinel."""
    slot[0x4FE] = 0
    slot[0x4FF] = 0
    total = sum(int.from_bytes(slot[i:i + 2], "little") for i in range(0, 0x500, 2)) & 0xFFFF
    adjust = (0x5A5A - total) & 0xFFFF
    slot[0x4FE] = adjust & 0xFF
    slot[0x4FF] = adjust >> 8


def slot_report(sram: bytes) -> dict:
    slot = sram[:0x500]
    total = sum(int.from_bytes(slot[i:i + 2], "little") for i in range(0, 0x500, 2)) & 0xFFFF
    game_state = slot[0x3C5] if len(slot) > 0x3C5 else None
    saved_world = slot[0x3CA] if len(slot) > 0x3CA else None
    valid = len(sram) >= 0x3E7 and slot[0x3E5] == 0xAA and slot[0x3E6] == 0x55
    gbc = bool(valid and saved_world not in (None, 0) and game_state is not None and game_state < FARORE_RESCUED)
    return {
        "length": len(sram),
        "valid": valid,
        "checksum": total,
        "checksum_ok": total == 0x5A5A,
        "mirror_ok": len(sram) >= 0x1400 and slot == sram[0xF00:0x1400],
        "game_state": game_state,
        "saved_world": saved_world,
        "gbc": gbc,
    }


# ---------------------------------------------------------------- findings


def finding_key(kind: str, scenario_id: str, check: str) -> str:
    return f"{kind}.{scenario_id}.{check}"


def make_finding(scenario: dict, check: str, severity: str, message: str, location: str) -> dict:
    kind = scenario.get("kind") if scenario.get("kind") in KINDS else "schema"
    target = scenario.get("jump_target") if isinstance(scenario.get("jump_target"), dict) else {
        "kind": "overworld", "id": 0, "x": 0, "y": 0,
    }
    return {
        "id": f"{scenario.get('id', 'suite')}.{check}",
        "finding_key": finding_key(kind, str(scenario.get("id", "suite")), check),
        "severity": severity,
        "suite": kind if kind in KINDS else str(scenario.get("kind", "schema")),
        "message": message,
        "location": location,
        "jump_target": {
            "kind": target.get("kind"),
            "id": target.get("id"),
            "x": target.get("x"),
            "y": target.get("y"),
        },
        "fixable": False,
    }


def normalize_finding(raw: dict) -> dict:
    target = raw.get("jump_target") or {}
    kind = raw.get("suite") if raw.get("suite") in KINDS else "schema"
    scenario_id = str(raw.get("id", "suite")).split(".", 1)[0]
    check = str(raw.get("id", "finding")).split(".", 1)[-1]
    key = raw.get("finding_key") or finding_key(kind, scenario_id, check)
    return {
        "id": raw.get("id") or f"{scenario_id}.{check}",
        "finding_key": key,
        "severity": raw.get("severity") if raw.get("severity") in SEVERITIES else "error",
        "suite": raw.get("suite") or kind,
        "message": raw.get("message") or "",
        "location": raw.get("location") or "",
        "jump_target": {
            "kind": target.get("kind"),
            "id": target.get("id"),
            "x": target.get("x"),
            "y": target.get("y"),
        },
        "fixable": False,
    }


def classify(findings: list[dict], baseline: dict | None) -> dict:
    current = [normalize_finding(item) for item in findings]
    current.sort(key=lambda item: item["finding_key"])
    if baseline is None:
        return {
            "findings": current,
            "new_findings": list(current),
            "baselined_findings": [],
            "resolved_findings": [],
        }
    previous = [normalize_finding(item) for item in baseline.get("findings", [])]
    known = {item["finding_key"] for item in previous}
    have = {item["finding_key"] for item in current}
    return {
        "findings": current,
        "new_findings": [item for item in current if item["finding_key"] not in known],
        "baselined_findings": [item for item in current if item["finding_key"] in known],
        "resolved_findings": [item for item in previous if item["finding_key"] not in have],
    }


def build_report(suite_name: str, rom_sha: str | None, scenarios: int, passed: int,
                 failed: int, classified: dict) -> dict:
    findings = classified["findings"]
    return {
        "tool": TOOL,
        "suite_name": suite_name,
        "rom_sha256": rom_sha,
        "total_scenarios": scenarios,
        "passed": passed,
        "failed": failed,
        "baselined": len(classified["baselined_findings"]),
        "total_findings": len(findings),
        "error_count": sum(1 for item in findings if item["severity"] in ("error", "critical")),
        "warning_count": sum(1 for item in findings if item["severity"] == "warning"),
        "findings": findings,
        "new_findings": classified["new_findings"],
        "baselined_findings": classified["baselined_findings"],
        "resolved_findings": classified["resolved_findings"],
    }


def exit_code(report: dict, *, baseline_set: bool, strict: bool) -> int:
    if strict and (report["error_count"] or report["warning_count"]):
        return 1
    if not baseline_set:
        return 1 if report["failed"] else 0
    fresh = [item for item in report["new_findings"] if item["severity"] in ("error", "critical")]
    return 1 if fresh else 0


def format_text(report: dict) -> str:
    lines = [
        f"{report['tool']} {report['suite_name']}",
        f"rom {report['rom_sha256'] or '-'}",
        (f"scenarios {report['passed']}/{report['total_scenarios']} passed, "
         f"{report['failed']} failed, {report['baselined']} baselined"),
        (f"findings {report['total_findings']} "
         f"({report['error_count']} error, {report['warning_count']} warning)"),
    ]
    for item in report["findings"]:
        lines.append(f"[{item['severity']}] {item['finding_key']}: {item['message']} ({item['location']})")
    lines.append(
        f"new {len(report['new_findings'])}, "
        f"baselined {len(report['baselined_findings'])}, "
        f"resolved {len(report['resolved_findings'])}"
    )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- schema


def card_meta(scenario: dict) -> dict | None:
    raw = scenario.get("retroid_card")
    if raw is True:
        raw = scenario.get("card")
    if not raw:
        return None
    if not isinstance(raw, dict):
        raise ValueError("retroid_card must be an object or true")
    return raw


def _jump_errors(scenario: dict) -> list[str]:
    target = scenario.get("jump_target")
    if not isinstance(target, dict):
        return ["jump_target object is required"]
    errors = []
    if target.get("kind") not in JUMP_KINDS:
        errors.append("jump_target.kind must be overworld, dungeon, or message")
    for key in ("id", "x", "y"):
        try:
            parse_int(target.get(key))
        except (ValueError, TypeError):
            errors.append(f"jump_target.{key} must be an integer")
    return errors


def _write_errors(items, label: str) -> list[str]:
    if not isinstance(items, list) or not items:
        return [f"{label} must be a non-empty write list"]
    errors = []
    for index, item in enumerate(items):
        if not isinstance(item, dict) or "addr" not in item:
            errors.append(f"{label}[{index}] needs addr")
            continue
        if not any(key in item for key in ("value", "set_bits", "clear_bits")):
            errors.append(f"{label}[{index}] needs value, set_bits, or clear_bits")
    return errors


def validate_scenario(scenario: dict, checkpoints: dict[str, dict]) -> list[str]:
    if not isinstance(scenario, dict):
        return ["scenario is not an object"]
    errors = []
    name = scenario.get("id")
    if not isinstance(name, str) or not name:
        errors.append("id is required")
    kind = scenario.get("kind")
    if kind not in KINDS:
        errors.append(f"kind must be one of {', '.join(KINDS)}")
        return errors
    errors.extend(_jump_errors(scenario))
    if kind == "save_quit_matrix":
        errors.extend(_require_checkpoint(scenario, checkpoints))
        errors.extend(_spawn_errors(scenario.get("spawn"), "spawn"))
        expect = scenario.get("expect")
        if not isinstance(expect, dict):
            errors.append("expect object is required")
        else:
            if expect.get("file_select_form") not in FORMS:
                errors.append("expect.file_select_form must be link or gbc")
            for key in ("saved_world", "game_state"):
                try:
                    parse_int(expect.get(key))
                except (ValueError, TypeError):
                    errors.append(f"expect.{key} must be an integer")
        errors.extend(_write_errors(scenario.get("preserve"), "preserve"))
    elif kind == "entrance_roundtrip":
        errors.extend(_require_checkpoint(scenario, checkpoints))
        for key in ("entrance", "room", "parent_map"):
            try:
                parse_int(scenario.get(key))
            except (ValueError, TypeError):
                errors.append(f"{key} must be an integer")
    elif kind == "warp_landing":
        if scenario.get("transport") not in TRANSPORTS:
            errors.append("transport must be whirlpool, bird, or portal")
        for key in ("source_map", "dest_map", "via_room", "submodule"):
            try:
                parse_int(scenario.get(key))
            except (ValueError, TypeError):
                errors.append(f"{key} must be an integer")
    elif kind == "vblank_budget":
        if scenario.get("mechanic") not in MECHANICS:
            errors.append("mechanic must be epona, korl, deku, zora, or gust")
        for key in ("area", "via_room", "frames", "max_overruns", "max_black_scanlines"):
            try:
                parse_int(scenario.get(key))
            except (ValueError, TypeError):
                errors.append(f"{key} must be an integer")
        else:
            try:
                if parse_int(scenario.get("frames")) <= 0:
                    errors.append("frames must be positive")
            except (ValueError, TypeError):
                pass
        if scenario.get("after_land") is not None:
            errors.extend(_write_errors(scenario.get("after_land"), "after_land"))
    elif kind == "dialogue_trigger":
        errors.extend(_require_checkpoint(scenario, checkpoints))
        try:
            parse_int(scenario.get("message_id"))
        except (ValueError, TypeError):
            errors.append("message_id must be an integer")
        has_door = "entrance" in scenario or "room" in scenario
        has_spawn = "spawn" in scenario
        if has_door:
            for key in ("entrance", "room"):
                try:
                    parse_int(scenario.get(key))
                except (ValueError, TypeError):
                    errors.append(f"{key} must be an integer")
        elif has_spawn:
            errors.extend(_spawn_errors(scenario.get("spawn"), "spawn"))
        else:
            errors.append("dialogue needs entrance/room or spawn")
    if "retroid_card" in scenario:
        errors.extend(_card_errors(scenario))
    return errors


def _require_checkpoint(scenario: dict, checkpoints: dict[str, dict]) -> list[str]:
    name = scenario.get("checkpoint")
    if not isinstance(name, str) or name not in checkpoints:
        return [f"checkpoint {name!r} is not in checkpoints.json"]
    return []


def _spawn_errors(spawn, label: str) -> list[str]:
    if not isinstance(spawn, dict):
        return [f"{label} object is required"]
    errors = []
    for key in ("via_room", "area"):
        try:
            parse_int(spawn.get(key))
        except (ValueError, TypeError):
            errors.append(f"{label}.{key} must be an integer")
    return errors


def _card_errors(scenario: dict) -> list[str]:
    try:
        card = card_meta(scenario)
    except ValueError as exc:
        return [str(exc)]
    if card is None:
        return ["retroid_card is empty"]
    errors = []
    for field in CARD_FIELDS:
        value = card.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"retroid card {field} is required")
    if isinstance(card.get("id"), str) and not card["id"].replace("_", "").isalnum():
        errors.append("retroid card id must be a safe directory name")
    return errors


def validate_suite(suite: dict, checkpoints: dict[str, dict]) -> dict[str, list[str]]:
    """Map scenario id -> schema errors. An empty list means the scenario can run."""
    found: dict[str, list[str]] = {}
    seen: set[str] = set()
    for index, scenario in enumerate(suite.get("scenarios") or []):
        name = scenario.get("id") if isinstance(scenario, dict) else None
        label = name if isinstance(name, str) and name else f"#{index}"
        errors = validate_scenario(scenario if isinstance(scenario, dict) else {}, checkpoints)
        if label in seen:
            errors.append("duplicate scenario id")
        seen.add(label)
        found[label] = errors
    return found


# ---------------------------------------------------------------- handlers


def _bad(findings: list[dict]) -> bool:
    return any(item["severity"] in ("error", "critical") for item in findings)


def _probe_location(probe: dict) -> str:
    return (f"mod:{probe.get('module', 0):02X}/{probe.get('sub', 0):02X} "
            f"area:{probe.get('area', 0):02X} room:{probe.get('room', 0):03X}")


def _coords_oob(probe: dict) -> bool:
    return not (0 <= int(probe.get("x", -1)) < 0x2000 and 0 <= int(probe.get("y", -1)) < 0x2000)


def _screen_findings(scenario: dict, check: str, probe: dict, location: str) -> list[dict]:
    findings = []
    black = int(probe.get("black", 0))
    if probe.get("forced_blank") or probe.get("bright") not in (0x0F, None):
        findings.append(make_finding(
            scenario, f"{check}_blank", "critical",
            f"frame is blank or INIDISP is ${probe.get('bright', 0):02X}", location))
    elif black:
        findings.append(make_finding(
            scenario, f"{check}_black", "error",
            f"{black} leading black scanlines", location))
    if _coords_oob(probe):
        findings.append(make_finding(
            scenario, f"{check}_oob", "error",
            f"coordinates ({probe.get('x')}, {probe.get('y')}) are outside the map", location))
    return findings


def handle_save_quit(scenario: dict, runtime, checkpoints: dict[str, dict]) -> list[dict]:
    expect = scenario["expect"]
    spawn = scenario["spawn"]
    findings = []
    runtime.boot()
    runtime.apply_writes(resolve_writes(checkpoints, scenario["checkpoint"]))
    runtime.apply_writes(scenario.get("writes") or [])
    landed = runtime.load_overworld(parse_int(spawn["via_room"]), parse_int(spawn["area"]))
    where = f"ow:0x{parse_int(spawn['area']):02X}"
    if landed.get("area") != parse_int(spawn["area"]) or landed.get("module") not in PLAYABLE:
        findings.append(make_finding(
            scenario, "land", "error",
            f"save setup did not land on {where} ({_probe_location(landed)})", where))
        return findings
    runtime.apply_writes(scenario["preserve"])
    runtime.save_and_quit()
    sram = runtime.read_sram()
    info = slot_report(sram)
    if not info["valid"] or not info["checksum_ok"] or not info["mirror_ok"]:
        findings.append(make_finding(
            scenario, "sram_integrity", "error",
            (f"SRAM valid={info['valid']} checksum={info['checksum']:04X} "
             f"mirror={info['mirror_ok']}"),
            "sram:0x3E5"))
    if info["game_state"] != parse_int(expect["game_state"]) or info["saved_world"] != parse_int(expect["saved_world"]):
        findings.append(make_finding(
            scenario, "sram_world", "error",
            (f"saved GameState ${info['game_state']:02X} SavedWorld ${info['saved_world']:02X}, "
             f"wanted ${parse_int(expect['game_state']):02X} / ${parse_int(expect['saved_world']):02X}"),
            "sram:0x3C5"))
    want_gbc = expect["file_select_form"] == "gbc"
    if info["gbc"] != want_gbc:
        findings.append(make_finding(
            scenario, "file_select_form", "error",
            f"File Select eligibility is {'GBC' if info['gbc'] else 'normal Link'}",
            "sram:0x3CA"))
    select = runtime.open_file_select()
    if select.get("module") != 0x01:
        findings.append(make_finding(
            scenario, "file_select_open", "error",
            f"File Select did not open ({_probe_location(select)})", "module:0x01"))
    preview = runtime.cgram_word(GBC_PREVIEW_ADDR)
    if want_gbc and preview != GBC_PREVIEW_WORD:
        findings.append(make_finding(
            scenario, "gbc_palette", "error",
            f"File Select preview word ${preview:04X} is not GameboyLinkPalette ${GBC_PREVIEW_WORD:04X}",
            "cgram:0x7EC604"))
    if not want_gbc and preview == GBC_PREVIEW_WORD:
        findings.append(make_finding(
            scenario, "link_palette", "error",
            f"normal Link File Select is showing the GBC preview ${preview:04X}",
            "cgram:0x7EC604"))
    if _bad(findings):
        return findings
    resumed = runtime.reload_file()
    if resumed.get("module") in (0, None) or resumed.get("module") not in PLAYABLE:
        findings.append(make_finding(
            scenario, "reload", "critical" if resumed.get("module") in (0, None) else "error",
            f"reload is not playable ({_probe_location(resumed)})", "module:$10"))
        return findings
    if want_gbc and (resumed.get("mask") != 0x06 or resumed.get("link_gfx") != 0x3B):
        findings.append(make_finding(
            scenario, "reload_gbc", "error",
            f"Abyss reload mask ${resumed.get('mask', 0):02X} gfx ${resumed.get('link_gfx', 0):02X}",
            "wram:0x02B2"))
    if not want_gbc and (resumed.get("mask") not in (0, None) or resumed.get("link_gfx") not in (0x10, None)):
        findings.append(make_finding(
            scenario, "reload_link", "error",
            f"Light World reload mask ${resumed.get('mask', 0):02X} gfx ${resumed.get('link_gfx', 0):02X}",
            "wram:0x02B2"))
    return findings


def handle_entrance(scenario: dict, runtime, checkpoints: dict[str, dict]) -> list[dict]:
    room = parse_int(scenario["room"])
    parent = parse_int(scenario["parent_map"])
    runtime.boot()
    runtime.apply_writes(resolve_writes(checkpoints, scenario["checkpoint"]))
    entered = runtime.enter_entrance(parse_int(scenario["entrance"]), room)
    findings = []
    location = f"room:0x{room:03X}"
    if entered.get("module") != 0x07 or entered.get("room") != room:
        findings.append(make_finding(
            scenario, "enter", "error",
            f"entrance did not reach room ${room:03X} ({_probe_location(entered)})", location))
        return findings
    findings.extend(_screen_findings(scenario, "enter", entered, location))
    exited = runtime.exit_overworld(room, parent)
    outside = f"ow:0x{parent:02X}"
    if exited.get("module") not in (0x09, 0x0B) or exited.get("area") != parent:
        findings.append(make_finding(
            scenario, "exit", "error",
            f"exit did not return to map ${parent:02X} ({_probe_location(exited)})", outside))
        return findings
    findings.extend(_screen_findings(scenario, "exit", exited, outside))
    moved = runtime.nudge("Down", 24)
    if (moved.get("x"), moved.get("y")) == (exited.get("x"), exited.get("y")):
        moved = runtime.nudge("Right", 24)
    if (moved.get("x"), moved.get("y")) == (exited.get("x"), exited.get("y")):
        findings.append(make_finding(
            scenario, "stuck", "error",
            f"Link did not leave ({exited.get('x')}, {exited.get('y')})", outside))
    return findings


def handle_warp(scenario: dict, runtime, _checkpoints: dict[str, dict]) -> list[dict]:
    source = parse_int(scenario["source_map"])
    dest = parse_int(scenario["dest_map"])
    runtime.boot()
    origin = runtime.load_overworld(parse_int(scenario["via_room"]), source)
    findings = []
    if origin.get("area") != source or origin.get("module") not in PLAYABLE:
        findings.append(make_finding(
            scenario, "source", "error",
            f"did not reach source map ${source:02X} ({_probe_location(origin)})",
            f"ow:0x{source:02X}"))
        return findings
    arrived = runtime.run_transport(scenario["transport"], dest, parse_int(scenario["submodule"]))
    location = f"ow:0x{dest:02X}"
    if arrived.get("area") != dest or arrived.get("module") not in PLAYABLE + (0x0E,):
        findings.append(make_finding(
            scenario, "dest", "error",
            f"{scenario['transport']} did not land on ${dest:02X} ({_probe_location(arrived)})",
            location))
        return findings
    if arrived.get("module") == 0:
        findings.append(make_finding(
            scenario, "softlock", "critical", "transport left module $00", location))
    findings.extend(_screen_findings(scenario, "land", arrived, location))
    return findings


def handle_vblank(scenario: dict, runtime, _checkpoints: dict[str, dict]) -> list[dict]:
    area = parse_int(scenario["area"])
    frames = parse_int(scenario["frames"])
    runtime.boot()
    landed = runtime.load_overworld(parse_int(scenario["via_room"]), area)
    findings = []
    location = f"ow:0x{area:02X}"
    if landed.get("area") != area or landed.get("module") not in PLAYABLE:
        findings.append(make_finding(
            scenario, "land", "error",
            f"{scenario['mechanic']} did not land on {location} ({_probe_location(landed)})",
            location))
        return findings
    runtime.apply_writes(scenario.get("after_land") or [])
    buttons = scenario.get("buttons") or {"epona": "Right", "korl": "Right", "deku": "A",
                                          "zora": "Right", "gust": "Y"}[scenario["mechanic"]]
    sample = runtime.hold(str(buttons), frames)
    overruns = int(sample.get("overruns", 0))
    black = int(sample.get("black", 0))
    advanced = int(sample.get("frames_advanced", 0))
    limit = parse_int(scenario["max_overruns"])
    black_limit = parse_int(scenario["max_black_scanlines"])
    if overruns > limit or black > black_limit:
        findings.append(make_finding(
            scenario, "vblank", "error",
            f"{overruns} VBlank overruns, {black} black scanlines (limits {limit}/{black_limit})",
            location))
    if advanced < frames:
        findings.append(make_finding(
            scenario, "pacing", "error",
            f"frame counter advanced {advanced} of {frames}", location))
    probe = sample.get("probe") or {}
    if probe.get("module") in (0, None):
        findings.append(make_finding(
            scenario, "softlock", "critical",
            f"module collapsed during {scenario['mechanic']}", location))
    return findings


def handle_dialogue(scenario: dict, runtime, checkpoints: dict[str, dict]) -> list[dict]:
    message = parse_int(scenario["message_id"])
    runtime.boot()
    runtime.apply_writes(resolve_writes(checkpoints, scenario["checkpoint"]))
    if "entrance" in scenario:
        runtime.enter_entrance(parse_int(scenario["entrance"]), parse_int(scenario["room"]))
    else:
        spawn = scenario["spawn"]
        runtime.load_overworld(parse_int(spawn["via_room"]), parse_int(spawn["area"]))
    opened = runtime.arm_message(message)
    findings = []
    location = f"msg:0x{message:04X}"
    if opened.get("module") != 0x0E or int(opened.get("message") or 0) != message:
        findings.append(make_finding(
            scenario, "open", "error",
            f"message ${message:04X} did not open ({_probe_location(opened)} msg ${opened.get('message', 0):04X})",
            location))
        return findings
    if opened.get("forced_blank"):
        findings.append(make_finding(
            scenario, "garbage", "error", "message frame is a solid blank", location))
    closed = runtime.close_message()
    if closed.get("module") == 0x0E or int(closed.get("message") or 0) not in (0,):
        findings.append(make_finding(
            scenario, "close", "error",
            f"message box did not close ({_probe_location(closed)} msg ${closed.get('message', 0):04X})",
            location))
    if closed.get("module") in (0, None):
        findings.append(make_finding(
            scenario, "hang", "critical", "input died on the message box", location))
    return findings


HANDLERS = {
    "save_quit_matrix": handle_save_quit,
    "entrance_roundtrip": handle_entrance,
    "warp_landing": handle_warp,
    "vblank_budget": handle_vblank,
    "dialogue_trigger": handle_dialogue,
}


# ---------------------------------------------------------------- Mesen runtime


class MesenRuntime:
    """One NativeSession, one headless Mesen, many scenarios."""

    def __init__(self, rom: Path, work: Path, seed: Path | None, deadline: float):
        self.rom = rom
        self.work = work
        self.seed = seed if seed and seed.is_file() else None
        self.deadline = deadline
        self.session = None
        self.bridge = None
        self._booted = False

    def open(self):
        sys.path.insert(0, str(REPO / "Scripts" / "Agents"))
        if MESEN_CLIENT.is_dir():
            sys.path.insert(0, str(MESEN_CLIENT))
        from native_session import NativeSession
        from mesen2_client_lib.bridge import MesenBridge

        self.work.mkdir(parents=True, exist_ok=True)
        rom_copy = self.work / "suite.sfc"
        if self.rom.resolve() != rom_copy.resolve():
            rom_copy.write_bytes(self.rom.read_bytes())
        home = self.work / "home"
        saves = home / "Saves"
        saves.mkdir(parents=True, exist_ok=True)
        if self.seed is not None:
            (saves / "suite.srm").write_bytes(self.seed.read_bytes())
        self.session = NativeSession(
            "oos-runtime-suite", "beta runtime suite", self.work, deadline=self.deadline,
        ).__enter__()
        try:
            _pid, socket = self.session.launch_mesen(rom_copy, home=home)
            for _ in range(80):
                if socket.exists():
                    break
                time.sleep(0.25)
            if not socket.exists():
                raise RuntimeError(f"Mesen2 socket did not appear: {socket}")
            bridge = MesenBridge(str(socket), auto_reconnect=False, max_retries=0)
            if not bridge.ensure_connected(retries=20, delay=0.4):
                raise RuntimeError("Mesen2 socket did not accept a client")
            self.bridge = bridge
            self._wait_rom()
            self._pause()
            self._arm_input()
            self.step(1)
        except BaseException:
            self.close()
            raise
        return self

    def close(self) -> None:
        session = self.session
        self.session = None
        self.bridge = None
        if session is not None:
            session.close()

    def _wait_rom(self) -> None:
        want = hashlib.sha1(self.rom.read_bytes()).hexdigest().lower()
        for _ in range(100):
            if str(self.bridge.get_rom_info().get("sha1", "")).lower() == want:
                return
            time.sleep(0.1)
        raise RuntimeError("Mesen2 did not report the suite ROM")

    def _paused(self) -> bool:
        reply = self.bridge.send_command("STATE")
        data = reply.get("data", {}) if reply.get("success") else {}
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return False
        return bool(data.get("paused"))

    def _pause(self, timeout: float = 5.0) -> None:
        if self._paused():
            return
        self.bridge.pause()
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self._paused():
                return
            time.sleep(0.01)
        raise RuntimeError("Mesen2 did not pause")

    def _frames(self) -> int:
        value = self.bridge.get_rom_info().get("frameCount", 0)
        return int(value, 0) if isinstance(value, str) else int(value)

    def _arm_input(self) -> None:
        """The debugger socket accepts clients before INPUT is ready."""
        last: dict = {}
        for _ in range(50):
            last = self.bridge.send_command("INPUT", {"buttons": "", "frames": "0", "player": "0"})
            if last.get("success") and self.bridge.get_cpu_state():
                return
            time.sleep(0.1)
        raise RuntimeError(f"INPUT rejected: {last}")

    def step(self, count: int = 1, buttons: str = "") -> None:
        self._pause()
        entered = self.bridge.send_command("INPUT", {"buttons": buttons, "frames": "0", "player": "0"})
        if not entered.get("success"):
            raise RuntimeError(f"INPUT rejected: {entered}")
        before = self._frames()
        stepped = self.bridge.send_command("FRAME", {"count": str(count)})
        if not stepped.get("success"):
            raise RuntimeError(f"FRAME rejected: {stepped}")
        end = time.monotonic() + max(6.0, count / 8.0)
        while time.monotonic() < end:
            if self._frames() >= before + count and self._paused():
                break
            time.sleep(0.005)
        else:
            raise RuntimeError(f"FRAME({count}) stalled at {self._frames()}")
        if buttons:
            self.bridge.send_command("INPUT", {"buttons": "", "frames": "0", "player": "0"})

    def tap(self, button: str, hold: int = 6, settle: int = 12) -> None:
        self.step(2)
        self.step(hold, button)
        self.step(settle)

    def u8(self, addr: int) -> int:
        return self.bridge.read_memory(addr) & 0xFF

    def u16(self, addr: int) -> int:
        return self.bridge.read_memory16(addr) & 0xFFFF

    def w8(self, addr: int, value: int) -> None:
        if not self.bridge.write_memory(addr, value & 0xFF):
            raise RuntimeError(f"write ${addr:06X} rejected")

    def apply_writes(self, writes: list[dict]) -> None:
        self._pause()
        for item in writes:
            addr = parse_int(item["addr"])
            current = self.u8(addr)
            if "value" in item:
                current = parse_int(item["value"])
            if "set_bits" in item:
                current |= parse_int(item["set_bits"])
            if "clear_bits" in item:
                current &= ~parse_int(item["clear_bits"])
            self.w8(addr, current)

    def probe(self, shot: bool = False) -> dict:
        state = {
            "module": self.u8(MODULE),
            "sub": self.u8(SUB),
            "bright": self.u8(BRIGHT),
            "indoors": self.u8(INDOORS),
            "area": self.u8(AREA),
            "room": self.u16(ROOM),
            "x": self.u16(LINK_X),
            "y": self.u16(LINK_Y),
            "mask": self.u8(MASK),
            "link_gfx": self.u8(LINK_GFX),
            "message": self.u16(MESSAGE),
            "black": 0,
            "forced_blank": False,
        }
        if shot:
            png = self.bridge.screenshot()
            if not png:
                state["forced_blank"] = True
            else:
                black, solid = leading_black_scanlines(png)
                state["black"] = black
                state["forced_blank"] = solid or state["bright"] == 0x80
        return state

    def _until(self, pred, max_frames: int, step: int = 8) -> int:
        spent = 0
        while spent < max_frames:
            if pred():
                return spent
            count = min(step, max_frames - spent)
            self.step(count)
            spent += count
        return spent

    def boot(self) -> dict:
        if self._booted:
            if not self.bridge.reset():
                raise RuntimeError("Mesen2 reset was rejected")
            self._pause()
            # A reset keeps the previous module readable until the title owns
            # the machine. Step past that window, then require the press-start
            # screen ($00/$08) before any later gameplay check can match.
            self.step(120)
            self._until(lambda: (self.u8(MODULE), self.u8(SUB)) == (0x00, 0x08), 3600, 16)
            if (self.u8(MODULE), self.u8(SUB)) != (0x00, 0x08):
                raise RuntimeError(f"reset stalled at {_probe_location(self.probe())}")
        self._until(
            lambda: (self.u8(MODULE), self.u8(SUB)) == (0x00, 0x08) or self.u8(MODULE) in (0x01, 0x07, 0x09),
            2700, 16)
        if self.u8(MODULE) == 0x00:
            self.tap("Start", 4, 12)
        self._until(
            lambda: (self.u8(MODULE) == 0x01 and self.u8(SUB) == 0x05) or self.u8(MODULE) in (0x07, 0x09),
            400, 8)
        if self.u8(MODULE) == 0x01:
            self.tap("Start", 4, 16)
        self._until(lambda: self.u8(MODULE) in (0x07, 0x09) and self.u8(SUB) == 0, 1800, 16)
        self._booted = True
        state = self.probe()
        if state["module"] not in (0x07, 0x09):
            raise RuntimeError(f"boot stalled at {_probe_location(state)}")
        return state

    def load_overworld(self, via_room: int, area: int) -> dict:
        self._pause()
        self.w8(ROOM, via_room & 0xFF)
        self.w8(ROOM + 1, (via_room >> 8) & 0xFF)
        for addr in (0x7E010A, 0x7E04AA, 0x7E009B, SUB, 0x7E00B0):
            self.w8(addr, 0)
        self.w8(BRIGHT, 0x80)
        self.w8(MODULE, 0x08)
        self._until(lambda: self.u8(MODULE) in (0x09, 0x0B) and self.u8(SUB) == 0 and self.u8(BRIGHT) == 0x0F, 900, 8)
        self.step(4)
        return self.probe(shot=True)

    def enter_entrance(self, entrance: int, room: int) -> dict:
        self._pause()
        self.w8(0x7E010E, entrance & 0xFF)
        self.w8(0x7E010F, 0)
        self.w8(0x7E010A, 1)
        self.w8(0x7E04AA, 0)
        self.w8(INDOORS, 1)
        self.w8(SUB, 0)
        self.w8(0x7E00B0, 0)
        self.w8(MODULE, 0x05)
        self._until(lambda: self.u8(MODULE) == 0x07 and self.u8(SUB) == 0 and self.u16(ROOM) == room, 900, 8)
        self.step(8)
        return self.probe(shot=True)

    def exit_overworld(self, room: int, parent_map: int) -> dict:
        self._pause()
        self.w8(ROOM, room & 0xFF)
        self.w8(ROOM + 1, (room >> 8) & 0xFF)
        for addr in (0x7E010A, 0x7E04AA, 0x7E009B, SUB, 0x7E00B0):
            self.w8(addr, 0)
        self.w8(BRIGHT, 0x80)
        self.w8(MODULE, 0x08)
        self._until(
            lambda: self.u8(MODULE) in (0x09, 0x0B) and self.u8(SUB) == 0 and self.u8(AREA) == parent_map,
            900, 8)
        self.step(4)
        return self.probe(shot=True)

    def run_transport(self, transport: str, dest_map: int, submodule: int) -> dict:
        self._pause()
        if transport == "whirlpool":
            self.w8(SUB, submodule & 0xFF)
            self.w8(0x7E00B0, 0)
        elif transport == "bird":
            self.w8(0x7E0200, 0x05)
            self.w8(SUB, submodule & 0xFF)
        else:
            self.w8(SUB, submodule & 0xFF)
        self._until(lambda: self.u8(AREA) == dest_map and self.u8(MODULE) in PLAYABLE and self.u8(SUB) == 0, 1200, 8)
        self.step(8)
        return self.probe(shot=True)

    def save_and_quit(self) -> dict:
        self.tap("Select", 30, 20)
        for _ in range(6):
            if self.u8(CHOICE) == 1 or self.u8(MODULE) in (0x00, 0x17):
                break
            self.tap("Down", 8, 8)
        if self.u8(MODULE) not in (0x00, 0x17):
            self.tap("A", 8, 30)
        if self.u8(MODULE) not in (0x00, 0x01):
            self._pause()
            self.w8(SUB, 0)
            self.w8(MODULE, 0x17)
        # Title submodule $04 is still the logo. The press-start screen is $00/$08.
        self._until(
            lambda: (self.u8(MODULE), self.u8(SUB)) == (0x00, 0x08)
            or (self.u8(MODULE) == 0x01 and self.u8(SUB) >= 0x05),
            2400, 8)
        self.step(8)
        return self.probe()

    def read_sram(self) -> bytes:
        blob = self.bridge.read_block(0, 8192, "SnesSaveRam")
        return bytes(blob or b"")

    def cgram_word(self, addr: int) -> int:
        return self.u16(addr)

    def open_file_select(self) -> dict:
        self._until(
            lambda: (self.u8(MODULE), self.u8(SUB)) == (0x00, 0x08)
            or (self.u8(MODULE) == 0x01 and self.u8(SUB) >= 0x05),
            2400, 8)
        if self.u8(MODULE) == 0x00:
            self.tap("Start", 4, 16)
        self._until(lambda: self.u8(MODULE) == 0x01 and self.u8(SUB) >= 0x05, 800, 8)
        self.step(4)
        return self.probe(shot=True)

    def reload_file(self) -> dict:
        if self.u8(MODULE) == 0x01:
            self.tap("Start", 4, 16)
        self._until(lambda: self.u8(MODULE) in PLAYABLE and self.u8(SUB) == 0 and self.u8(BRIGHT) == 0x0F, 1800, 8)
        # A story box on the landing pad is still a live game; dismiss it.
        for _ in range(8):
            if self.u8(MODULE) != 0x0E:
                break
            self.tap("A", 6, 10)
        self.step(4)
        return self.probe(shot=True)

    def arm_message(self, message_id: int) -> dict:
        self._until(lambda: self.u8(MODULE) == 0x0E and self.u16(MESSAGE) == message_id, 240, 8)
        if self.u8(MODULE) != 0x0E or self.u16(MESSAGE) != message_id:
            self._pause()
            self.w8(MESSAGE, message_id & 0xFF)
            self.w8(MESSAGE + 1, (message_id >> 8) & 0xFF)
            self.w8(SUB, 0x02)
            self.w8(MODULE, 0x0E)
            self.step(16)
        return self.probe(shot=True)

    def close_message(self) -> dict:
        for _ in range(16):
            if self.u8(MODULE) != 0x0E and self.u16(MESSAGE) == 0:
                break
            self.tap("A", 6, 8)
        self.step(4)
        return self.probe(shot=True)

    def hold(self, buttons: str, frames: int) -> dict:
        before = self._frames()
        overruns = 0
        black = 0
        left = frames
        while left:
            count = min(30, left)
            self.step(count, buttons)
            left -= count
            png = self.bridge.screenshot()
            if not png:
                overruns += 1
                continue
            rows, solid = leading_black_scanlines(png)
            black = max(black, rows)
            if rows or solid:
                overruns += 1
        return {
            "frames_advanced": self._frames() - before,
            "overruns": overruns,
            "black": black,
            "probe": self.probe(),
        }

    def nudge(self, buttons: str, frames: int) -> dict:
        self.step(frames, buttons)
        return self.probe()

    def screenshot(self) -> bytes:
        png = self.bridge.screenshot()
        if not png:
            raise RuntimeError("Mesen2 returned an empty screenshot")
        return frame_png(png)

    def save_state(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not self.bridge.save_state(path=str(path)):
            raise RuntimeError(f"savestate rejected: {path}")
        if not path.is_file() or path.stat().st_size < 32:
            raise RuntimeError(f"savestate was not written: {path}")


# ---------------------------------------------------------------- export / run


def export_cards(scenarios: list[dict], dest: Path, runtime, dry_run: bool) -> list[dict]:
    findings = []
    dest.mkdir(parents=True, exist_ok=True)
    for scenario in scenarios:
        if "retroid_card" not in scenario:
            continue
        try:
            card = card_meta(scenario)
        except ValueError as exc:
            findings.append(make_finding(scenario, "retroid_card", "error", str(exc), "card"))
            continue
        errors = _card_errors(scenario)
        if errors:
            findings.append(make_finding(scenario, "retroid_card", "error", "; ".join(errors), "card"))
            continue
        folder = dest / card["id"]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "card.json").write_text(json.dumps({
            "id": card["id"],
            "title": card["title"],
            "badge": card["badge"],
            "summary": card["summary"],
            "scenario": scenario["id"],
            "kind": scenario["kind"],
        }, indent=2) + "\n", encoding="utf-8")
        if dry_run or runtime is None:
            continue
        try:
            (folder / "thumb.png").write_bytes(frame_png(runtime.screenshot()))
            runtime.save_state(folder / "state.mss")
        except Exception as exc:  # noqa: BLE001 - one card must not skip the rest
            findings.append(make_finding(
                scenario, "retroid_capture", "error", f"{type(exc).__name__}: {exc}", f"card:{card['id']}"))
    return findings


def _scenario_failed(findings: list[dict]) -> bool:
    return any(item["severity"] in ("error", "critical") for item in findings)


def run_suite(suite: dict, *, checkpoints: dict[str, dict], scenarios: list[dict],
              rom: Path | None, rom_sha: str | None, dry_run: bool, baseline: dict | None,
              runtime=None, export_dir: Path | None = None) -> dict:
    grouped: dict[str, list[dict]] = {}
    order = []
    for scenario in scenarios:
        name = str(scenario.get("id"))
        errors = validate_scenario(scenario, checkpoints)
        order.append(name)
        if errors:
            grouped[name] = [make_finding(scenario, "schema", "error", "; ".join(errors), "suite")]
            continue
        grouped[name] = []

    owned = None
    work_dir = None
    try:
        if any(not grouped[name] for name in order) and not dry_run:
            if runtime is None:
                if rom is None:
                    raise ValueError("a live suite needs --rom")
                work_dir = Path(tempfile.mkdtemp(prefix="oos-runtime-suite-"))
                seed = DEFAULT_SEED if DEFAULT_SEED.is_file() else None
                runtime = MesenRuntime(rom, work_dir, seed, deadline=480)
                owned = runtime
                runtime.open()
        for scenario in scenarios:
            name = str(scenario.get("id"))
            if grouped[name] or dry_run:
                continue
            try:
                grouped[name] = HANDLERS[scenario["kind"]](scenario, runtime, checkpoints)
            except Exception as exc:  # noqa: BLE001 - recorded per scenario; session still closes
                grouped[name] = [make_finding(
                    scenario, "exception", "critical", f"{type(exc).__name__}: {exc}", "runtime")]
        if export_dir is not None:
            export_findings = export_cards(scenarios, export_dir, runtime, dry_run)
            if export_findings:
                host = scenarios[0] if scenarios else {"id": "export", "kind": "schema",
                                                       "jump_target": {"kind": "overworld", "id": 0, "x": 0, "y": 0}}
                # Attach capture failures to the named scenario when possible.
                by_id = {str(item.get("id")): item for item in scenarios}
                for item in export_findings:
                    owner = item["id"].split(".", 1)[0]
                    if owner in grouped:
                        grouped[owner].append(item)
                    else:
                        grouped.setdefault(host.get("id", "export"), []).append(item)
    finally:
        if owned is not None:
            owned.close()
        if work_dir is not None:
            shutil.rmtree(work_dir, ignore_errors=True)

    flat = [item for name in order for item in grouped.get(name, [])]
    failed = sum(1 for name in order if _scenario_failed(grouped.get(name, [])))
    passed = len(order) - failed
    report = build_report(
        str(suite.get("name") or "suite"), rom_sha, len(order), passed, failed,
        classify(flat, baseline))
    return report


def _select(suite: dict, wanted: list[str] | None) -> tuple[list[dict], list[dict]]:
    scenarios = [item for item in suite.get("scenarios") or [] if isinstance(item, dict)]
    if not wanted:
        return scenarios, []
    by_id = {item.get("id"): item for item in scenarios}
    chosen = []
    missing = []
    for name in wanted:
        if name in by_id:
            chosen.append(by_id[name])
        else:
            missing.append({
                "id": name,
                "kind": "schema",
                "jump_target": {"kind": "overworld", "id": 0, "x": 0, "y": 0},
            })
    return chosen, missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Oracle of Secrets Mesen2 runtime suite")
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--rom", type=Path)
    parser.add_argument("--scenario", default="")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--write-baseline", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--format", choices=("json", "text"), default="text")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--export-retroid-cards", type=Path)
    parser.add_argument("--seed", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        suite = load_json(args.suite)
        checkpoint_path = REPO / str(suite.get("checkpoints") or "Data/debug/checkpoints.json")
        checkpoints = checkpoint_table(checkpoint_path)
        wanted = [item.strip() for item in args.scenario.split(",") if item.strip()] or None
        chosen, missing = _select(suite, wanted)
        rom_sha = sha256_file(args.rom) if args.rom and args.rom.is_file() else None
        baseline = load_json(args.baseline) if args.baseline else None
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"{TOOL}: {exc}", file=sys.stderr)
        return 2
    if args.rom and not args.rom.is_file():
        print(f"{TOOL}: ROM not found: {args.rom}", file=sys.stderr)
        return 2
    if not args.dry_run and args.rom is None:
        print(f"{TOOL}: a live run needs --rom (or pass --dry-run)", file=sys.stderr)
        return 2

    # A caller-supplied seed replaces the default fixture for this process only.
    global DEFAULT_SEED
    if args.seed is not None:
        DEFAULT_SEED = args.seed

    try:
        report = run_suite(
            suite, checkpoints=checkpoints, scenarios=chosen + missing,
            rom=args.rom, rom_sha=rom_sha, dry_run=args.dry_run, baseline=baseline,
            export_dir=args.export_retroid_cards)
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        name = type(exc).__name__
        if name == "SessionInterrupted":
            print(f"{TOOL}: {exc}", file=sys.stderr)
            return int(getattr(exc, "exit_code", 124))
        print(f"{TOOL}: {name}: {exc}", file=sys.stderr)
        return 1

    text = json.dumps(report, indent=2) + "\n" if args.format == "json" else format_text(report)
    sys.stdout.write(text)
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.write_baseline:
        args.write_baseline.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return exit_code(report, baseline_set=baseline is not None, strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
