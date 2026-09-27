# Oracle of Secrets: audit of agent instruction surfaces (2026-09-26, read-only)

Result first: at least **13 documents** tell agents where to start or what outranks what. They
name **at least 6 different "first" files** and **3 different story authorities**. The only
precedence rule written down (code > Docs > AFS > MEMORY) is broken by the files that state it:
they send agents to MEMORY and AFS before they send them to Docs. Most of the rules that
constrain agents today are AI-authored (class C) or stale (class S). The rules with scawful
evidence (class A) are few. They are the 2026-09-26 agent_board rules, the story canon rulings,
and the RC definition.

Provenance caveat: **git authorship cannot separate scawful from agents.** All 9 commits that
touched `AGENTS.md` (2026-01-21 .. 2026-04-12) are authored `scawful <justin.scofield@outlook.com>`
and have no Co-Authored-By trailer. The current `AGENTS.md` sections "Playtest Builds",
"Emacs Review", rule 4 and "Reference Knowledge" are **uncommitted** working-tree edits.
The same is true of the `CLAUDE.md` -> `@AGENTS.md` collapse. The canon sheet, the RC plan and
`decisions.org` are **untracked**:
`?? Docs/Planning/story_canon_beat_sheet.md`, `?? Docs/Planning/RC_MASTER_PLAN.md`,
`?? Docs/Planning/Status/decisions.org`. Worktrees and cloud sessions cannot see these files.
The rule-4 authority that AGENTS.md cites therefore does not exist on any branch.

Legend: A = scawful with evidence; B = verified fact; C = AI inference stated as a rule;
S = stale; X = contradiction.

---

## 1. Map of instruction surfaces

