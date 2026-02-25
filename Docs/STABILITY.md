# Technical Stability Reference

This document serves as the single source of truth for core technical stability issues in Oracle of Secrets, including PPU register management, APUIO handshakes, and softlock prevention.

---

## 1. PPU Register Management (Color Glitches)

### The "Yellow-Green Tint" / "Flash to Day" Bug
**Symptoms:** Screen tints yellow/green after loading a state or idling in areas like the Link's House spotlight. Transitions sometimes "flash" to a bright daytime palette temporarily.

**Root Cause:** Incomplete clearing of Color Math registers during area transitions. Specifically, the game was clearing the Subscreen Enable register ($1D) but leaving the **Color Math Control register ($9A)** and **Fixed Color mirrors ($9C/$9D)** set to stale values from previous custom overlays (Rain, Storms, etc.).

**Implementation Fix:**
In `Overworld/ZSCustomOverworld.asm`, the routine `Overworld_LoadBGColorAndSubscreenOverlay` now explicitly clears these registers when the Overlay ID is `$FF`:
```asm
SEP #$30
STZ.b $9A ; CGADDSUB mirror
STZ.b $9C ; COLDATA L mirror
STZ.b $9D ; COLDATA H mirror
```

---

## 2. Audio Processing Unit (APUIO) Handshakes

### B010: APU Softlocks
**Symptoms:** The game hangs indefinitely during music bank loads or after loading certain savestates.

**Root Cause:** Unbounded polling loops waiting for a handshake from the SPC700 ($2140-$2143). If the SPC state is desynced or unresponsive, the CPU spins forever.

**Current Status (2026-02-22):**
- The temporary timeout-hook experiment has been removed from `Core/patches.asm`.
- Do not treat feature-flag toggles as a mitigation path for this issue.
- Active work is root-cause debugging of song-bank handshake failures and transition flow.

**Diagnostics:**
Use `scripts/repro_blackout_transition.py --report-out <path>` to capture the final
transition/APUIO snapshot for each repro run. No persistent WRAM logging is enabled by
default in this path.

---

## 3. Emulator Interop & State Integrity

### Input Overrides vs. Direct Sets
Internal agents and automated tests must use `setInputOverrides()` via the Mesen2 Socket API instead of direct memory writes to input registers when possible. Direct sets can cause logic desyncs if they occur mid-frame.

### Savestate Alignment
Always verify that the `library` savestates match the current ROM version. Use `mesen2_client.py lib-verify-all` to ensure the baseline states are still valid after major ASM changes.
