# Asar Usage and ROM Management

This document outlines best practices for using Asar and managing ROM files within the Oracle of Secrets project.

## ROM Naming Convention

| File | Role |
|---|---|
| `Roms/oos<VERSION>.sfc` | Unpatched base ROM — the **edit target** (yaze, z3ed, ZScream) |
| `Roms/oos<VERSION>x.sfc` | Asar-patched output — **test/emulator target only**, never edited directly |

Current version: **168** (`oos168.sfc` / `oos168x.sfc`).

When the version increments: `oos169.sfc` (base) and `oos169x.sfc` (patched).

> **Historical note:** `oos168_test2.sfc` was a transitional name used during the ZSCustomOverworld v3 port.
> The standard naming (`oos168.sfc`) is canonical going forward.

Emulator/testing runs should always use the patched ROM (`oos168x.sfc`), not the base ROM.

The `Roms/` directory is ignored by git, so you don't have to worry about committing ROM files.

## Version Bump (macOS/Linux)

Use the bump script to create the next clean ROM and copy save states/SRMs:

```sh
./Scripts/Build/rom_bump.sh 168
```

This creates `Roms/oos169.sfc` (read-only) and copies `oos168x.*` save files to `oos169x.*`.

## Build Script (macOS/Linux)

Use the build script to archive the previous patched ROM and produce a fresh patched build:

```sh
./Scripts/Build/build_rom.sh 168
```

What it does:
1. Archives the existing `Roms/oos168x.sfc` to `~/Documents/OracleOfSecrets/Roms/`.
2. Copies `Roms/oos168.sfc` → `Roms/oos168x.sfc` (base ROM to patched output).
3. Runs `asar Oracle_main.asm Roms/oos168x.sfc`.

## Windows (Legacy)

`build.bat` is still available but not maintained. Prefer the macOS/Linux scripts above for the current workflow.

## Manual Build Process (macOS/Linux)

If you need to run Asar manually:

1.  **Copy the clean ROM**:
    ```sh
    cp Roms/oos168.sfc Roms/oos168x.sfc
    ```

2.  **Run Asar**:
    ```sh
    asar Oracle_main.asm Roms/oos168x.sfc
    ```

Using the scripts is recommended to avoid mistakes.
