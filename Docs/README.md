# Oracle of Secrets docs

Only docs a person edits or the code depends on stay in git. Everything else (agent plans, reviews,
evidence, debugging guides, status reports) lives in the private AFS context
`~/.context/projects/oracle-of-secrets/`. Docs removed on 2026-10-06 keep their old paths under
`scratchpad/archive/repo-slim-2026-10-06/repo/`.

| Path | What it is |
|---|---|
| `oracle.org` | Task tracker |
| `Planning/Status/decisions.org` | scawful's design and story rulings (DECIDED / OPEN) |
| `Planning/story_canon_beat_sheet.md` | Story canon |
| `Planning/Reviews/approved_dialogue_rewrites_2026-09-26.md` | Approved dialogue text |
| `Technical/` | Contracts the code depends on: memory map, flag ledger, table formats, inventories |
| `World/` | Dungeon, overworld, lore, NPC and quest references |
| `Dev/Planning/*.json` | yaze project registry data (labels, rooms, story events) |
| `schemas/` | JSON schema for dungeon annotations |
