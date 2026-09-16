# RG353P testing

**Use the handheld to play. Use one host command to identify a build or collect a bug.** The emulator app and the game ROM are separate updates.

## Current checkpoint — September 16, 2026

- **Oracle of Secrets `0.1.10-workshop` is installed and device-verified.** Workshop still includes Save checkpoint, Capture bug, explicit restore, optional Name/Note fields, best-effort `game_state`/`sprites`, measured FPS, and atomic host status.
- Version 0.1.10 includes the `0.1.9` batched runtime snapshot and makes the privileged emulator socket USB-only. Android binds `127.0.0.1:27015`; Mac tools attach through `adb forward`. LAN discovery, direct Wi-Fi control, and the associated Wi-Fi locks were removed. The installed APK SHA256 is `967e1184063bc9c37075e19d7bf4379ff987bd8ffd140a9f6b9f8d3fb9d503f0`.
- `GAMESTATE`, `SPRITES`, and now `HEALTH` remain observational without starting Mesen's persistent debugger. `HEALTH` returns PC/disassembly details only when a debugger was already active. The loaded-ROM SHA1 is cached across frequent UI/socket status polls and invalidated after each successful ROM load. In a short paused sample, process CPU averaged 41.8% before and 33.4% after; the UI thread averaged 20.8% before and 11.8% after. These samples are directional, not a full-speed claim.
- The handheld retains the September 14 outdoor color/rain ROM (`0c225e0f…`, CRC `9109C3A5`). The minecart junction build remains on the Mac and has not been deployed.
- All 14 files in the immediate pre-feature ROM/save backup retained their hashes, including `oos91x` saves. The feature test created two title-screen checkpoints and one Weather-category QA capture. Existing states/SRAM were not migrated.
- The 0.1.6 checkpoint at frame 836 contains both metadata objects, survived sleep/wake with the same framebuffer, and collected successfully with zero warnings. Its exact APK is archived for restore compatibility. Measured emulation remains about 37–41 FPS in controlled fixtures; final 0.1.8 measured 39.93 FPS independently and 40.51 FPS in Workshop. The socket's `60.1` is nominal. Speaker, physical controls, and sustained play still need user testing.

The device was left paused on 0.1.10 at frame 302 with `debugging=false`. `ss` showed only `127.0.0.1:27015`; USB-forwarded health passed at 7 ms against CRC `9109C3A5`, and direct `192.168.1.227:27015` access timed out. Preinstall Workshop artifacts were copied to `Roms/device-workshop/workshop-jg9bgwwq/` without deleting device files. `mesen-discover` reads canonical app-private `workshop.json` through Android `run-as`, so USB status matches the Workshop screen. Direct Wi-Fi access is intentionally unavailable. The save/capture buttons use the app locally and do not require a Mac connection.

The [current diagnostics report](../Planning/Status/rg353p_workshop_diagnostics_2026-09-15.md) records 0.1.5 through 0.1.8; the exact 0.1.10 deployment evidence is in `Roms/HandheldApps/oos-android-0.1.10-workshop-20260916-967e1184/build.json`. The [0.1.4 names/Wi-Fi follow-up](../Planning/Status/rg353p_workshop_labels_2026-09-15.md) is historical. The [Workshop feature report](../Planning/Status/rg353p_workshop_features_2026-09-15.md) records the 0.1.3 save/capture/restore tests. Use live `status` when starting a test; a cached Workshop file does not prove connectivity.

## Capture directly on the handheld

1. Open Workshop with the existing Back/Mode control or Start + Select. The game pauses.
2. Optionally tap **Name** or **Note** to type. D-pad skips these fields. Then choose **Save checkpoint**, or **Capture bug** and select Weather, Collision / movement, Audio, Graphics, or Other.
3. Wait for the saved/captured message. Each item contains a state, game screenshot, exact ROM/app identity and file hashes.
4. Use **Checkpoints** to review a saved moment. Selecting it does not load it; **Restore checkpoint** does. Restore replaces the current emulated session and leaves it paused.

