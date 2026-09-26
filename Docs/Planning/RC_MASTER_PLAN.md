# Oracle of Secrets — RC master plan

Updated: 2026-09-23. Owner: opening/coordination thread 01a0d06d-ee1d-7893-be24-c52b3a73c09c.

This is the current planning entry point. It consolidates priorities and ownership; detailed packets retain their evidence. [Story canon](story_canon_beat_sheet.md) remains the authority for creative rulings. Suggestions below are not automatically canon. Documentation and source evidence do not establish current gameplay acceptance.

**Usage-limit continuation:** [Claude Thursday handoff](Plans/claude_thursday_continuation_2026-09-24.md) records the stable Yaze candidate, source/test versus UI evidence, manifest section11.4 change requests, migration ownership and the unanswered Goron layout choice. Coordinator checked canonical worktree clean at `17b40b061` and general editor idle when writing it. Hourly monitoring remains paused; do not assume background Codex work continues.

## 1. What RC means

Scawful's ruling: a main adventure playable from a new file through the ending, with all eight dungeons, all three shrines, required rewards/progression, and normal saves working. Optional content and nonblocking bugs may remain; later RCs can add content. No content freeze is required. Exact version syntax is still open. No current ROM is promoted by this plan.

Keep base/edit ROM and patched/test ROM separate. Use existing Yaze save/backup facilities; automatic timestamped backups are not release versions. Preserve named milestone artifacts with base/source/flag/build identity and known issues. Current source is heavily dirty; a HEAD hash alone is not a reproducible build identity.

## 2. Work order

### Thursday, September 24 — daily target

Thursday manifest review findings (backend, read-only, final contract pending): proposed protected ranges contain 1,481 bytes of unwritten gap padding because regions merge across gaps of up to16 bytes. Exact-emission mode should union only overlapping/touching spans. Expanded hooks are omitted from proposed protection; Yaze v3+ `SaveDiggableTiles` writes PC `$140980..$1409C0` and `$140149`, overlapping Oracle emitted graphics data at `$140980..$140998` and `$140149..$14014B`. This is source/format evidence, not observed corruption; actual Oracle save-path reachability is requested. Dungeon data/allocation/editor regions and three stream pointer tables had no proposed overlaps, which does not qualify overworld writes. Yaze ignores proposed provenance/hash JSON fields, so a producer gate or explicit consumer enforcement is required. Semantic manifest migration remains blocked pending minimal contract review; editor owner notified. No ROM changes or new tests from this review.

Final review correction: section11.4 of `Plans/python_tooling_extraction_handoff_2026-09-24.md` now contains the completed minimal contract. Normal coordinated File Save calls `OverworldEditor::Save()`, which does **not** call the conflicting diggable writer. That writer is reachable through lower-level `Overworld::Save(Rom*)` after prior serializers succeed and PC `$140145` is `$03..$FE` (v3); vanilla/`$FF`/v1/v2 skip it. No current native File Save corruption is established. Exact-union, expanded-protection/writer-exclusion and producer-enforced patched-output hash requirements remain. Backend owner is done and stopped; editor owner received correction. No production code or ROM changed in this review.

Finish one demonstrated Oracle editing workflow in the canonical Yaze candidate, then use that workflow for a reviewed RC-A content change. Morning check: combined worktree clean at `17b40b061`, application source `699c86326`; all nine peer agents inactive/not loaded. Reactivated only general editor and backend owners:

1. General editor: identify one reliable native session, use isolated app data/practice ROM/project, complete Origins `$005` edit -> Undo/Redo -> Save As -> reopen, fix concrete blockers and report actual interaction evidence. Preserve user's other sessions/layouts and original ROMs. No other agent assigned UI control.
2. Backend: bounded read-only review of Claude's section11 manifest proposal and external `manifest-review/` package. Check exact protection spans, allocation compatibility, sprite-table semantics and hash provenance. No competing build or implementation; return accept/change requests to root and editor owner.
3. Root/user next creative action: choose one existing Goron `$77/$87` route proposal or one Origins puzzle adjustment for the first intentional content-edit session after editor qualification. No layout approval inferred from today's planning request. Title/summons remains the first opening implementation milestone; do not add the new-file experiment cinematic to today's scope.

Other agents remain parked until a concrete dependency arises. Claude owns parser/manifest implementation; section11 reports parser-only byte parity and proposal artifacts ready, semantic migration unapplied. Keep asar default and scanner fallback. Daily success is usable editing plus one clear next content change, not another branch/build inventory or RC completion claim. Hourly monitoring remains paused unless resumed separately.

