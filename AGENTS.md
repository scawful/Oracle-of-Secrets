# AGENTS.md

## ROM Naming
- `Roms/oos<VERSION>.sfc` — unpatched base, the **edit target**
- `Roms/oos<VERSION>x.sfc` — Asar-patched, **test in emulator only** (never edit directly)
- Current: `oos168.sfc` / `oos168x.sfc`

## Essentials
- Build: `./Scripts/Build/build_rom.sh 168`
- After ASM changes: `python3 Scripts/Build/check_zscream_overlap.py`
- Current work: `.context/scratchpad/agent_handoff.md`
- File routing: `.context/CONTEXT_INDEX.md`

## Rules
1. Read `agent_handoff.md` first.
2. Smallest working change. Touch only task-related files.
3. Never claim verification not actually run.
4. Story/lore/dialogue work: `Docs/Planning/story_canon_beat_sheet.md` is the
   single source of truth (scawful's rulings). It overrides all other planning
   docs. Do not introduce Ganondorf-origin or two-villain plotlines.
