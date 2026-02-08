# Asar Usage and ROM Management

This document outlines best practices for using Asar and managing ROM files within the Oracle of Secrets project.

## Safety First: Preserve the Clean ROM

The most important rule is to **never modify the clean ROM directly**. The dev ROM for the current cycle may be a ZScream-edited file, for example:

- `Roms/oos168_test2.sfc` (current dev ROM, ZScream 3.2.5 + ZSCustomOverworld v3)

The legacy clean base is still kept read-only:

- `Roms/oos168.sfc` (read-only)

Patched output is always written to:

- `Roms/oos168x.sfc`

Emulator/testing runs should always use the patched ROM (`oos168x.sfc`), not the dev/edit ROM.

When we move to the next version, the number increments:

- `Roms/oos169.sfc` (clean, read-only)
- `Roms/oos169x.sfc` (patched output)

The `Roms/` directory is ignored by git, so you don't have to worry about committing ROM files.

## Version Bump (macOS/Linux)

Use the bump script to create the next clean ROM and copy save states/SRMs:

```sh
./scripts/rom_bump.sh 168
```

This creates `Roms/oos169.sfc` (read-only) and copies `oos168x.*` save files to `oos169x.*`.

## Build Script (macOS/Linux)

Use the build script to archive the previous patched ROM and produce a fresh patched build:

```sh
./scripts/build_rom.sh 168
```

What it does:
1. Archives the existing `Roms/oos168x.sfc` to `~/Documents/OracleOfSecrets/Roms/`.
2. Copies `Roms/oos168_test2.sfc` → `Roms/oos168x.sfc` when present (falls back to `oos168.sfc`).
3. Runs `asar Oracle_main.asm Roms/oos168x.sfc`.

## Windows (Legacy)

`build.bat` is still available but not maintained. Prefer the macOS/Linux scripts above for the current workflow.

## Manual Build Process (macOS/Linux)

If you need to run Asar manually:

1.  **Copy the clean ROM**:
    ```sh
    cp Roms/oos168_test2.sfc Roms/oos168x.sfc  # or oos168.sfc if test ROM isn't present
    ```

2.  **Run Asar**:
    ```sh
    asar Oracle_main.asm Roms/oos168x.sfc
    ```

Using the scripts is recommended to avoid mistakes.