| # | Path | What it claims | Modified |
|---|------|----------------|----------|
| 1 | `oracle-of-secrets/AGENTS.md` | ROM naming, build, "Read `agent_handoff.md` first", canon = single SoT, Emacs review protocol, playtest staging | 2026-09-26 (uncommitted) |
| 2 | `oracle-of-secrets/CLAUDE.md` | `@AGENTS.md` only (the 70-line skill table and rules were deleted, uncommitted) | 2026-09-02 |
| 3 | `~/src/CLAUDE.md` -> `~/src/AGENTS.md` | Oracle tasks via `mcp__book-of-mudora__manage_tasks`, fallback `Docs/oracle.org` | 2026-09-02 |
| 4 | `~/CLAUDE.md`, `~/.claude/CLAUDE.md` | Generic rules: ask one clarifying question when ambiguous; read MEMORY + handoff first | n/a |
| 5 | `~/.claude/projects/.../memory/MEMORY.md` | "RC entry point = RC_MASTER_PLAN + canon (supersedes Feb AFS scratchpad, which is stale)", then lists the Feb AFS files under "Read These First"; blockers; validation policy; story decisions | 2026-09-26 |
| 6 | memory/`oos-state-2026-09-25-evening.md`, `oos-rc-state-2026-09-24.md` | Point-in-time state; "read handoff `claude_session_audit_2026-09-25.md` first" | 09-24/25 |
| 7 | memory/`plan-review-emacs.md` | `> **Review:** APPROVED/REJECTED` stamps are authoritative plan status | 2026-09-26 |
| 8 | memory/other 9 files | Reference/project notes (bridge, Mesen gotchas, 2P, ring SRAM) | 09-24..26 |
| 9 | `~/.context/projects/oracle-of-secrets/CONTEXT_INDEX.md` (= repo `.context/`, symlink) | Precedence code > Docs > AFS > MEMORY; own read order: handoff -> active_investigations -> technical_debt -> MEMORY -> index | header 2026-02-22, file 09-15 |
| 10 | `scratchpad/agent_handoff.md` (130 lines, 35 KB) | "Sources Of Truth" list (AGENTS/RUNBOOK first, handoff second); stacked LATEST/PREVIOUS updates 09-14..09-25 | 2026-09-25 |
| 11 | `scratchpad/agent_board.md` | Heavy lock, throttle, emulator, isolated builds, integrator, Emacs rules, **quoted and dated scawful** | 2026-09-26 |
| 12 | `scratchpad/next_session_prompt.md` | "Your Mission: Maku Tree hint cascade" | 2026-02-05 |
| 13 | `scratchpad/active_investigations.md` | APU deadlock OPEN, D6 entrance OPEN | 2026-02-21 |
| 14 | `scratchpad/lessons_learned.md` | "Validation Policy (MANDATORY — Read Before Every Session)"; `scripts/` tool list | 2026-02-05 |
| 15 | `scratchpad/state.md` | "AFS consolidation in progress" | 2026-02-05 |
| 16 | `~/.context/projects/oracle-of-secrets/memory/technical_debt.md` | Canonical debt list (per Context_Model) | 2026-02-22 |
| 17 | project `knowledge/*.md` (agent-reference, oracle_quick_reference, OoS_Code_Guidelines, ...) | Old AGENTS.md text, `mesen-agent`, `scripts/` paths | 2025-12 .. 2026-02-24 |
| 18 | `~/.context/knowledge/hobby/oracle-*.md`, `workflows.md`, `oracle-of-secrets.md` | Build/hook rules, `mesen-agent build` "preferred", `scripts/` paths | all 2026-03-18 (before the 04-12 Scripts/ reorg) |
| 19 | `~/.claude/skills/oos-*` (13) + `oracle-debugger`, `mesen2-oos-debugging` | Domain rules, build/validate commands | 2026-04-12 (mesen2: 01-29) |
| 20 | `~/.claude/skills/synced/*/oos-{asm,build,dialogue}` | Same, plus dialogue voice/lore rules | 2026-09-24 |
| 21 | `~/src/lab/afs-scawful/skills/*` (+ a worktree copy) | Duplicate mesen2/hyrule/alttp skills | n/a |
| 22 | repo `.claude/agents/*.md` (9 subagents) | Story expert (`model: haiku`) etc.; no pointer to canon | 2025-12-07 / 2026-02-07 |
| 23 | repo `.claude/settings.local.json` | Allowlists old MCP tool names (`hyrule-historian__search_ram_comments`, `book-of-mudora__run_build`, `yaze_mcp__*`) | n/a |
| 24 | `Docs/GEMINI.md`, `.gemini/yaze_agent_prompt.md` | "Follow AGENTS.md first" | 02-24 / 02-07 |
| 25 | `Docs/RUNBOOK.md` | "primary how-do-I doc"; "Agent Sources Of Truth (read in order)" | 2026-09-15 (M) |
| 26 | `Docs/Debugging/Agent/Context_Model.md` | Precedence + canonical files (handoff, active_investigations, technical_debt) | reviewed 2026-07-27 |
| 27 | `Docs/Planning/README.md` | "Start Here": release_timeline -> rc_content_checklist -> content review -> **April execution focus**; canonical story = `narrative_design_master_plan.md` | 2026-08-06 |
| 28 | `Docs/Planning/RC_MASTER_PLAN.md` (untracked, mode 0600) | "This is the current planning entry point." Owner = Codex thread `01a0d06d…` | 2026-09-24 |
| 29 | `Docs/Planning/story_canon_beat_sheet.md` (untracked) | "supersedes conflicting claims in all other narrative docs"; `[DECIDED]` tags cite scawful 07-25 / 09-02 | 2026-09-25 |
| 30 | `Docs/Planning/Status/decisions.org` (untracked) | Decision inbox; answers move to `Docs/oracle.org` | 2026-09-26 |
| 31 | `Docs/Planning/Plans/dialogue_review_notes.md:14` | "Do not edit `Core/messages.org` as a publication path" | M |

---

## 2. Competing "source of truth" / "read first" claims

(a) There are **13 claims**, and they do not agree.

| Claimant | Says read/obey first | Story authority named |
|---|---|---|
| AGENTS.md:30,34 | `agent_handoff.md`; routing `.context/CONTEXT_INDEX.md` | canon beat sheet (rule 4) |
| AGENTS.md:15 | `agent_board.md` for "agent load rules" | — |
| MEMORY.md:4 | `RC_MASTER_PLAN.md` + canon ("supersedes Feb AFS scratchpad") | canon |
| MEMORY.md:5-9 | then CONTEXT_INDEX, handoff, **next_session_prompt**, active_investigations | — |
| oos-state-2026-09-25-evening.md:17 | `handoffs/claude_session_audit_2026-09-25.md` | — |
| CONTEXT_INDEX.md:18-24 | handoff -> active_investigations -> technical_debt -> MEMORY | canon (line 113) |
| Context_Model.md:21-33 | precedence code > Docs > AFS > MEMORY | — |
| agent_handoff.md:65-71 | AGENTS/RUNBOOK -> handoff -> canon -> dialogue -> gates -> timeline | canon |
| RUNBOOK.md:5-12 | AGENTS -> handoff -> canon -> ... ; "this is the primary doc" | canon |
| RC_MASTER_PLAN.md:5 | "current planning entry point" | canon |
| Planning/README.md:8-20 | release_timeline -> checklist -> review -> April focus | **narrative_design_master_plan.md** |
| story_canon_beat_sheet.md:5,15 | itself, then Story_Event_Graph, then narrative_design_master_plan | itself |
| lessons_learned.md:8 | "MANDATORY — Read Before Every Session" | — |