**Immediate user priority override (September 23): usable Yaze before weekly ChatGPT usage is exhausted.** User reports roughly 52% usage consumed and has Cursor/Claude available. Concentrate active implementation on the Yaze save defect and editor integration. Deliver an exact candidate app/worktree, focused validation, short user-operated Origins/Goron editing workflow, known limitations and portable Cursor/Claude handoff. One coordinated build/check cycle; avoid duplicate audits and speculative features. Sprite owner finishes only its bounded current deliverable and usability handoff. Oracle patrol, shrine, Goron, finale and handheld owners preserve completed packets and stop further work until needed. These instructions supersede the immediate scheduling labels below, not the RC scope or narrative order. No model settings were changed.

**UI/UX follow-through (supersedes treating the build as completion):** user explicitly rejects save-fix/build readiness as a sufficient daily-editor milestone. General editor owner now owns actual Origins editing-workflow inspection and the top one or two observed UI fixes: room navigation/framing, selection/overlap, movement/resize/layers, chest/tag inspection, Undo/Redo, dirty-state clarity and Save As/reopen. Use a disposable copy and actual UI evidence where available; source tests alone do not establish usability. Keep one ranked list of at most five issues in the existing Yaze manual checklist, not another broad report. Sprite owner aligns its current work with usable author/preview/export/reload interactions and coordinates shared UI ownership. Backend owner is available only for concrete defects from this pass. Goron owner supplies one short existing-plan editing scenario then stops. Patrol, shrine, finale and handheld tasks remain idle with completed packets preserved. No additional agents or model changes.

| Priority | Outcome | Next bounded work |
|---|---|---|
| Now: opening | Strong title and first playable chapter | Five history narration cards and practical scene assets; inspect existing Abyss route before proposing changes |
| Now: Power + Goron Mines | Existing dungeons give correct rewards and have clear, recoverable routes | S2 reward packet review; $77/$87 route/station manifest; qualify geometry concerns before editing |
| Parallel: main-path inventory | Know actual late-game gaps | Trace Courage reward and Fortress/volcano/final-room/ending dispatch against existing content |
| Next: final-act integration | Rescue Farore and finish the adventure | Assign concrete D7 victory/rescue and finale integration after current tracing; preserve existing bosses/rooms |
| Following RC improvements | Better guidance, character payoff, regions and spectacle | Quest hints/journal, Farore's disclosure, garrison/East Kalyxo, retained visions, Fortress and volcanic-chamber presentation |

Main-path blockers outrank optional polish. Narrative implementation stays title -> summons -> village -> experiment scene. Additional mapping can proceed independently. Do not treat unknown dungeon playability as proof it is broken.

## 3. Opening — accepted direction

Historical Yaze save-fix build: source `1677e0e7d90fe0bbad667c00ce6a1143ac5bcaed`, docs-only HEAD `55c181549`, executable SHA256 `12bbc3908644ef89e7bc5177d9d9ab8ca6507692a234658c450816da3ca518f3`. Subsequent rebuilds below supersede this binary identity. Exact candidate app location remains `/Users/scawful/src/hobby/yaze-worktrees/overworld-paint-regression-fixes/build/presets/mac-ai/bin/Debug/yaze.app`; current identity must come from its `combined-editor-candidate.json`. Guide: candidate `docs/internal/agents/editor-personal-use-handoff-2026-09-23.md`. Focused save tests: 42/42 writer/save-manager and 28/28 editor, zero skips; unrelated `RomTest.LoadFromFile` fixture-size failure excluded. Installed launcher/iPad builds unchanged. This is not daily-editor usability acceptance.

### Current Yaze UI integration status

Monitoring checkpoint `2026-09-24T03:26:54Z`: all nine assigned peer tasks are inactive (eight idle, Goron not loaded). Latest general-editor completion confirms the canonical consolidation below; no pending integration build or new result was found. Hourly monitoring is paused to conserve usage. Remaining work is explicitly open: combined native Origins editing/save-reopen acceptance, project/expanded-ROM checks, and the separate manifest-consumer review once Claude's diff is ready. No agent was restarted and no verification was rerun at this checkpoint.

**Current canonical consolidated build:** owner reports clean `codex/combined-editor-candidate`, app source `699c863265c8203c1f6505419fbcd151de4f1f0b`, docs-only HEAD `17b40b061`. Final app/CLI/unit/quick-editor build passed. Current executable SHA256 `c28d4e97e8cbe3ba98d1687ef057c914c1c877ed6943245c21bc5c8cdfe42378`; CLI SHA256 `ce1c78d6c3be6e2d7dd2c26812269d0d2bcc294ea9c611139dab2d29e19e528a`. This supersedes earlier binary identities below. Added SPC700 reset, drawer badge fit, Tile16 doctor correction and 13-file Tile16/graphics preview packet. Final focused checks: 99 preview/tracking/history, 62 welcome/theme and 17 drawer/SPC/doctor passed; suites overlap, so do not sum these counts. Theme test isolation was corrected in `d238e478e` after a synthetic UTF8-name fixture overwrote the real Rose Pine theme singleton. Earlier sprite/save test evidence remains separate.

