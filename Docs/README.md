# Oracle of Secrets docs

Only docs a person edits or the code depends on stay in git. Everything else (agent plans, reviews,
evidence, debugging guides, status reports) lives in the private AFS context
`~/.context/projects/oracle-of-secrets/`. Docs removed on 2026-10-06 keep their old paths under
`scratchpad/archive/repo-slim-2026-10-06/repo/`.

| Path | What it is |
|---|---|
| `Technical/` | Contracts the code depends on: memory map, flag ledger, table formats, inventories |
| `World/` | Dungeon, overworld, lore, NPC and quest references |
| `Dev/Planning/*.json` | yaze project registry data (labels, rooms, story events) |
| `schemas/` | JSON schema for dungeon annotations |
Start with `CURRENT_PLOT.md`, then `RIDOYIE_WRITER_PACKET.md` and
`YAZE_DIALOGUE_GUIDE.md`. These reconcile Lyra Sea shrines, Sky D8, the Abyss
story role, fixed Farore meetings and the planned Lupo/Fortress swap. World
registry/map snapshots remain implementation references, not relocation proof.