Where they agree: every current doc except Planning/README names the canon sheet as story
authority, and AGENTS, RUNBOOK and the handoff give the same order.
Where they disagree:
- RC_MASTER_PLAN is the "entry point" in MEMORY and in the plan itself. AGENTS, RUNBOOK, the
  handoff, CONTEXT_INDEX and Context_Model do not list it.
- agent_board.md is the most current file and holds the only dated scawful rules. CONTEXT_INDEX,
  RUNBOOK and the handoff do not list it. AGENTS.md:15 is the only pointer to it.
- MEMORY.md calls the Feb AFS scratchpad stale on line 4. On lines 6-8 it lists three Feb files
  under "Read These First".
- Context_Model says MEMORY ranks lowest. CONTEXT_INDEX:62 and :76/:86 make MEMORY.md the
  **primary** file for the crystal bitfield, the probe gotcha and the $20-$23 gotcha.
- Who coordinates is unclear. RC_MASTER_PLAN:3 names Codex thread `01a0d06d…` as owner, and
  Codex quota is out until 09-30 (oos-rc-state-2026-09-24.md). agent_board:5 names
  "Claude RC test handoff" as integrator.

---

## 3. Top 10 class-C or stale rules that actively constrain agents

| # | File:line | Rule | Class | Impact |
|---|---|---|---|---|
| 1 | synced `oos-dialogue/SKILL.md:14-15`; `oos-dialogue-author/SKILL.md:21,30,171` | "`Core/messages.org` — Source dialogue — edit this file"; `message.asm` "generated from messages.org" | S + X | Sends dialogue agents to a file that the repo calls "review snapshots only" (CONTEXT_INDEX:118, handoff:77) and "not a publication path" (dialogue_review_notes:14). The real source is `Data/dialogue/expanded_messages.json` -> `Core/Generated/expanded_messages.asm` (verified: `Core/message.asm:57` incsrc). Edits there are lost. |
| 2 | synced `oos-dialogue/SKILL.md:91-96` | "Never mention Ganondorf before Lava Lands… Final: 'I am Ganondorf.'" plus a Ganondorf voice row | C + X | Directly contradicts canon :68 ("Ganondorf in hiding framing rejected"), the mindless residue and the wordless coda, and AGENTS rule 4. Most likely to make an agent write off-canon text. |
| 3 | MEMORY.md:103 | "Ganondorf origin: Ambiguous in-game (supports ALTTP-Ganon and OoT-intruder readings)" — "Locked" | C/S + X | Presented as locked. Canon rejects the OoT framing. |
| 4 | MEMORY.md:7 + `next_session_prompt.md` | "Your Mission: wire $1C9/$1CA/$1CB for D2/D4/D6" | S | The code has moved on: `maku_tree.asm:29-32,185` uses `$1CA` = 7 crystals and marks `$1C9`/`$1CB` RESERVED; the 09-26 audit lists `$1C9` as a protected Impa hint. A new session following it would overwrite Impa text. |
| 5 | MEMORY.md:81, :99 | "Maku hint text $1C5-$1CB are placeholder" and "Don't touch … Maku cascade 0x1C5-0x1CB" | S + X (with each other) | `dialogue_audit_2026-09-26.md:140` shows real text in `$1C5`. The "Don't touch" list has no scawful citation (C). The 09-26 audit repeats it as "protected sets", so the inference now propagates. |
| 6 | `oos-build-pipeline/SKILL.md:41-50`, `oos-hook-author:276-278`, synced `oos-build:14-21`, `oos-asm:15`, all `~/.context/knowledge/hobby/*` | `./scripts/build_rom.sh`, `scripts/check_zscream_overlap.py`, `scripts/mesen2_client.py`, `mesen-agent build` "preferred" | S | The paths moved to `Scripts/Build/…` and `Scripts/Mesen2/…` on 04-12 (689bf463). `Scripts/check_zscream_overlap.py` and `Scripts/mesen2_client.py` are missing. `mesen-agent` is not on PATH. The synced skills were written 09-24 and are still stale. |
| 7 | `oos-hook-author:250-252`, `oos-overworld-workshop:96`, `oos-build-pipeline:80-82`, `oracle-hook-patterns.md:301,317` | "Banks $21-$27, $29-$2A: NEVER USE / never org into these banks" | C (over-absolute) | `Scripts/Build/check_zscream_overlap.py:15-27` has `OWNED_REGIONS` that deliberately allow ZSCustomOverworld, lost_woods, bunny_hood and water_fill_table inside the reserved banks. The script is the real contract. |
| 8 | AGENTS.md:5-6,28 (+ skills, knowledge) | "Current: oos168x.sfc test in emulator"; "Build: `./Scripts/Build/build_rom.sh 168`" | S + X | agent_board:20-21 (A, 09-26) requires isolated-copy builds and reuse of staged ROMs. The shared `oos168x.sfc` is stale and GM-005-guarded (memory 09-24/25). The playtest ROM is `Roms/Playtest/oos-play.sfc`. An in-place build by any agent breaks the heavy-lock and integrator rules. |
| 9 | MEMORY.md:118-124, `lessons_learned.md:8-45` | "Feature flags for risky hooks must stay OFF until runtime regression"; "set it to 0 immediately" | C (Feb, agent-written, no scawful quote) | Useful intent. It conflicts with current practice: playtest builds turn flags on (handoff:3, "four new flags… flags on"), and `!ENABLE_WATER_GATE_HOOKS = 1` ships. An agent could flip shared flags to 0 without asking. |
| 10 | CONTEXT_INDEX.md:99,106,168-169 | "Build commands / Mesen2 client / z3dk: primary file = project `CLAUDE.md`" | S | `CLAUDE.md` is now `@AGENTS.md` and has none of this. Agents reach a dead end and improvise. |

