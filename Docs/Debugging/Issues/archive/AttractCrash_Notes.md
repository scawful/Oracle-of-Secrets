# Attract Crash Notes

## Summary (2026-01-22)

During the intro/attract sequence, the game crashes after transitioning out of the attract state. Logging captured a transition from Mode `0x14` (Attract) into an invalid-looking `0x34` state with `indoors` set to `0x10`.

### Last observed transitions (from `attract_crash.jsonl`)
- Frame ~3270: `MODE=0x14` `SUB=0x00` `INDOORS=0x00` `ROOM=0x00`
- Frame ~5952: `MODE=0x14` `SUB=0x00` `INDOORS=0x01` `ROOM=0x51`
- Frame ~5960: `MODE=0x34` `SUB=0x02` `INDOORS=0x10` `ROOM=0x34`

`MODE=0x34` and `INDOORS=0x10` look corrupt (expected `MODE` in 0x00-0x1B and `INDOORS` 0x00/0x01).

## Next steps

1) Enable write tracing for core state variables to find the exact writer:
```
./scripts/mesen_cli.sh trace start ~/Documents/Mesen2/bridge/logs/write_trace.jsonl
```

2) Reproduce the crash and inspect `write_trace.jsonl` for the last write to:
`$7E0010` (MODE), `$7E0011` (SUBMODE), `$7E001B` (INDOORS), `$7E00A0` (ROOMID).

3) Set debugger breakpoints on the writer once identified.

## Notes
- Save-state load in this area may be unstable; prefer letting the attract sequence run naturally.
