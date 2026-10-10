# AGENTS.md

## ROM Naming
- `Roms/oos<VERSION>.sfc` — unpatched base, the **edit target**
- `Roms/oos<VERSION>x.sfc` — Asar-patched, **test in emulator only** (never edit directly)
- Current: `oos168.sfc` / `oos168x.sfc`

## Feature Defaults (2026-09-29)
- Active RC features and their fixes are enabled in normal builds. Feature flags
  are diagnostic opt-outs, not a requirement to opt into intended game behavior.
- Keep `Util/macros.asm` defaults and generated `Config/feature_flags.asm` aligned
  with the integrated RC feature set. Use `--disable <feature>` for isolation.
- Inactive prototypes remain explicitly separate. A default-profile build must
  match the same candidate built with its explicit RC flags before integration.
- This supersedes earlier blanket default-off guidance for active RC work.

## ASM Changes (2026-10-08)
- Agents may change Oracle ASM for bug fixes, small features and tests. Build
  receipts, CI, headless Mesen2 and routine fixtures now catch what the old
  patch-only rule protected against.
- Work in your own git worktree on a `claude/*` or `codex/*` branch, never in the
  shared checkout. Merge by PR after CI passes.
- Each PR states the build receipt result (`Roms/oos168x.build.json` required
  checks) and, for gameplay changes, a headless Mesen2 scenario or routine test.
  Commit the test under `Tests/` when practical.
- Still need scawful's OK: base-ROM writes, playtest staging, Discord posts.
- Lanes and load rules: `~/.context/projects/oracle-of-secrets/scratchpad/agent_board.md`.

## Playtest Builds (2026-09-26)
- Version: `Config/version.json` (`v0.9.0-b<N>`); `build_rom.sh` stamps it into
  message `$C7` ("Oracle of Secrets Preview / v0.9.0-bN") via `Scripts/Build/version_stamp.py`
  (`OOS_SKIP_VERSION_STAMP=1` skips it).
- Integrator only: `python3 Scripts/Build/stage_playtest.py bump`, build in an isolated
  copy, then `stage --from <copy>/Roms` -> `Roms/Playtest/oos-v<ver>-b<N>.sfc` and
  `Roms/Playtest/oos-play.sfc` (fixed name so the Mesen play window keeps one save).
- scawful's play window: `oos-play` (`Scripts/Mesen2/oos_play.py`) opens Mesen instance
  `oos-rc-play` on `Roms/Playtest/oos-play.sfc`, or offers a newer build to the open window;
  `stage` offers automatically. Agents never launch or stop `oos-rc-play` themselves.
- Agent load rules and session board: `~/.context/projects/oracle-of-secrets/scratchpad/agent_board.md`.

## Emacs Review (2026-09-26)
scawful reviews .org/.md in Emacs through agent-bridge (`~/src/tools/agent-bridge/README.md`).
New sessions have `emacs_*` MCP tools; older sessions use the `emacs-agent` CLI.
- Decision needed: add an OPEN heading to `Docs/Planning/Status/decisions.org`, then
  `emacs-agent review <doc> --reason "<the question>"`. Read answers back from that file.
- After editing a tracker entry: `emacs-agent open Docs/oracle.org --line N --reason "..."`.
- Story/dialogue text or shared-file changes that need approval: `emacs-agent diff` (file untouched).
- New playtest build staged: one `emacs-agent notify "..."` line with the ROM path.
- Never: progress logs, focus-stealing (`--focus`), more than one item per decision.

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
   docs. scawful's newer rulings are recorded as DECIDED entries in
   `Docs/Planning/Status/decisions.org` (e.g. the villain chain: prison -> Farore ->
   Kydrog -> Twinrova -> Ganon, Ganondorf/beast finale); follow both.
5. Repo stays small. New plans, reviews, evidence, handoffs, and patches go in
   AFS (`~/.context/projects/oracle-of-secrets/`), not `Docs/`. The only planning
   files that belong in git are the beat sheet, `decisions.org`, approved
   dialogue rewrites, and `Docs/oracle.org`. Policy:
   `~/.context/projects/oracle-of-secrets/memory/repo_hygiene.md`.

## Reference Knowledge
When a skill doesn't cover the task, consult `~/.context/knowledge/` (paths relative to it):

| Task | Read |
|------|------|
| Writing ASM hooks/patches | `hobby/oracle-hook-patterns.md` |
| Sprite development | `hobby/oracle-sprite-ram.md` + `alttp/sprite_catalog.md` |
| Progression/flag work | `hobby/oracle-progression.md` |
| Overworld editing | `hobby/zscustom-overworld.md` |
| Dialogue/message editing | `hobby/oracle-message-format.md` |
| Understanding game architecture | `alttp/architecture.md` |
| Looking up vanilla routines | `alttp/routine_index.md` |
| Finding ROM data tables | `alttp/data_tables.md` |
| SNES hardware questions | `snes/cpu_memory.md`, `snes/ppu_registers.md`, `snes/dma_registers.md` |
| Debugging workflows | `hobby/workflows.md` |
| Cross-referencing addresses | `hobby/usdasm.md` (bank map) + `alttp/ram_map.md` |
| Full project overview | `hobby/oracle-of-secrets.md` |