Only complete checkpoints from the same ROM and exact APK can restore. Unavailable entries explain the mismatch and stay visible. Normal game saves and legacy emulator states are separate. A changed APK may require the original APK to restore an older checkpoint; no automatic migration occurs.

Later, connect USB and collect the saved items on the Mac:

```bash
Scripts/Device/oos_rg353p.sh collect
```

This creates a new folder under `Roms/device-workshop/`, verifies hashes, retains partial evidence, and leaves the device files in place. The QA items from implementation testing are identified in the feature report; they are not user progress or a newly reported weather bug.

## Three things to keep separate

| Thing | Meaning | Consistency rule |
|---|---|---|
| ROM build (`.sfc`) | The version of the game being tested | Give each distributed build a unique name and full hash manifest. |
| Save RAM (`.srm`) | Normal in-game progress, potentially containing several save slots | Back up under a named profile; transfer a copy to another build only after checking compatibility. |
| Emulator state (`.mss` for Mesen; `.frz` for Snes9x) | A frozen emulator session, including cached code/data | Keep the original ROM and emulator identity. Do not assume it works on another build or emulator. |

Changing a ROM filename also changes the default save filename the emulator looks for. A named build may therefore show empty save slots until a save-RAM copy is explicitly selected. The workflow never silently imports an older save or state. `handheld` is a backup-profile label, not an assertion about a particular game slot.

## Everyday commands

Run from the Oracle repository on the Mac. Connect USB and authorize debugging. An explicit `--endpoint` is only for a separately secured tunnel; the Android app no longer accepts direct LAN connections.

```bash
# Which game build is actually loaded? Does it match the stored copies?
Scripts/Device/oos_rg353p.sh status

# Record a bug without sending controls, pausing, or resetting.
Scripts/Device/oos_rg353p.sh capture --note "Rain continued after leaving the village"

# Copy existing save files and ROMs into a new, verified backup folder.
Scripts/Device/oos_rg353p.sh backup --profile handheld
```

When reporting a bug in chat, say **“capture this bug: …”** while the handheld is connected and the problem is visible. Opening Workshop pauses through the handheld's own controls. The capture command itself does not pause or resume. Screenshots and frame observations can therefore come from slightly different times if play continues.

Capture folders live under `Roms/device-captures/`. Each includes a note, ROM identity, live run-state observations, screenshot, and any read errors. USB captures also include the Android display and installed APK fingerprint. A capture does not create an emulator state. Missing debugger/game-state support is reported explicitly; cached Workshop fields are never presented as live reads.

Backup folders live under `Roms/device-saves/backup-<profile>-<UTC>-<unique>/`. The manifest distinguishes ROMs, save RAM, states, and sidecars. It inventories Mesen internal Saves/SaveStates as well as SD/drop copies, records full file hashes, and reports missing or inaccessible locations. Existing files are copied without renaming them. Legacy state origins remain **unknown**, even when a current ROM sits beside them. Disk backup does not force unsaved in-memory progress to be saved.

For lower-level Mesen commands over USB, generate and load the explicit handheld environment:

```bash
Scripts/Device/oos_rg353p.sh mesen-env
source .context/scratchpad/mesen2/handheld.env
python3 Scripts/Mesen2/mesen2_client.py health
```

The environment exports `MESEN2_HANDHELD=1` and the explicit forwarded endpoint `tcp://127.0.0.1:27015`. In handheld mode, the client refuses Unix socket auto-discovery, so a missing or malformed handheld target cannot silently attach to a desktop Mesen instance. `mesen-env --lan` now fails explicitly instead of generating an unreachable or unsafe target.

## Android and app performance reports

Connect the handheld through adb, then run:

```bash
Scripts/Device/oos_rg353p.sh android-report --seconds 5
```

