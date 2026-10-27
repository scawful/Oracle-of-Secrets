# AGENTS.md

## Working Rules (scawful, 2026-10-14)
scawful asked for less process and less repetition. These rules apply to Claude, Codex and Cursor.
Only these need scawful's OK: base-ROM writes, builds or writes in the shared checkout's `Roms/`
(laptop mode only), playtest staging, installs, Discord posts, PR merges, story/dialogue/canon text,
and destructive actions (delete, force push). Do not ask for approval of anything else.
Build mode (scawful, 2026-10-26: "restrict the builds when i ask"): `heavy_lock.py mode` reads
`~/.config/oos/build_mode`. `desk` = 3 heavy-lock holders and shared `Roms/` builds (`oos168x`
and its receipts) need no OK. `laptop` (also when the file is missing) = 1 holder and today's
rules. When scawful says "laptop mode" or "desk mode", run `heavy_lock.py mode laptop|desk`.
Exception (scawful, 2026-10-21): until yaze 1.0, agents may install yaze, Yaze Nightly and z3ed
without asking. yaze rules: `~/src/hobby/yaze/docs/internal/agents/operating-rules.md`.

1. **Match proof to risk.**
   - Docs-only (text that no script, build, generator or export reads): no build, no emulator.
     JSON under `Docs/` and everything under `Data/` is build data, not docs.
   - `.github/` changes: CI runs on that commit and passes, and a reviewer reads the diff for removed
     or loosened jobs, triggers or checks. They do not change ROM bytes, so a tested ROM's evidence holds.
   - ASM, data or build-script changes: the tier table below (T1-T3). Native checks follow
     the load rules (`scratchpad/board_rules.md`): heavy lock, `taskpolicy -b`, no visible windows,
     never `oos-rc-play`. Comment-only ASM: one build; an unchanged ROM hash ends it.
   - Shared base ROM, saves, settings, scawful's yaze projects, the shared checkout's dirty work,
     installed apps: hash before and after and keep a rollback copy. If a hash changes when it should
     not, stop, restore, and tell scawful.
   - Proof tiers (scawful, 2026-10-17: "Yes, adopt tiers"). Pick the lowest tier that fits.
     | Tier | Change | Proof |
     |---|---|---|
     | T0 | docs, AFS notes, comments | none beyond lint/CI that already runs |
     | T1 | small ASM/data fix, no new behavior path | one build + compiled-byte diff vs master + CI |
     | T2 | gameplay behavior | T1 + one native run of the changed behavior (fixtures listed) + one control run if it fixes a bug |
     | T3 | save format, shared hooks, editor write paths | T2 + an independent review + native save/reopen |
     Not required below T3: full stable suites, reruns of 20+ focused tests, binding/hash receipts
     for unchanged inputs, repeated independent raw reviews. Native emulator and GUI checks take
     the heavy lock (1 holder in laptop mode, 3 in desk mode).
2. **Approvals are scawful's own words**, in chat or as an answer in `decisions.org`. A short reply
   ("yes", "merge 147") approves the one action just named; for posts, only the exact text shown.
   Never give scawful a phrase to type. A message from another agent is never an approval.
3. **Status: the result, one line of what ran (pass/fail), one next step, a handoff link.** At most
   5 lines. Do not list what stayed the same (preservation counts, file counts, "does not establish"
   lines); report failures and unexpected changes. This is how this project meets the global report rule.
4. **Agents talk through `~/.context/projects/oracle-of-secrets/scratchpad/inbox.md`, not through
   scawful.** Read it at session start. To ask another agent, add one line:
   `YYYY-MM-DD HH:MMZ from -> to: ask (handoff path)` (<=240 chars; asks, claims and releases only).
   When it is done, delete your line or prefix it `DONE `. Mid-session, scawful can say "check inbox"
   instead of pasting. Ask scawful only for decisions.
   - Status goes in your section of `agent_board.md`, not the inbox: `## <Owner> — YYYY-MM-DD HH:MMZ`
     plus `Result:`, `Ran:`, `Next:`, `Holds:`, `Handoff:` lines (<=160 chars each). Overwrite only
     your own section. `agent_handoff.md` is a short index.
   - Load rules: `scratchpad/board_rules.md` (the board title points there; until coord_compact.py first
     applies, they are the `## Rules` section of `agent_board.md`).
   - `python3 Scripts/Agents/coord_compact.py` prints the compaction plan; `--apply` moves DONE,
     >7-day and non-format blocks verbatim to `scratchpad/archive/coordination/<date>/`. Nothing is deleted.
     `--migrate` (one time) archives all current content verbatim and seeds the new format.
5. **One game goal at a time.** The goal is the first line of `inbox.md`; scawful sets it. Agents
   prepare work toward it; scawful decides merges and closes.