Runners-up:
- MEMORY.md:72 lists "Pendant misalignment" as High, but the handoff:103 says the S1/S2 chest data
  is already fixed.
- MEMORY.md:75 says dialogue bundles were "appended to `Core/message.asm`", which is now the
  generated path.
- MEMORY.md:74 says `oos168_test2.sfc`.
- MEMORY.md:134 says "2 worktrees"; there are 8.
- active_investigations.md:26 says the APU deadlock is "OPEN"; MEMORY reclassifies it.
- The skill `oracle-debugger:251` diffs `oos167x.sfc`.
- `.claude/settings.local.json` allowlists MCP tool names that no longer exist.
- The `oracle-of-secrets-story-expert` subagent (haiku) never mentions the canon sheet.

(d) Class-C rules that most constrain behavior today:
- #2, #3 and #5 constrain story and dialogue content.
- #7 constrains code placement.
- #9 constrains feature flags.
- "Required Language" (lessons_learned:22-28) and "Never claim verification" constrain reporting.
  These two are well aligned with ~/CLAUDE.md (scawful's global) and can be promoted to A.

(b) Duplicates with different wording:
- **Validation**: AGENTS rule 3, ~/CLAUDE.md rule 5, MEMORY "Validation Policy" 1-5,
  lessons_learned "MANDATORY", CLAUDE.md (old) rule 4, GEMINI.md rule 5. There are six copies.
- **ROM naming**: AGENTS:3-6, workflows.md:7, oracle-of-secrets.md:5, skills oos-build-pipeline:23,
  oos-dungeon-workshop:23, synced oos-build:29-30, MEMORY:98, state.md.
- **Crystal bitfield**: MEMORY, handoff:128, next_session_prompt, CONTEXT_INDEX:62 (points at
  MEMORY), `Core/sram.asm`.
- **Code gotchas** ($20-$23, SprState, +20px Y, JumpTableLocal, DBR): MEMORY 1-6,
  lessons_learned:115-121, agent-reference:269, debugging_patterns, skills.
- **Knowledge routing table**: AGENTS:41-57, the old CLAUDE.md, CONTEXT_INDEX:26-45.
  The table is identical in all three.
- **Emacs review**: AGENTS:17-25 and agent_board:24-28 (the board says "Details: AGENTS.md").
  There is also a *separate* mechanism in memory `plan-review-emacs.md`
  (`> **Review:**` stamps, `~/src/tools/plan-review`).
- **Task tracker**: `~/src/CLAUDE.md` (book-of-mudora `manage_tasks`, fallback `Docs/oracle.org`),
  AGENTS:22 (`Docs/oracle.org` via emacs-agent), and decisions.org ("move results into
  `Docs/oracle.org`").

(c) Stale items summary:
- ROM version and build: all `scripts/` paths, `mesen-agent`, `oos167x`, `oos168_test2`.
- AFS scratchpad files called "stale" but still "read first": next_session_prompt,
  active_investigations, lessons_learned, state.md (all Feb), technical_debt (02-22).
- CONTEXT_INDEX header date 02-22.
- Planning/README still says "Start Here" at the April focus, which the handoff:108 calls
  superseded.
- MCP names in `.claude/settings.local.json`.
- The branch and worktree list in MEMORY.
- Project `knowledge/agent-reference.md` is the January AGENTS.md verbatim.

---

## 4. Contradictions table

| # | Source 1 | Source 2 | Conflict | Likely winner |
|---|---|---|---|---|
| X1 | skills oos-dialogue(-author): edit `messages.org` | CONTEXT_INDEX:118, handoff:77, dialogue_review_notes:14 | Where dialogue is authored | Repo (JSON -> generated) |
| X2 | synced oos-dialogue:91 "I am Ganondorf" | canon :68,:81; AGENTS rule 4; RC plan :99 | Named villain reveal vs rejected framing | Canon (A) |
| X3 | MEMORY:103 Ganondorf "ambiguous, both readings" | canon :68 OoT framing rejected | Story lock | Canon (A) |
| X4 | Planning/README:20 canonical = narrative_design_master_plan | canon :15-17 ranks it 3rd | Story authority | Canon |
| X5 | Planning/README:15 start at April focus | handoff:108 "April focus… superseded" | Current priorities | Handoff / RC plan |
| X6 | MEMORY:4 RC_MASTER_PLAN is the entry point | AGENTS:34, RUNBOOK:5, handoff:65 omit it | Entry point | Undecided (Q1) |
| X7 | MEMORY:4 AFS scratchpad stale | MEMORY:6-8 lists AFS files "Read These First" | Self-contradiction | Neither, prune |
| X8 | Context_Model: MEMORY lowest | CONTEXT_INDEX:62,76,86 MEMORY = primary file | Precedence | Context_Model |
| X9 | AGENTS:28 build in place; AGENTS:5 test `oos168x` | agent_board:20-23 isolated copy, integrator only; playtest ROM `Roms/Playtest/oos-play.sfc` | Who builds, where | agent_board (A) |
| X10 | Skills/knowledge: reserved banks NEVER | `check_zscream_overlap.py:15-27` OWNED_REGIONS | Code placement | Script (B) |
| X11 | MEMORY:121-123 flags OFF until validated | handoff:3 flags on in test builds; `ENABLE_WATER_GATE_HOOKS = 1` | Flag policy | Undecided (Q5) |
| X12 | MEMORY:81 Maku `$1C5-$1CB` placeholder; next_session_prompt `$1C9` = D2 hint | `maku_tree.asm:29-32`; audit 09-26 `$1C9` = Impa hint, `$1C5` real text | Message ID ownership | Code (B) |
| X13 | RC_MASTER_PLAN:3 owner Codex thread | agent_board:5 integrator "Claude RC test handoff" | Coordinator | agent_board (current) |
| X14 | AGENTS:20 decisions via `decisions.org` | memory plan-review-emacs: `> **Review:**` stamps authoritative | Where scawful's verdicts live | Both? (Q3) |
| X15 | `~/src/CLAUDE.md` tasks in book-of-mudora `manage_tasks` | AGENTS:22 / decisions.org -> `Docs/oracle.org` | Task tracker SoT | Undecided (Q4) |
| X16 | ~/CLAUDE.md "ask one clarifying question before executing" | parallel-agent board: integrator relays, "one item per decision" | Ask directly vs route via decisions.org | decisions.org for Oracle |
| X17 | CONTEXT_INDEX:99 etc. -> project `CLAUDE.md` | `CLAUDE.md` = `@AGENTS.md` | Dead pointer | Fix index |
| X18 | active_investigations:26 APU deadlock OPEN | MEMORY "Active Blockers / APU" reclassified (Mesen restore bug, fixed) | Bug status | MEMORY (evidence doc exists: `Docs/Planning/Status/spc_restore_fix_2026-09-14.md`) |

---

## 5. Proposed single-source-of-truth layout

Principle: **one owner per kind of rule; every other surface is a one-line pointer.** Everything
that owns a rule is committed to git, and each rule carries a provenance tag (`[scawful YYYY-MM-DD]`
or `[agent]`).

| Kind of rule | Owner (single file) | Everything else becomes |
|---|---|---|
| Entry point, read order, precedence, operating rules (A only) | `AGENTS.md` (≤80 lines, committed) | CLAUDE.md, GEMINI.md, RUNBOOK "Agent SoT", handoff "Sources Of Truth", CONTEXT_INDEX "Read Order", Context_Model -> pointer "see AGENTS.md" |
| Machine and concurrency rules (heavy lock, emulators, integrator, lanes) | `scratchpad/agent_board.md` (already A-quoted) | AGENTS.md keeps one pointer line (already present) |
| Story/lore/dialogue content rulings | `Docs/Planning/story_canon_beat_sheet.md` (**commit it**) | Planning/README:20 -> canon; delete Ganondorf rules from synced oos-dialogue skill; delete MEMORY "Story Decisions (Locked)" and point to canon |
| Dialogue pipeline (where text lives, protected IDs) | `Docs/Planning/dialogue_registry_and_workflow.md` + `Data/dialogue/message_registry.json` | Rewrite the oos-dialogue(-author) skills' "Source" sections as a pointer; move the "Don't touch" list here with provenance or drop it |
| Current priorities / RC plan | `Docs/Planning/RC_MASTER_PLAN.md` (**commit it**; one owner) | Planning/README "Start Here" -> RC plan; retire April focus; handoff keeps only session state |
| Current session state | one short `scratchpad/agent_handoff.md` (≤60 lines, latest only) plus `handoffs/*.md` | Move the stacked PREVIOUS UPDATE blocks to `handoffs/`; MEMORY state files -> pointer |
| Decisions waiting on scawful | `Docs/Planning/Status/decisions.org` (**commit it**) | Plan-review stamps: say in AGENTS whether they also count (Q3) |
| Build/debug commands | `Docs/RUNBOOK.md` + `Scripts/README.md` (B, verified) | Skills and `~/.context/knowledge/hobby/*`: replace command blocks with "see RUNBOOK"; fix `scripts/` -> `Scripts/Build`, drop `mesen-agent` |
| ASM gotchas and conventions | skills `oos-hook-author` / `oos-asm-quality` (B, with evidence commit) | MEMORY "Critical Code Gotchas", lessons_learned "Known Pitfalls", agent-reference -> pointer |
| Code placement / bank safety | `Scripts/Build/check_zscream_overlap.py` (the executable contract) | Skills say "run the script; reserved banks allowed only via OWNED_REGIONS" |
| Claude-only tactical notes | `MEMORY.md` (index only, no rules, no status) | Remove "Active Blockers", "Validation Policy", "Story Decisions", "Worktree & Branch Status", "Dialogue Quick Reference" |

Delete or archive to `scratchpad/archive/`:
- `next_session_prompt.md`
- `state.md`
- `active_investigations.md` (after its 2 open items move to the handoff or to `Docs/oracle.org`)
- `lessons_learned.md` (keep its "Required Language" table and promote it to AGENTS if scawful confirms)
- `codex_briefing_2026-02-12.md`, `gemini_*`, `ralph-loop.md`, `roadmap_phase0_*`
- project `knowledge/agent-reference.md` (it is the January AGENTS.md)
- `.claude/settings.local.json` old MCP allow entries

Fix: CONTEXT_INDEX dead `project CLAUDE.md` pointers; add the canon pointer to the story-expert subagent.

---

## 6. Questions for scawful (one line each)

1. Which single file is the agent entry point: `AGENTS.md`, `RC_MASTER_PLAN.md`, or `agent_board.md`?
2. May the untracked `story_canon_beat_sheet.md`, `RC_MASTER_PLAN.md` and `decisions.org` be committed so worktrees and cloud sessions see them?
3. Do `> **Review:**` plan stamps count as decisions, or is `decisions.org` the only decision inbox?
4. Is the task tracker `Docs/oracle.org` or book-of-mudora `manage_tasks`?
5. Did you decide "risky feature flags stay OFF until runtime-validated", or may agents enable flags in test builds only?
6. Did you decide the dialogue "Don't touch" list (Kydrog 0x21, Mask Salesman, Deku 0x140/141, Librarian 0x199-19F, Maku 0x1C5-1CB)?
7. May agents delete the Feb AFS scratchpad files (next_session_prompt, state, active_investigations, lessons_learned) after moving the live items?
8. Should the skills stop carrying commands and lore and point to RUNBOOK and canon instead?