Consolidation ledger: candidate `docs/internal/agents/worktree-consolidation-2026-09-23.md`; personal-use guide and binary provenance updated. Source-equivalent welcome/theme/sidebar branches were not redundantly merged. Dirty owner work, installed app/launcher, saved layouts, devices and source ROMs preserved. No build/CUA session active at completion. Full native Origins editing/save-reopen remains pending; older appearance may involve running-binary identity or saved layout, but neither is established as the cause. Hooks consumer review remains separate.

**User-directed worktree consolidation:** user reports older UI in some worktree builds and explicitly requests merging. General editor owner now owns consolidation of remaining relevant UI work into one canonical candidate, preserving modern intended layouts and user rulings rather than choosing by binary recency. Initial root inspection confirms main committed baseline `0f3855d6f` is an ancestor of combined `9342f089b`; additional UI source differences and dirty weekly-review drawer changes still require ownership review. Main has active dirty sprite/overworld/Tile16 work; do not overwrite, stash or reset it. Merge reviewed scoped changes, resolve conflicts deliberately, coordinate one build and record included/pending work. Check executable identity and persisted layout as possible causes of older UI. No worktree removal, installed-app update or push is implied. Overworld owner has been asked to identify newer owned work for integration.

Consolidation findings supersede initial branch-history guesses: welcome-polish files and theme assets/notices are byte-identical to the candidate, as are bundle-verifier files; sidebar/theme-key/UTF8 patches are already represented. Do not merge historical UI alternatives merely for ancestry. Owner reports actual additions: SPC700 reset `7b0d74012`, drawer badge fit `b5c7f34a7`, and removal of old Tile16 validation/zero-repair behavior `e3d5c34ed`. Build/check completion is pending. Current running executable and saved layout remain possible independent causes of old UI.

Tile16 preview owner delivered `/tmp/yaze-tile16-preview-followup-20260923.patch`, SHA256 `ac29e6d56b2d6dfcc992d87dc42d4abc50864b6f2c649038b72b103a541f0761`, 13 owned files, separate from prior overworld packet. Reports main app/quick-editor build, 99 passing tests and actual full-stamp hover on a copied ROM; includes mixed-map rectangle preview and graphics-group palette isolation/bounds fix. CUA/build ownership released. General integration owner is reviewing against the already-merged Tile16 validation correction; no combined-build acceptance inferred from main-worktree evidence.

**Latest completed combined candidate (supersedes build-in-progress notes below):** editor owner reports sprite integration `7e2f16590`, overworld integration/application source `ff0545893b9d6962e7a92d8ca6171d8d553acf95`, docs-only HEAD `9342f089b`, clean worktree. Built app, CLI and both relevant test targets. Combined sprite/project/dungeon-toolbar checks: 87/87; overworld/editor-save checks: 104/104; zero failures/skips. Final app executable SHA256 `d78e18265d61f19421033263ac0e2dc669cebf54f2339fd9b143b01a80e7cb98`; CLI SHA256 `0ad9205ffa4797f09912440967d045d33d6a4ffe9c100b6b5e566349d8cd5e67`. Paths remain the exact candidate location above. The earlier incomplete build registration was corrected and final build passed. Provenance/personal-use handoff updated by owner. Separate sprite and vanilla-overworld live checks do not establish combined Oracle editing/save acceptance. Native Origins workflow, expanded-map save/reopen and Tile16 multi-select preview follow-up remain open. No installed app, running session or shared ROM changed.

Toolchain coordination: Claude is authorized to extract shared source-parser helpers with byte-identical manifest verification and prepare a same-ROM protected-region comparison. Semantic hooks-list migration remains unapplied pending Yaze consumer review. Preserve fresh-emission requirements, explicit asar fallback and rejection of stale standalone hooks; no default switch or scanner deletion implied by this integration milestone.