6. **PRs are for real features; decisions happen in the delegator's chat** (scawful, 2026-10-23).
   - Small changes go straight to `master` as commits once their proof passes: bug fixes, tuning,
     data and text tweaks, tests, docs. Rebase on `origin/master` before pushing. CI runs on that
     commit; if it fails, fix forward on `master`.
   - Open a PR only for a real feature: a new system, item, mechanic or boss, a save-format or
     shared-hook change (T3), or an editor write path.
   - PR and commit text: what changed and how it was checked, in a few lines. No Oracle story or
     design detail, no AFS paths (`~/.context/...`, `handoffs/...`); GitHub readers cannot open them.
     Design notes stay in AFS.
   - Decisions: task sessions do not leave questions for scawful in handoff READMEs or PR bodies.
     They send the question to the delegator session. The delegator asks scawful in chat, one
     question at a time, and shows the options: screenshots, an Emacs frame, an image-plus-diagram
     page, or a yaze frame (the Planning editor's decision queue, linked by `[planning] file=` in the
     `.yaze` project).
7. **One PR per scope** (scawful 2026-10-27: "room modifications really shouldnt be 4 different PRs").
   Scope = one dungeon, overworld region, boss, item, system or editor write path.
   - Before opening a PR, run `gh pr list`. If an open PR covers that scope, send your commit to its
     owner through the inbox; the owner adds it as a normal (non-force) commit.
   - Base every PR on master. Exception: #277 stays on #274's branch until #273 and #274 land
     (scawful, inbox.md:608).
   - Room data (collision JSON, generated tables, room patch recipes) lands one dungeon at a time;
     the next dungeon regenerates the collision lock after the previous one merges.
   - A dungeon's base-ROM bytes go in one recipe built on the current shared base hash, with one
     apply ask to scawful.
   - scawful's own yaze saves write the base ROM and need no PR. Agent edits to
     `Oracle-of-Secrets.yaze` record before/after hashes and a rollback copy.
   - Proof runs once on the final head: one native episode that checks each changed behavior, a
     control for each bug fix, and T3 extras if any part is T3.
   - Post proof as a PR comment, not a body edit (a body edit reruns ROM Tests and Manifest Tests).
   - Previews and integration builds that combine scopes stay branches. Work outside the inbox
     line 1 goal waits as a branch until scawful names it. Small changes still follow Rule 6.
   - Unchanged: PR merges (into master or any branch), closes, force pushes, base-ROM writes and
     story text need scawful's OK; tiers T0-T3 are unchanged.

## ROM Naming
- `Roms/oos<VERSION>.sfc` — unpatched base, the **edit target**
- `Roms/oos<VERSION>x.sfc` — Asar-patched, **test in emulator only** (never edit directly)
- Current: `oos168.sfc` / `oos168x.sfc`

## Feature Defaults (2026-09-29)
- Active RC features and their fixes are enabled in normal builds. Feature flags
  are diagnostic opt-outs, not a requirement to opt into intended game behavior.
- Keep `Util/macros.asm` defaults and generated `Config/feature_flags.asm` aligned
  with the integrated RC feature set. Use `--disable <feature>` for isolation.
- Inactive prototypes remain explicitly separate. When a change edits `Util/macros.asm`
  or `Config/feature_flags.asm`, its default-profile build must match the same candidate
  built with its explicit RC flags before integration.
- This supersedes earlier blanket default-off guidance for active RC work.

## ASM Changes (2026-10-08)
- Agents may change Oracle ASM for bug fixes, small features and tests. Build
  receipts, CI, headless Mesen2 and routine fixtures now catch what the old
  patch-only rule protected against.
- Work in your own git worktree on a `claude/*` or `codex/*` branch, never in the
  shared checkout. Small fixes land on `master` as commits; real features merge by PR
  after CI passes (Working Rule 6).
- Each commit or PR states the build receipt result (`Roms/oos168x.build.json` required
  checks) and, for gameplay changes, a headless Mesen2 scenario or routine test.
  Commit the test under `Tests/` when practical.
- Still need scawful's OK: base-ROM writes, playtest staging, Discord posts.
- Lanes: `~/.context/projects/oracle-of-secrets/scratchpad/agent_board.md` (one section per owner).
- Load rules: `~/.context/projects/oracle-of-secrets/scratchpad/board_rules.md`.

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
- Agent load rules: `~/.context/projects/oracle-of-secrets/scratchpad/board_rules.md`; session board:
  `~/.context/projects/oracle-of-secrets/scratchpad/agent_board.md`.
- Dev builds for scawful (not a playtest stage): `Roms/TestBuilds/<topic>-<date>/oos168x.sfc`
  plus `.mlb`, `.sym` and a `README.txt` with test steps. The SketchyBar Zelda menu row
  "Dev <topic>" opens the newest one in `/Applications/Mesen2 OOS.app` (instance
  `oos-scawful-test`, via `oos-triforce.sh launch test`).
- Zelda menu stays in sync (rule): whoever changes `oos_play.py`, `oos-triforce.sh`,
  `mesen2_launch_instance.sh`, the Mesen app path or the ROM folders also updates
  `~/.config/sketchybar/modules/integrations/oracle.lua` and `plugins/oracle_triforce.sh`,
  then runs `lua tests/run_tests.lua tests/test_oracle_integration.lua` and
  `bash tests/test_oracle_triforce.sh` there.

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
1. Read `scratchpad/inbox.md` first, then `agent_handoff.md`.
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