This saves a new `report.json` and `summary.txt` under `Roms/device-diagnostics/`. It records the Android build, installed APK fingerprint, Home/foreground app, available memory, and a short CPU sample. `--serial` selects an authorized device; `--out` selects a parent directory for unique reports. It reads Android without connecting to or controlling the emulator.

If Oracle is closed or restarts during sampling, its CPU result is **unavailable**. A partial report still saves successfully; inspect the status and unavailable fields. CPU is reported both as a share of all logical CPUs and as a one-core equivalent. A value of 100% of one core means one core's worth of work, not the whole four-core device. Sequential reads introduce sampling error.

For a before/after comparison, keep the same ROM, scene, run/pause state, display mode, and debug attachment. This report does not measure frame rate or speaker quality. `STATE.fps` is the nominal SNES rate, so use actual emulated frame-count change over elapsed time when evaluating gameplay speed.

The app is labeled **Oracle of Secrets** in Android. Its larger icon is installed and pinned on Home. Opening that icon returns to the existing session without a ROM-selection extra. Workshop's Add to Home reports unsupported on this vendor launcher; if the icon is removed, open All Apps, find Oracle, and drag it onto Home. The app keeps its visible screen awake; returning Home retains Android's normal timeout. See the [Android update report](../Planning/Status/rg353p_android_update_2026-09-15.md).

## Names for Android app builds

APK packages live separately under `Roms/HandheldApps/`. The installed emulator is `oos-android-0.1.10-workshop-20260916-967e1184` (version code 11), APK SHA256 `967e1184063bc9c37075e19d7bf4379ff987bd8ffd140a9f6b9f8d3fb9d503f0`. The exact prior 0.1.8 and 0.1.6 APKs remain archived so their checkpoints stay restorable; 0.1.7 is preserved as the superseded health-probe diagnostic build, and 0.1.9 was never installed. Installing an APK does not select a newer game ROM or migrate saves. Exact-APK restore rules still apply to older checkpoints.

## Names for new test builds

Format: `oos-<base-version>-<UTC-date>-<change-name>-<hash8>.sfc`

Prepared example: `oos-168-20260915-minecart-junction-992c2441.sfc`.

The eight-character hash identifies the ROM contents. The adjacent `build.json` contains full SHA256/SHA1/CRC32, source location, creation time, and save-handling rules. The build system still uses `Roms/oos168.sfc` for editing and `Roms/oos168x.sfc` for assembly output; naming is applied to a separate distribution copy.

```bash
Scripts/Device/oos_rg353p.sh prepare --name minecart-junction \
  --rom Roms/TestBuilds/minecart-junction-2026-09-15/oos168x.sfc
```

`prepare` makes a new immutable directory under `Roms/HandheldBuilds/`. It prints the exact install command but does not run it. Existing directories, ROMs, and saves are not overwritten.

When an update is intentionally selected, use the printed `push --rom <prepared-path> --mesen` command. This backs up disk saves first, copies the selected ROM, launches that exact filename, and verifies the loaded hash. It restarts Mesen, so finish the current play session first. It does not migrate save RAM. The deployment sequence has host-only tests; this new named deployment has not yet been exercised on the device.

## Remaining work

1. Choose the ordinary save-RAM profile to carry into the first named build; inspect compatibility and copy it explicitly.
2. Yaze TCP P1/timeout is compiled in `yaze/build/presets/mac-ai/bin/Debug/z3ed`. Use USB `MESEN2_SOCKET_PATH=tcp://127.0.0.1:27015` after `mesen-forward`. Do not use `/usr/local/bin/z3ed` until that nightly symlink is refreshed.
3. Compare 0.1.10's batched status snapshot against the prior 0.1.8 measurements under the same scene and pause/run state, then continue core-emulation performance work separately. The USB-only transport checks have passed. Profiling still places most running cost in SNES CPU/PPU/SPC execution and observed speed remains about 37–41 FPS.

Review evidence: [Workshop and testing review](/Users/scawful/src/hobby/oracle-of-secrets/Docs/Planning/Status/rg353p_workshop_review_2026-09-15.md).