- Dungeon commit `1e7c1a5ea`: persistent hexadecimal room entry (`000`–`127`, Enter to submit), explicit grid-navigation arrow descriptions, app rebuild and 11/11 toolbar tests per owner. These are source-confirmed discoverability improvements. Full Origins UI editing/save/reopen remains unverified: two same-bundle-ID applications caused unreliable native picker targeting, and bounded attempts stopped without ROM edits. Do not report automation routing as a proven Yaze defect.
- Sprite owner completed an actual two-frame workflow in its separate main-worktree build: different offsets/previews, Play/Stop, Undo/Redo, save/reopen and restart. Fixed preview/tilesheet publication, selection alignment, independent metadata scrolling, sprite-panel docking, fallback names and frame-status contrast. 70 tests/11 suites passed separately. Numeric-input undo remains intermediate-value granular; playback timing precision, palette, catalog/export, project-binding reload and in-game acceptance remain open.
- Sprite source identity: main worktree HEAD `0f3855d6f2df4d8cad409ec10a23ef98880d5676` plus dirty owned source recorded in `/tmp/yaze-sprite-two-frame-source-identity.json`; separate executable SHA256 `6a0cbd9eeba4536ce06408d4d6f84d8f487cd85614a539923f8472c19913da67`. Do not attribute that evidence to the combined candidate automatically.
- General editor owner verified all 43 incoming source hashes and is integrating only the owned sprite changes. Shared project/build registration overlaps resolved while retaining candidate carriage-return validation and dungeon registrations; unrelated patrol test excluded. Current live status: combined build in progress, focused project/sprite/toolbar checks next. No completed integrated binary or integrated UI acceptance claimed yet. Sprite owner is idle; other Oracle packets remain parked.
- Monitoring requested by user: hourly thread follow-up, meaningful changes only, update this document in place, avoid duplicate builds/audits or idle-agent wakeups. Pause monitoring when all assigned work is idle with no pending integration result.

### Title/attract history

Five short narrated scenes: Kalyxo and its peoples -> crystal/Mirror discovery -> Hyrule arrives -> benefits and restrictions of occupation -> neglect and unresolved danger. Preserve the island's identity. Farore's private appeal and the prison's contents are later revelations. Exact narration is still draft.

### Implementation sequence

1. Reusable cutscene framework and title sequence, beginning with the existing-scene compatibility fixture.
2. Move "Accept our quest, hero" into the falling/spinning Oracle-style arrival leading to bed wake-up.
3. Village Stalfos pursuit: approach from left, blocked east exit, escape toward hole, meaningful NPC access. Approved contact target: half heart, ordinary recoil/invulnerability, brief guard recovery; no capture or forced restart. Full search remains in the design.
4. New-file experiment cinematic last: Zora uses Mirror by Happy Mask Salesman map river -> Abyss -> enemy approaches -> return with Stalfos following -> Farore pleads -> divine summons. No bespoke crystal apparatus required. This is a later crossing, not the historical first discovery.

All new runtime features default off behind experiment flags. No feature is declared implemented by this plan. A complete visual cutscene editor is not required.

### Existing playable opening: improve in place

Accepted follow-up: modestly deepen Origins' existing Minish puzzle, emphasize Moon Pearl pickup/NES-to-GBC transformation, and correct post-Pearl reactions. On first post-Pearl exit, stage a brief mysterious exterior disturbance: ambience drop, rumble/mountain shake, existing animals flee, then quiet. Lighting/overlay is optional. Preserve the animals' later L4 Master Sword scene. No visible attacker, explanatory dialogue or new seal-breaking lore. Exact expansion layout, framing, trigger storage and implementation remain open.


Preserve Abyss -> Shrine of Origins -> Eon Owl -> sword/shield -> return to Kalyxo. Existing ROM messages $35/$36 already provide Impa's explanation, Pearl objective and Maku return direction. $E6 already points to the sword with forgotten-dream imagery and a hint that blades cannot sever every bond. Owl proximity/fly-away and equipment collectible code exist.

Current [map/dialogue review](Reviews/abyss_origins_review_2026-09-23.md) identifies Origins as entrance $76 / room $05, the existing multi-chamber Minish/Pearl setup, and post-Pearl dialogue mismatches with the user-confirmed NES Link -> GBC Link presentation.

Remaining review: exact current Origins route and transformation order, equipment receipt/shield effect, fixed return portal destination, normal traversal and pacing. Map labels/parent maps differ in old docs; do not relocate content based on that alone. Focus proposed changes on readability and atmosphere, not new mandatory tutorials. See [existing-content review](Reviews/opening_existing_content_and_agent_steering_2026-09-23.md).

## 4. Plot and finale

The story moves from Farore's capture and island exploration, through conflicting Zora/Goron/Hylian accounts, to Farore's rescue and Kydrog's healing. Preserve the Meadow Blade connection, failed-revival residue, Kydreeok as Abyss form, Song of Healing resolution and custom wordless coda. Rejected Ganondorf-origin/two-villain drafts are not implementation requirements.

