# Overworld Softlock — Less Cerebral Options

Date: 2026-01-29  
Purpose: Concrete, hands-on ways to move forward without more theory.

Pick one and run with it. No scripts required unless noted.

---

## 1. Play and write down what breaks

Play normally (or a fixed route). When it softlocks, note: “Did X, then Y, then black screen.” Keep a short repro log and a “last good” savestate. Use that as the real-world repro for sharing or bisect.

---

## 2. One small fix, then test

Pick a single low-risk change (e.g. fix JumpTableLocal once for width, or one NMI SP clamp). Ship it, play the same route, and see if softlocks drop. Less “prove root cause,” more “try a fix and observe.”

---

## 3. One golden path

Define one path that must never softlock (e.g. start → overworld → first dungeon door). Make that the only regression test for a while. Ignore the rest until that path is solid.

---

## 4. On-screen debug

Show SP (or one or two key values) on screen during play. When it softlocks, you see the last value without attaching a debugger. Helps narrow “when” and “where” with minimal setup.

**How to add a minimal on-screen display:**

- **Option A (HUD hook):** In the HUD draw path, read the stack pointer and the NMI SP save location `$7E1F0A`. Write both to a fixed WRAM word (e.g. `$7E0F80` / `$7E0F82`) or a 2–4 byte debug region. Use an existing debug tile routine (hex digits to tilemap) to display that word. If the codebase has a debug overlay (search for "debug", "hex", "draw" in Menu or Util), add one line to copy SP (and optionally `$7E1F0A`) into that overlay's source address.
- **Option B (NMI hook):** In NMI, after the vanilla SP save/restore, read SP and `$7E1F0A` and STA to a debug WRAM region; have a separate draw pass or existing debug layer display those bytes. Toggle via a define (e.g. `!SHOW_SP_DEBUG = 1`) so you can turn it off for release.
- **Where to look:** `Menu/` for HUD hooks, `Core/` or `Util/` for debug helpers; `hooks.json` for HUD_Update or NMI-related hooks.

---

## 5. Savestate checklist

Keep a small set of “known good” savestates (after boot, after load, after key events). On softlock, reload the last good one and trim the repro to the shortest sequence. Good for sharing and for bisect later.

---

## 6. Ask the community

Post a minimal repro (what you did + savestate or ROM + “black screen here”) on romhacking.net or a Discord. Someone may have seen the same pattern or know a tool that helps.

---

## 7. Compare to a known-good build

If you have an older Oracle-of-Secrets or vanilla build that doesn’t softlock on the same route, diff or high-level compare (e.g. what modules/areas changed). Less “theory of stack,” more “what changed.”

---

## 8. Pause features, only fix regressions

Temporarily stop new overworld/sprite features; only fix regressions and polish that path. Fewer moving parts makes it easier to see if a fix actually helps.

---

See also: [OverworldSoftlock_RootCause.md](OverworldSoftlock_RootCause.md), [OverworldSoftlock_Investigation_Alternatives.md](OverworldSoftlock_Investigation_Alternatives.md).
