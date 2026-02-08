# Oracle of Secrets Debugging Status Report

Date: 2026-01-23

## Snapshot
- As of Jan 23, 2026, Oracle of Secrets is Alpha; debugging focus remains water collision + probe detection, with Lost Woods camera offset low priority. (STATUS.md)
- Water collision fix (Jan 21) is applied and room-load hook re-enabled, but persistence verification is still pending; prior test notes (Jan 22) show only partial swim coverage and water persistence not retested. (Docs/Testing/oos168x_test_status.md)
- Probe logic attempt on Jan 23 was reverted after a wrong assumption (vanilla probes set $0D80,X, not SprTimerD); next step is vanilla research around $05C15D (FireProbe) and guard states. (~/.context/projects/oracle-of-secrets/scratchpad/agent_handoff.md)
- Oracle AI tooling refresh landed: test runner defaults to socket backend, capture helper unified, gateway actions expanded (build/symbols/tests/health/open dirs). (~/.context/projects/oracle-of-secrets/scratchpad/debugging_session_20260123_oracle_ai.md)
- New tests exist for Lost Woods camera + overworld basic flows. (tests/lost_woods_camera.json, tests/overworld_basic.json)

## Mesen2 Fork
- Fork head is "Socket: validate INPUT parameters" on master. (/Users/scawful/src/hobby/mesen2-oos)
- Local, uncommitted UI additions introduce an "Oracle AI" menu with Build/Symbols/Testing/Yaze/Gateway/AFS/LLM actions, plus OracleAgentLauncher utility; Mesen2 app rebuild needed to see these. (UI/ViewModels/MainMenuViewModel.cs, UI/Utilities/OracleAgentLauncher.cs)
- Input injection and warp reliability remain open in the socket client; planned fix path mentions adding frame counters in Mesen2 Debugger -> SocketServer -> bridge/client. (~/.context/projects/oracle-of-secrets/scratchpad/agent_handoff.md)

## Sheets Data
- New CSVs in Docs/Sheets/ (timestamps Jan 23, 2026): Rooms/Entrances, Dungeons, Spritesets, Overworld GFX, Overworld Spr, Custom Sprites, Sheet8.
- Room names, overworld areas, entrance info, and dungeon metadata are already embedded in scripts/mesen2_client_lib/constants.py and referenced in ~/.context/projects/oracle-of-secrets/knowledge/oracle_quick_reference.md.
- No automated import pipeline found; remaining sheets (spritesets/overworld gfx & spr/custom sprites/sheet8) appear staged for future tooling/docs updates.

## Open Work
- WaterGate persistence verification still pending (Room 0x27/0x25, re-entry + save/reload) using scripts/mesen_water_debug.lua; no results logged (scratchpad test_results.md does not exist yet).
- Populate .mss state library referenced by Docs/Testing/save_state_library.json and run tests/*.json via updated test runner/gateway.
- Cross-emulator verification (Mesen2 vs yaze) and follow-up on menu GFX regressions listed in Docs/Testing/oos168x_test_status.md.