D7 should pay off the rescue and establish the next objective. Farore needs an active post-rescue role. Her responsibility for Hyrule's intervention should have a meaningful reveal; exact placement remains proposed. Fortress and the volcanic final chamber need a dedicated presentation pass around their actual existing layout: approach, chamber reveal, combat transitions, healing, coda and aftermath. Do not invent a new route until current connections are traced.

Current inventory reports Kydrog in $A4, Dark Link in $0D/$30 and Kydreeok in $00. D7 rescue scaffold exists but is disabled. Kydreeok has combat/head regrowth/death; healing finisher is not present in inspected code. Current patched ROM still bypasses the ending. Actual final-route connectivity and normal completions remain unverified. See [RC inventory](../../.context/scratchpad/handoffs/rc_inventory_2026-09-23/README.md).

### Creative discussion queue — one at a time

- First: after verifying existing pacing, what single fact must the player understand when leaving the opening? Current working objective: Farore needs help; the Abyss is dangerous; seek Maku Tree.
- When scripting the experiment: why does this crossing give Kydrog his opportunity? No latest assistant suggestion is settled canon.
- Later: timing of Farore's power entering the blade; occupation/prison chronology; Twinrova's relationship to Kydrog's aims.
- At finale staging: Farore disclosure placement, healing/farewell presentation and volcanic-chamber effects.

No need to answer all of these before technical work continues.

## 5. Owners and actionable assignments

Role labels below are not renamed app tasks. IDs route messages. No additional agents requested.

| Owner / thread ID | Next deliverable | Boundaries |
|---|---|---|
| Opening (this thread) 01a0d06d-ee1d-7893-be24-c52b3a73c09c | Existing Abyss route review + title cards; shared cutscene/hook integration | Own master plan, global opening flags/hooks and story coordination |
| Goron 01a0d089-7dad-7110-b72e-e761e876cd03 | Exact $87 north/$77 south access and station/route packet | Preserve current cart mechanics and T0-T3/T10; isolated room edits only after layout review |
| Power 01a0d0e8-fc71-7aa0-8fa2-713854fb89f7 | Reviewed isolated S2 reward correction and pickup tests | No boss addition or speculative geometry redesign; proposed patch remains unapplied |
| Patrol 01a0d0e9-2568-7b83-a220-9c973270f093 | Bounded moving-guard compatibility audit using Yaze handoff, then behavior integration | Preserve $3F blockers and probe children; no invented ID/cache or shared-hook mutation |
| Yaze sprites 01a0d077-216b-7021-98a7-9f88e1062460 | Resolve concrete single-context-actor binding with patrol owner | Own catalog/transport; general authoring backend is independent of patrol readiness |
| Yaze editing 01a0cb50-a603-7763-8964-a27e9b7aa74a | Correct stale header-clearing tests; retain editor/UI and later room-specific qualification | Preserve raw IDs and label provenance; no unsafe automatic header clearing; coordinate backend boundary |
| Yaze overworld UX 01a0d136-c963-7f10-9c72-22fb64241140 | Current-map tracking fixes and overworld editing-flow review against Hyrule Magic/ZScream | User explicitly chose follow cursor when unpinned; own overworld flow, coordinate shared source/build/CUA with general editor |
| Yaze backend 01a0d11f-b60c-7c13-bf61-2516f86d5d9f | Audit replacement-aware save-capacity preview; smallest implementation packet | Reuse existing allocator/save plan; no duplicate editor work or Oracle ROM edits |
| Claude Python migration (external owner) | Tooling extraction and authoritative command/destination handoff | Destination not yet confirmed here; other owners must not move, restore or recreate migrated scripts |
| RC integration 01a0a0af-f246-77c3-a816-bf77cd85ccf4 | Courage reward + exact final-route/ending dispatch packet | Read-only until implementation assignment; do not duplicate shrine or boss changes |
| Handheld UI 01a0d06d-39f7-7982-889f-ee6335c64334 | Current scope/status and bounded UI handoff | Supporting work, not opening dependency; no implicit device deployment/save changes |
| Scawful | Creative choices; garrison/East Kalyxo mapping | Reserve authored maps; opening must not depend on completing eastern expansion |

### Important live findings and handoffs

