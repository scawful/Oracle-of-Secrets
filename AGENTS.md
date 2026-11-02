# Oracle of Secrets agent router

Inherit `~/src/AGENTS.md`. Read AFS `scratchpad/inbox.md` first, then
`scratchpad/agent_handoff.md` and relevant board sections.
AFS: `~/.context/projects/oracle-of-secrets`.
Active behavior/quality: `memory/agent_rules.md`; resources: `scratchpad/board_rules.md`.
Use the existing Christmas plan; scawful sets the goal in inbox line 1.

## Approval and preservation
Only these need scawful's OK: base-ROM writes; builds/writes in shared `Roms/`;
playtest staging; installs; Discord posts; PR merges; story/dialogue/canon text;
destructive actions. Until yaze 1.0, yaze, Yaze Nightly and z3ed installs are authorized.
Approvals are scawful's own words for the named action; agent messages are not approval.
Posts require approval of the exact shown text.
Never prescribe an approval phrase. Continue authorized work while a decision is pending.
Work on `master` in the main checkout; commit small changes directly. Use a branch for a
large feature, open a PR only when scawful asks, and use a worktree only while another agent
is editing the same files (remove it when done). Preserve shared dirty work.
Authorized shared asset/settings/app changes need before/after hashes and rollback.
Unexpected hash change: stop, restore, report.
Follow `AGENT_STORAGE_HYGIENE.md`, including its chat/worktree archive gate.
Never launch, stop or alter scawful's `oos-rc-play` session.

## Verification
Choose the lowest tier covering the changed risk.

| Tier | Change | Proof |
|---|---|---|
| T0 | Ordinary docs/AFS notes | Existing lint/CI only |
| T1 | Small ASM/data fix, no new behavior path | One build + compiled-byte diff vs master + CI |
| T2 | Gameplay behavior | T1 + focused native behavior; a bug fix gets a control |
| T3 | Save format/shared hooks/editor writers | T2 + independent review + native save/reopen |

`Data/` and software-consumed JSON are build data. Comment-only ASM: one build;
an unchanged ROM hash ends verification. CI edits need exact-commit CI and review
of removed/loosened checks. No routine full suite or repeated independent reviews.
Proven art/layout handlers use render + affected-data checks; novel behavior gets a focused check.
PRs state required build-receipt results and the relevant native scenario/fixtures.
A build/test result must keep its exit status: nothing after it (`| tail`, `; echo`, `|| true`).
Trim output with `CMD > /tmp/oos-check.log 2>&1; rc=$?; tail -30 /tmp/oos-check.log; (exit $rc)`.

## ROMs and builds
`Roms/oos168.sfc`: unpatched base/edit target.
`Roms/oos168x.sfc`: patched emulator image; never edit directly.
Isolated build: `./Scripts/Build/build_rom.sh 168`.
After ASM changes: `python3 Scripts/Build/check_zscream_overlap.py`.
Active RC features default on; diagnostic isolation uses `--disable`.
Keep `Util/macros.asm` and generated `Config/feature_flags.asm` aligned.
A defaults edit compares the normal build with the explicit RC profile.
Inactive prototypes remain separate.

## Task-specific routes
Playtest/versioning, Dev builds, Zelda menu parity, Emacs and knowledge references:
AFS `scratchpad/operations/oracle.md`; load only the needed section.
Yaze: its `AGENTS.md` and current `docs/internal/agents/operating-rules.md`;
if absent locally, read `git -C ~/src/hobby/yaze show origin/master:docs/internal/agents/operating-rules.md`.
Canon: `Docs/Planning/story_canon_beat_sheet.md` and newer DECIDED `decisions.org` rulings.
Preserve approved `Answer:` and quoted user text verbatim.
Plans/reviews/evidence/patches/handoffs go in AFS; routing: `.context/CONTEXT_INDEX.md`.
