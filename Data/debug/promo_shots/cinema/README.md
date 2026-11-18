# Cinema shot library

Authored compositions (not raw warp doorways). Schema = yaze cutscene v1 +
director extensions (`label`, `checkpoint`, `beat`, `extent`, `savestate`).

## Story gear
Each shot should set `checkpoint` to a `Data/debug/checkpoints.json` id so
`StageResolver` applies that beat’s items/flags before travel.

## Lyra / special OW (`$80+`)
- Require `extent` and a private `savestate` path (`.mss`).
- Exit-table `warp-area` cannot load these maps.
- Example: [lyra_sea_coast.json](lyra_sea_coast.json) — fill `savestate` then:

```bash
bash Scripts/Mesen2/oos_director.sh --socket /tmp/mesen2-<instance>.sock \
  capture --shots Data/debug/promo_shots/cinema/lyra_sea_coast.json \
  --out Roms/telemetry/promo/lyra01 --hud-off --gif --no-rom
```