- New overworld UX owner is active. Direct user ruling in that thread: map properties follow the cursor whenever unpinned. Owner reports work on tracking across editing modes, middle-drag panning without unintended pinning, active-game-state sprite labels and parent-area property readback. These are in-progress owner reports, not completed verification. Broader overworld flow review is separately authorized by the user. General editor and overworld owner have been connected for exact source/build integration and exclusive UI input; do not override the user's hover-tracking choice with older click-only assumptions. Hourly monitoring includes this owner.
- Overworld completion supersedes the preceding in-progress status: owner reports scoped patch `/tmp/yaze-overworld-flow-20260923.patch`, identity/path manifest `/tmp/yaze-overworld-flow-20260923-manifest.txt`, main baseline `0f3855d6f2df4d8cad409ec10a23ef98880d5676`, no sprite/shared-file changes. App and quick editor target built; 76/76 focused tests including nine new regressions passed. Actual UI on a copied vanilla ROM verified hover `00`/`01`, pin/unpin, parent readback, tracking after Brush/Fill, middle-click without pinning, and row wrapping at two sizes. Save/reload, Oracle expanded-ROM behavior, CI and gameplay remain unqualified. Review: Yaze main `docs/internal/plans/overworld-flow-review-2026-09-23.md`. General editor owns scoped integration after sprite merge; combined binary acceptance remains pending. CUA released and existing sessions preserved.

- Power owner traced $3A to Wolf Mask and $39 to Power in current Oracle receipt code. S2 proposal changes one chest byte and its forced-output source patch. S1's $39 similarly warrants Wisdom correction review; S3 Courage mapping is $37. Runtime pickup remains unverified. See [reward packet](Plans/shrine_power_reward_review_packet_2026-09-23.md).
- Yaze candidate fixes receipt labels with item_name_source. Vanilla fallback is not Oracle handler evidence. Installed nightly is unchanged; exact candidate binary is recorded in owner packets.
- Yaze sprite handoff recommends auditing moving guards $41/$42/$43, preserving probe dispatch. It proposes a family-local post-property-load Prep adapter and one contextual authored actor using existing Y/X/ID data. This is an audit direction, not an allocated member, identity cache or approved runtime binding. Dynamic patrol spawning can remain unsupported in the first contract. The source handoff is docs/internal/plans/stalfos-patrol-binding-handoff-2026-09-23.md under Yaze.
- Yaze sprite owner's cross-thread delivery was blocked by tool approval policy. Opening owner read the local handoff and relays it; do not mistake failed delivery for missing work.

### Latest Yaze qualification update

Owner reports commit `dfb2e1c88`: 52 read-only CLI calls covering 26 Shrine/Goron rooms on both recorded ROMs; six staircase candidates resolve under the vanilla collision model, ten are blocked by custom collision. All remain `runtime_qualified=false`. Goron door records match the audit, but connected-graph outer-door eligibility remains incomplete. 106 focused tests and app/CLI/unit builds passed per owner report. Candidate command supports `--include-staircase-resolution`; installed nightly unchanged. Evidence: Yaze worktree `docs/internal/agents/shrine-goron-staircase-qualification-2026-09-23.md` and `.json`. Relayed to Shrine, Goron and RC owners.

RC tooling caution from source review: `VersionManager::CreateSnapshot` stages all changes and can report success after ROM backup failure; do not invoke it on concurrent dirty work. Existing `SaveRomAs` supports source preservation/target backups; `Save Snapshot As` is layout-only. A named receipt after successful existing Save As is a proposed bounded improvement, not implemented release tooling.

### Origins authoring-readiness update

Yaze editor owner reports against candidate `dfb2e1c88`: extending existing room `$05` does not require new room IDs or completion of all dungeon features. Selection, layers, doors/raw tags, undo, coupled chest/reward edits and manifest-bounded stream relocation exist in source with focused synthetic coverage. A concrete layout and room-specific save/reopen qualification remain necessary. The empty southwest quadrant is not an approved or collision-qualified expansion site.

The new backend owner is auditing a read-only capacity preview that reuses `PlanDungeonStreamWrites`: draft byte growth, shared source, authorized relocation, pointer changes or precise blocked reason. Editor/UI integration remains with the existing editor owner. Current dungeon room count is 296; expanded entrance tables and stream relocation do not establish support for additional room IDs. No additional agent is needed for this slice.

The owner ran 145 focused room-edit/selection/allocator tests: 143 passed, two `ConnectedClearStaleIsOneActionAfterEarlierPropertyEdit/{0,1}` cases failed because they still expect automatic header clearing. The editor owner is assigned to assert metadata preservation instead. This is separate from the earlier 106 passing staircase/CLI tests; the candidate is not fully qualified.

Tag discrepancy pending Oracle source verification: owner traces raw tag `$36` through vanilla dispatch `$01C2E9` to `$01CC10`, patched by Oracle to `RoomTag_MinishShutterDoor`. `Docs/Technical/Room_Tag_Slots.md` reportedly says `$37`. Preserve room `$05` tag `$36`; inspect any dispatch-table patches before correcting the documentation. Runtime Minish shutter behavior, effective collision and room-specific preservation of Pearl receipt `$1F` / entrance `$76` remain unverified. No ROM changes were made for this readiness review.

