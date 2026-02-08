# SPC / Savestate Regression Plan (Mesen2-OOS + ROM)

**Goal:** Prevent B010-style softlocks by exercising SPC state, APUIO handshakes, and savestate load/resume across both ROM and emulator layers.

## Test matrix
| Scope | Test | Pass criteria |
|-------|------|---------------|
| ROM instrumentation | Handshake log written to WRAM on every music bank load (pre/post poll) | Log shows transition out of poll; no repeated 0x0000 |
| Emulator regression | Load slot 1 → run 600 frames → frame counter increments; APUIO changes over time | Automated test exits 0 |
| Color/overlay | After savestate + idle in house/Spotlight, $9A/$1D cleared; no persistent yellow/green tint | Overlay/color registers cleared to 0 when leaving |
| Static (z3dk) | Scan for unbounded loops touching $2140-$2143 | No unbounded loops or all have timeout |
| Dynamic (planned, z3dk+mesen2) | Trace CPU+SPC around savestate load; SPC runs at least one instruction within 2 frames | Trace shows SPC PC advance after load |
| SPC logging (ROM) | $7E0730-$7E0736 reflect handshake state (0x10 entry, 0x20 success, 0xFF timeout), magic, APUIO, counter | State transitions to 0x20; counter non-zero |

## How to run
1) **Automated savestate regression (emulator):**
```
MESEN_APP=/Users/scawful/src/hobby/mesen2-oos/bin/osx-arm64/Release/osx-arm64/publish/Mesen2\ OOS.app \
MESEN2_SOCKET_PATH=/tmp/mesen2-test.sock \
# python3 scripts/mesen2_client.py test-hypothesis --headless --slot 1 --frames 600
# lightweight quick check
# MESEN2_SOCKET_PATH=/tmp/mesen2-test.sock python3 scripts/mesen2_client.py smart-save 1
```
(Integrate this into mesen2-oos test suite once stable.)

2) **Static scan (z3dk):**
```
cd ../z3dk
./build/src/z3analyze --rom ../hobby/oracle-of-secrets/Roms/oos168x.sfc --scan apu-handshake --report ../hobby/oracle-of-secrets/Docs/Debugging/Issues/B010_static_report.txt
```
(Command placeholder—update when the new z3dk passes land.)

3) **Dynamic trace (planned):**
- Enable z3dk-mesen2 instrumentation to capture synchronized CPU+SPC traces on savestate load.
- Compare pre/post-load traces for SPC PC advance and APUIO writes.

4) **Overlay/tint check:**
```
MESEN2_SOCKET_PATH=... python3 scripts/mesen2_client.py diagnostics --json \
  && python3 scripts/mesen2_client.py watch --json
```
Verify $9A/$1D and overlay ID return to 0/FF when leaving the house/Spotlight.

## Agent guidance
- Always record ROM CRC (current: C4E2E26E) and emulator build path.  
- Do not assume prior fixes; treat B010 as open.  
- Keep new test artifacts in `Docs/Debugging/Issues/B010_*` or `Docs/Debugging/` with dates.  
- Update this plan when z3dk dynamic hooks ship or when new automation is added.
