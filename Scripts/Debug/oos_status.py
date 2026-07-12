#!/usr/bin/env python3
"""Emit a small JSON status snapshot for the Oracle of Secrets cockpit."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AGENTS_PATH = ROOT / "AGENTS.md"
HANDOFF_PATH = ROOT / ".context" / "scratchpad" / "agent_handoff.md"
TRACKER_PATH = ROOT / "oracle.org"
WORKFLOW_PATH = ROOT / "Docs" / "Planning" / "Plans" / "development_workflow_alignment_2026-03-28.md"
RUNBOOK_PATH = ROOT / "Docs" / "RUNBOOK.md"


def run_command(args: list[str], *, cwd: Path | None = None, timeout: float = 2.0) -> tuple[bool, str, str]:
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd or ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, "", str(exc)
    return completed.returncode == 0, completed.stdout, completed.stderr


def iso_mtime(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def age_minutes(path: Path) -> int | None:
    if not path.exists():
        return None
    delta = datetime.now(tz=timezone.utc).timestamp() - path.stat().st_mtime
    return int(delta // 60)


def sanitize_text(text: str) -> str:
    text = re.sub(r"\[\[[^\]]+\]\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"[=`~*]+", "", text)
    text = re.sub(r"\s+:[^:\s]+(?::[^:\s]+)*:\s*$", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def detect_version() -> int:
    if AGENTS_PATH.exists():
        agents_text = AGENTS_PATH.read_text(encoding="utf-8")
        match = re.search(r"Current:\s+`oos(\d+)\.sfc`\s*/\s*`oos\d+x\.sfc`", agents_text)
        if match:
            return int(match.group(1))
    rom_dir = ROOT / "Roms"
    versions: list[int] = []
    for path in rom_dir.glob("oos*.sfc"):
        match = re.fullmatch(r"oos(\d+)(x)?\.sfc", path.name)
        if match:
            versions.append(int(match.group(1)))
    return max(versions) if versions else 168


def parse_markdown_table(section: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or set("".join(cells)) <= {"-", ":"}:
            continue
        rows.append(cells)
    if len(rows) >= 2 and rows[0] and rows[0][0].lower() in {"system", "task"}:
        return rows[1:]
    return rows


def extract_markdown_section(text: str, heading: str) -> str:
    pattern = rf"^{re.escape(heading)}\n(.*?)(?=^#{{1,6}}\s|\Z)"
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ""


def parse_handoff() -> dict[str, Any]:
    text = HANDOFF_PATH.read_text(encoding="utf-8") if HANDOFF_PATH.exists() else ""
    latest = re.search(r"LATEST UPDATE (\d{4}-\d{2}-\d{2})", text)

    next_tasks_section = extract_markdown_section(text, "## Next Tasks (Priority Order)")
    next_tasks = [
        sanitize_text(match.group(1))
        for match in re.finditer(r"^\d+\.\s+(.*)$", next_tasks_section, flags=re.MULTILINE)
    ]

    blocked_section = extract_markdown_section(text, "## What's BLOCKED")
    blocked = []
    for row in parse_markdown_table(blocked_section):
        if len(row) >= 2:
            blocked.append({"task": sanitize_text(row[0]), "blocker": sanitize_text(row[1])})

    runtime_section = extract_markdown_section(text, "## What Needs Runtime Testing")
    runtime_testing = []
    for row in parse_markdown_table(runtime_section):
        if len(row) >= 3:
            runtime_testing.append(
                {
                    "system": sanitize_text(row[0]),
                    "method": sanitize_text(row[1]),
                    "blocker": sanitize_text(row[2]),
                }
            )

    return {
        "path": str(HANDOFF_PATH),
        "latest_update": latest.group(1) if latest else None,
        "next_tasks": next_tasks[:8],
        "blocked": blocked[:6],
        "runtime_testing": runtime_testing[:6],
    }


def parse_workflow_plan() -> dict[str, Any]:
    text = WORKFLOW_PATH.read_text(encoding="utf-8") if WORKFLOW_PATH.exists() else ""
    sessions: list[dict[str, Any]] = []
    matches = list(re.finditer(r"^### (Session [A-Z] - .+)$", text, flags=re.MULTILINE))
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end]
        goal_match = re.search(r"\*\*Goal:\*\*\s*(.+)", body)
        bullets = [
            sanitize_text(bullet.group(1))
            for bullet in re.finditer(r"^- (.+)$", body, flags=re.MULTILINE)
        ]
        sessions.append(
            {
                "title": sanitize_text(match.group(1)),
                "goal": sanitize_text(goal_match.group(1)) if goal_match else "",
                "bullets": bullets[:4],
            }
        )
    return {
        "path": str(WORKFLOW_PATH),
        "sessions": sessions,
        "recommended_session": sessions[0]["title"] if sessions else None,
    }


def parse_tracker() -> dict[str, Any]:
    active: list[dict[str, str]] = []
    todo: list[dict[str, str]] = []
    if not TRACKER_PATH.exists():
        return {"path": str(TRACKER_PATH), "active": active, "todo": todo}

    for raw_line in TRACKER_PATH.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\*+\s+(TODO|ACTIVE)\s+(?:\[#([A-C])\]\s+)?(.+)$", raw_line)
        if not match:
            continue
        status, priority, title = match.groups()
        item = {
            "status": status,
            "priority": priority or "",
            "title": sanitize_text(title),
        }
        if status == "ACTIVE" and len(active) < 6:
            active.append(item)
        elif status == "TODO" and len(todo) < 6:
            todo.append(item)
        if len(active) >= 6 and len(todo) >= 6:
            break

    return {"path": str(TRACKER_PATH), "active": active, "todo": todo}


def parse_git() -> dict[str, Any]:
    ok, stdout, stderr = run_command(["git", "status", "--porcelain=v1", "--branch"], timeout=2.5)
    if not ok:
        return {"available": False, "error": stderr.strip() or "git status failed"}

    lines = stdout.splitlines()
    branch = ""
    ahead = 0
    behind = 0
    if lines and lines[0].startswith("## "):
        header = lines[0][3:]
        branch = header.split("...")[0].strip()
        sync_match = re.search(r"\[([^\]]+)\]", header)
        if sync_match:
            sync_info = sync_match.group(1)
            ahead_match = re.search(r"ahead (\d+)", sync_info)
            behind_match = re.search(r"behind (\d+)", sync_info)
            ahead = int(ahead_match.group(1)) if ahead_match else 0
            behind = int(behind_match.group(1)) if behind_match else 0

    modified = 0
    added = 0
    deleted = 0
    renamed = 0
    untracked = 0
    for line in lines[1:]:
        if line.startswith("??"):
            untracked += 1
            continue
        if len(line) < 2:
            continue
        codes = line[:2]
        if "M" in codes:
            modified += 1
        if "A" in codes:
            added += 1
        if "D" in codes:
            deleted += 1
        if "R" in codes:
            renamed += 1

    return {
        "available": True,
        "branch": branch,
        "ahead": ahead,
        "behind": behind,
        "dirty": modified + added + deleted + renamed + untracked > 0,
        "modified": modified,
        "added": added,
        "deleted": deleted,
        "renamed": renamed,
        "untracked": untracked,
    }


def tool_status(version: int) -> dict[str, Any]:
    home = Path.home()
    z3ed = shutil.which("z3ed")
    if not z3ed:
        candidate = home / "src" / "hobby" / "yaze" / "build" / "bin" / "z3ed"
        if candidate.exists():
            z3ed = str(candidate)
    mesen_app = Path("/Applications/Mesen2 OOS.app")
    return {
        "mesen2_oos_app": {"available": mesen_app.exists(), "path": str(mesen_app)},
        "yaze_nightly": {"available": shutil.which("yaze-nightly") is not None, "path": shutil.which("yaze-nightly")},
        "z3ed": {"available": z3ed is not None, "path": z3ed},
        "flips": {"available": shutil.which("flips") is not None, "path": shutil.which("flips")},
        "mesen_agent": {"available": shutil.which("mesen-agent") is not None, "path": shutil.which("mesen-agent")},
        "build_wrapper": {"available": (ROOT / "build.sh").exists(), "path": str(ROOT / "build.sh")},
        "quick_wrapper": {"available": (ROOT / "Scripts" / "Build" / "oos-quick.sh").exists(), "path": str(ROOT / "Scripts" / "Build" / "oos-quick.sh")},
        "verify_wrapper": {"available": (ROOT / "Scripts" / "Build" / "oos-verify.sh").exists(), "path": str(ROOT / "Scripts" / "Build" / "oos-verify.sh")},
        "session_wrapper": {"available": (ROOT / "Scripts" / "Build" / "oos-session.sh").exists(), "path": str(ROOT / "Scripts" / "Build" / "oos-session.sh")},
        "version": version,
    }


def registry_summary(owner: str) -> dict[str, Any]:
    ok, stdout, stderr = run_command(
        ["python3", str(ROOT / "Scripts" / "Mesen2" / "mesen2_registry.py"), "list", "--json"],
        timeout=2.5,
    )
    if not ok:
        return {
            "available": False,
            "error": stderr.strip() or "registry lookup failed",
            "recommended_instance": f"oos-{owner}-debug",
        }

    try:
        entries = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return {
            "available": False,
            "error": f"invalid registry json: {exc}",
            "recommended_instance": f"oos-{owner}-debug",
        }

    active = [entry for entry in entries if entry.get("active")]
    alive = [entry for entry in entries if entry.get("alive")]
    active_alive = [entry for entry in active if entry.get("alive")]
    stale_active = [entry for entry in active if not entry.get("alive")]
    recent_instances = [entry.get("instance") for entry in active[:6] if entry.get("instance")]

    warning = None
    if len(stale_active) >= 5:
        warning = "Registry has many stale active instances; prefer --instance targeting and prune old entries."
    elif len(entries) >= 15:
        warning = "Registry is crowded; prefer named instances over auto-attach."

    return {
        "available": True,
        "total": len(entries),
        "active": len(active),
        "alive": len(alive),
        "active_alive": len(active_alive),
        "stale_active": len(stale_active),
        "recent_active_instances": recent_instances,
        "recommended_instance": f"oos-{owner}-debug",
        "warning": warning,
    }


def rom_status(version: int) -> dict[str, Any]:
    base = ROOT / "Roms" / f"oos{version}.sfc"
    patched = ROOT / "Roms" / f"oos{version}x.sfc"
    return {
        "version": version,
        "base_path": str(base),
        "patched_path": str(patched),
        "base_exists": base.exists(),
        "patched_exists": patched.exists(),
        "base_mtime": iso_mtime(base),
        "patched_mtime": iso_mtime(patched),
        "base_age_minutes": age_minutes(base),
        "patched_age_minutes": age_minutes(patched),
        "edit_target_rule": "Edit the base ROM only; test the patched ROM only.",
    }


def recommended_actions(version: int, rom: dict[str, Any], handoff: dict[str, Any], workflow: dict[str, Any]) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    if not rom["patched_exists"]:
        actions.append(
            {
                "title": "Build the patched ROM",
                "detail": f"Generate oos{version}x.sfc before trying to test or launch seeds.",
                "action": "quick-build",
                "command": f"./Scripts/Build/oos-quick.sh {version}",
            }
        )
    actions.append(
        {
            "title": workflow.get("recommended_session") or "Session A - Testing surface hardening",
            "detail": "Make the fast-test surface cheap: verify seeds, save-data profiles, and must-run checks.",
            "action": "open-workflow",
            "command": "",
        }
    )
    actions.append(
        {
            "title": "Validate Maku progression helpers",
            "detail": "Use named Maku sessions for 0/1/3/5/7 crystals and verify message + map icon.",
            "action": "session-maku",
            "command": "./Scripts/Build/oos-session.sh maku --crystals 3",
        }
    )
    if handoff.get("next_tasks"):
        actions.append(
            {
                "title": "Keep the real blocker visible",
                "detail": handoff["next_tasks"][0],
                "action": "open-handoff",
                "command": "",
            }
        )
    return actions[:4]


def build_finish_line(
    version: int,
    rom: dict[str, Any],
    git: dict[str, Any],
    tools: dict[str, Any],
    registry: dict[str, Any],
    handoff: dict[str, Any],
) -> dict[str, Any]:
    focus: dict[str, str]
    alerts_level = "ok"
    compact_label = "Build"

    if not rom["patched_exists"]:
        focus = {
            "label": "Build",
            "title": "Build the patched ROM",
            "detail": f"Create oos{version}x.sfc before trying to play targeted sessions.",
            "action": "quick-build",
            "command": f"./Scripts/Build/oos-quick.sh {version}",
            "session": "free",
        }
        alerts_level = "error"
    else:
        focus = {
            "label": "Maku 0",
            "title": "Play Maku Tree at 0 crystals",
            "detail": "Smallest high-value unknown: progression helpers and Maku hint dispatch are assembled but still untested.",
            "action": "continue-play",
            "command": "./Scripts/Build/oos-session.sh maku --crystals 0",
            "session": "maku",
        }
        compact_label = "M0"
        if registry.get("warning") or not tools["mesen2_oos_app"]["available"]:
            alerts_level = "warn"

    today = [
        {
            "title": "Patch + Reload",
            "detail": "Rebuild the patched ROM and sync the emulator-facing target first.",
            "action": "verify-build",
            "command": f"./Scripts/Build/oos-verify.sh {version}",
        },
        {
            "title": "Transition Regressions",
            "detail": "Run the daily-driver transition subset before manual dungeon work.",
            "action": "transition-tests",
            "command": "./Scripts/Validate/run_regression_tests.sh regression --tag transition -q --fail-fast",
        },
        {
            "title": "Maku 0",
            "detail": "Talk to the tree and verify the message shown and MapIcon state.",
            "action": "session-maku-0",
            "command": "./Scripts/Build/oos-session.sh maku --crystals 0",
        },
        {
            "title": "Maku 1",
            "detail": "Repeat with the 1-crystal state only if the 0-crystal run is stable.",
            "action": "session-maku-1",
            "command": "./Scripts/Build/oos-session.sh maku --crystals 1",
        },
    ]

    next_items = [
        {
            "title": "Maku 3 / 5 / 7",
            "detail": "Finish the threshold sweep once the 0 and 1 crystal cases are proven.",
            "action": "session-maku-3",
            "command": "./Scripts/Build/oos-session.sh maku --crystals 3",
        },
        {
            "title": "Key NPC Spot-Check",
            "detail": "Validate one imported dialogue route after Maku proves the helper stack.",
            "action": "open-workflow",
            "command": "",
        },
        {
            "title": "D6 Entrance Repro",
            "detail": "Move to the dedicated overworld entrance seed only after progression confidence improves.",
            "action": "session-d6",
            "command": "./Scripts/Build/oos-session.sh d6",
        },
        {
            "title": "D4 Waterfall Roundtrip",
            "detail": "Keep Zora Temple transition and water-gate validation behind Maku and D6 confidence work.",
            "action": "session-d4",
            "command": "./Scripts/Build/oos-session.sh d4",
        },
    ]

    blocked: list[dict[str, str]] = []
    next_tasks = handoff.get("next_tasks") or []
    if next_tasks:
        blocked.append(
            {
                "title": "APU deadlock",
                "detail": next_tasks[0],
                "action": "open-handoff",
                "command": "",
            }
        )
    if len(next_tasks) >= 6:
        blocked.append(
            {
                "title": "D6 entrance failure",
                "detail": next_tasks[5],
                "action": "session-d6",
                "command": "./Scripts/Build/oos-session.sh d6",
            }
        )
    for item in handoff.get("blocked") or []:
        if len(blocked) >= 4:
            break
        blocked.append(
            {
                "title": item.get("task", "Blocked task"),
                "detail": item.get("blocker", ""),
                "action": "open-handoff",
                "command": "",
            }
        )

    status_line = compact_label
    if git.get("dirty"):
        status_line += "*"
        if alerts_level == "ok":
            alerts_level = "warn"

    return {
        "summary": "Confidence first: Maku progression, then D6 entrance, then D4 and broader dungeon work.",
        "focus": focus,
        "today": today,
        "next": next_items,
        "blocked": blocked[:4],
        "status_line": status_line,
        "alerts_level": alerts_level,
        "notification": {
            "title": "Zelda Hacking",
            "subtitle": focus["title"],
            "message": focus["detail"],
        },
    }


def build_snapshot() -> dict[str, Any]:
    version = detect_version()
    owner = os.getenv("USER", "scawful")
    rom = rom_status(version)
    handoff = parse_handoff()
    workflow = parse_workflow_plan()
    tracker = parse_tracker()
    registry = registry_summary(owner)
    git = parse_git()
    tools = tool_status(version)
    finish_line = build_finish_line(version, rom, git, tools, registry, handoff)

    alerts: list[str] = []
    if not rom["patched_exists"]:
        alerts.append("Patched ROM is missing; run the quick build before emulator testing.")
    if not tools["flips"]["available"]:
        alerts.append("flips is not on PATH, so BPS packaging is not ready on a clean path.")
    if not tools["mesen_agent"]["available"]:
        alerts.append("mesen-agent is still unavailable on PATH; prefer mesen2_client and named instances.")
    if registry.get("warning"):
        alerts.append(registry["warning"])

    return {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "repo_root": str(ROOT),
        "rom": rom,
        "git": git,
        "tools": tools,
        "registry": registry,
        "handoff": handoff,
        "workflow": workflow,
        "tracker": tracker,
        "paths": {
            "handoff": str(HANDOFF_PATH),
            "tracker": str(TRACKER_PATH),
            "workflow": str(WORKFLOW_PATH),
            "runbook": str(RUNBOOK_PATH),
        },
        "commands": {
            "quick": f"./Scripts/Build/oos-quick.sh {version}",
            "verify": f"./Scripts/Build/oos-verify.sh {version}",
            "sessions": {
                "maku": "./Scripts/Build/oos-session.sh maku",
                "maku0": "./Scripts/Build/oos-session.sh maku --crystals 0",
                "maku1": "./Scripts/Build/oos-session.sh maku --crystals 1",
                "maku3": "./Scripts/Build/oos-session.sh maku --crystals 3",
                "maku5": "./Scripts/Build/oos-session.sh maku --crystals 5",
                "maku7": "./Scripts/Build/oos-session.sh maku --crystals 7",
                "d4": "./Scripts/Build/oos-session.sh d4",
                "d6": "./Scripts/Build/oos-session.sh d6",
                "d6cart": "./Scripts/Build/oos-session.sh d6cart",
                "menu": "./Scripts/Build/oos-session.sh menu",
            },
            "transition_tests": "./Scripts/Validate/run_regression_tests.sh regression --tag transition -q --fail-fast",
        },
        "recommended_actions": recommended_actions(version, rom, handoff, workflow),
        "finish_line": finish_line,
        "alerts": alerts,
    }


def strip_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: strip_none(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [strip_none(item) for item in value]
    return value


def build_barista_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return strip_none(
        {
            "generated_at": snapshot.get("generated_at"),
            "finish_line": snapshot.get("finish_line", {}),
            "commands": snapshot.get("commands", {}),
            "paths": snapshot.get("paths", {}),
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit Oracle of Secrets cockpit status as JSON.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the JSON output.")
    parser.add_argument(
        "--barista",
        action="store_true",
        help="Emit a reduced null-free payload for Barista/SketchyBar integration.",
    )
    args = parser.parse_args()

    snapshot = build_snapshot()
    if args.barista:
        snapshot = build_barista_snapshot(snapshot)
    json.dump(snapshot, sys.stdout, indent=2 if args.pretty else None, sort_keys=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