### Agent steering refresh — September 23

Checked all eight other Oracle/Yaze/handheld Codex tasks and their available handoffs. Some completed thread turns expose no messages, so local packets supply their findings. All steering messages were delivered; completion of new assignments is not implied.

- **Yaze editor:** owner reports test-only commit `bf471e33b`, with 145/145 room-edit/selection/allocator tests passing after correcting the two stale clearing expectations. Automatic clearing remains disabled. Candidate runtime binary is unchanged. Keep this owner available for backend review and later approved-layout save/reopen qualification.
- **Yaze backend:** existing room-transfer preview already exercises production serializers on a detached ROM. Do not duplicate a planner. Owner is investigating a synthetic-file reproduction of predictable temporary-file symlink/hardlink corruption in `SaveToFile`; editor confirms backend ownership of `rom.cc` and focused save tests. Prioritize the proven save defect over new preview diagnostics; await the bounded packet and validation.
- **Yaze sprites + patrol:** contextual `$42` source contract accepted with probe exclusion, validated doubled-index authored key, loaded-area scope, loading-cell uniqueness across all actors, selected-Prep bypass and expired-context cleanup. Sprite owner now specifies decoder/validator contract; patrol owner completes RAM/moving-art compatibility and recommends an exact intro predicate and placement. Root still owns eventual shared bridges. No runtime binding or ROM placement approved by this refresh.
- **Goron + Power:** existing exact route and reward packets are ready for targeted review. Owners asked to close with one recommendation and outstanding checks, without more broad audits or implementation. S2 patch remains unapplied; Goron layout remains a proposal.
- **RC integration:** finish the readable S3/finale trace from `.context/scratchpad/handoffs/rc_final_trace_2026-09-23/` evidence; identify proven edges, unresolved transitions and smallest integration packet. D7 rescue remains a subsequent assignment, not another active implementation lane.
- **Handheld:** local handoff supersedes earlier permissions-blocked/main-checkout assessment. `mesen2-oos-performance-ui` has a built, uninstalled `0.1.34-menu` candidate; controller/device acceptance remains pending. Owner now coordinates the host build-root/client-root split, preserving the menu candidate and external Python migration ownership. See `.context/scratchpad/handoffs/rg353p_controller_menu_2026-09-23.md` and `rg353p_toolbox_check_2026-09-23.md`.
- **Claude migration:** not exposed as a Codex task, so no direct status/control claim. Current local handoff identifies sibling `oos-rg353p` for handheld tooling, `mesen2-oos/tools/oos_client` for protocol client and Oracle compatibility shims. Backend owner received these references; verify command dispatch before relying on them. No script relocation assigned to other agents.

No additional agents created. Opening owner retains title-first framework work and the next Origins puzzle/animal-event discussion. This coordination pass changed planning only; no ROM, save or device action occurred.

Handheld follow-up: owner confirms current migration roots from source and proposes toolbox-only build selection precedence `MESEN2_ANDROID_ROOT` > legacy `MESEN2_OOS_ROOT` > sibling default, without changing Python shims. Claude coordination endpoint remains unknown. Current feature-worktree APK reportedly hashes `c8abc0caa6c775f300abb0ec30d27ce7edb6206459d82bddaa751b22e73089c3`, differing from recorded tested artifact `c2b541a06c0a1b5287ae891cd446ef259f4535a7c55299a54839ca154d78255f`. Owner assigned read-only provenance reconciliation; do not transfer prior build/test identity to changed bytes or deploy either artifact through this planning task.

## 6. Integration and acceptance

Finale trace correction from RC owner: `.context/scratchpad/handoffs/rc_final_trace_2026-09-23/README.md` supersedes preliminary ending interpretation. `$0E9889` selects submode `$20`, whose vector reaches credits initialization; it skips vignettes, not credits. Existing source/table chain runs Kydreeok cleanup -> tag `$3D` -> special north passage -> module `$19` -> credits module `$1A`. Do not remove that patch to reconnect an ending already connected in source. Ordinary gameplay remains unverified.

Fortress victory uses room `$0D` tag `$38` and module `$18`; later transport-slot loading selects actual destination OW `$40`, superseding the earlier `$5B` write. Route OW `$40` -> `$57` and gate `$7EF2DB & $20` need qualification. OW `$57` holes -> entrance `$7B` -> room `$00` are direct table edges. S3 room `$07` already has chest receipt `$37` granting Courage; vanilla `$BD` boss death spawns a heart and tag `$08` operates shutters. No new reward or Vaati implementation is justified by this trace. Next packet is isolated ordinary victory/arrival/final-route/credits qualification, with repairs only for demonstrated failures. No runtime check occurred in the read-only trace.

Limit concurrent implementation to roughly four lanes; audits and reviews can overlap. One owner per shared hook/registration/flag region and per ROM editing target. Separate source worktrees and isolated base-ROM copies; serially integrate structured room/map changes with before/after identities and range manifests. Never merge binary ROMs as source patches or overwrite unrelated dirty work.

Use existing overlap/z3dk and focused build checks, including feature-off baseline and relevant enabled configurations. Distinguish source tests, synthetic fixtures, real-ROM readback, emulator behavior, ordinary traversal/save evidence and physical-device acceptance. Optional content can change across RCs; revalidate affected main-path behavior on each selected artifact.

No new backup manager, sprite platform, broad progression rewrite or mass dialogue migration is needed to begin. Preserve authoritative dialogue sources: vanilla base ROM, expanded JSON/generated ASM; messages.org is a review snapshot.

## 7. Detailed packets

- [Opening storyboard and order](Plans/opening_and_rc_development_2026-09-23.md)
- [Agent plan and dispatch prompts](Plans/oracle_yaze_rc_agent_plan_2026-09-23.md)
- [Cutscene framework](Plans/cutscene_framework_spec.md)
- [Experiment validation](Plans/intro_experiment_validation.md)
- [Patrol packet](Reviews/stalfos_patrol_packet_2026-09-23.md)
- [Goron first slice](Plans/goron_77_87_rc_packet_2026-09-23.md)
- [Power audit](Plans/shrine_of_power_rc_audit_2026-09-23.md)

Update this master for priority/ownership changes; update the canon sheet only for accepted creative rulings. Owners keep evidence in their own packets and return concise outcomes/next dependencies.

## Next opening packet — Origins disturbance and puzzle

Technical work here: trace existing animal actors and sword-event conditions on parent map $40, their positions relative to Origins' exit, and existing shake/lighting/sound helpers. Determine whether the animals can be visible from the exit's camera; do not assume same large map means same screen. Specify a minimal reusable scene, one-shot trigger and normal re-entry/save behavior, preserving the L4 event. Source inspection precedes new graphics, RAM allocation or ROM edits. Keep the title-first implementation order.

Next discussion with scawful: what one additional Minish challenge should Origins develop before the Pearl? Inspect actual traversal first; use the current pots, small passages and shutter. Choose one puzzle goal, then produce a small layout sketch. No boss or new item is required. Defer disturbance cause, broader chronology and finale spectacle decisions until their implementation packets need them.

## Claude (cloud) update — September 25

- Origins question above: the user chose puzzle A only. No Pearl presentation, exit disturbance or new Pearl text for now.
- Applied in source and the edit base (`Roms/oos168.sfc` now `bf4529a2…`; the old base is `Roms/oos168.pre_rc_intro_origins_20260925.sfc`):
  - S2 (`$39`) and S1 (`$38`) chest fixes, lava-corner tile types, the Roc's Feather patch and the collision cleanup (September 24).
  - Goron R1–R4: switch-track guard, King Dodongo 40 HP + phase clamp, room `$B8` pit damage, `$87` T3 north stop (September 25). The `$77/$87` walking transfer is next.
  - Origins puzzle A: rails and `$65` gap in room `$05`, new pot, NE-only shutter check behind `!ENABLE_ORIGINS_MINISH_PUZZLE` (default off).
  - Opening: `Core/Cutscene/opening.asm` (arrival: fall + "Accept our quest" on black, then iris and wake-up) and the 5-card island-history attract, behind `!ENABLE_CUTSCENE_FRAMEWORK`, `!ENABLE_ORACLE_ARRIVAL_SEQUENCE` and `!ENABLE_CUSTOM_ATTRACT_SEQUENCE` (default off). The narration is a draft.
- Test build: `Roms/TestBuilds/rc-intro-origins-goron-2026-09-25/` (flags on, `2ceeacff…`, with `playtest.md`). Flags off, the same source gives `41cd0cea…` in the cloud; the Mac build is not checked yet.
- The yaze headless emulator ran the attract, the arrival, Origins puzzle A and D6 room checks. Controls on the old build reproduce the `$77` hang, the `$B8` fall to room `$00` and phase 6 at 96 HP. Mesen2 and hardware play are still to do.
- Two yaze emulator bugs were found and fixed on yaze branch `claude/emu-io-fixes` (`d29389036`, not pushed): 8-bit `ORA` set Z from the high byte of A (attract text closed by itself), and WRIO reset to 0, so the iris wipe never ended.
