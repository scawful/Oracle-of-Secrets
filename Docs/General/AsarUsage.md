# Asar Usage and ROM Management

This document outlines the best practices for using Asar and managing ROM files within the Oracle of Secrets project.

## Safety First: Preserve the Clean ROM

The most important rule is to **never modify the clean ROM directly**. The clean ROM for this project is expected to be `Roms/oos169.sfc`. All patches must be applied to a *copy* of this file. This ensures that you always have a pristine base to work from and prevents irreversible changes to the original game file.

The `Roms/` directory is ignored by git, so you don't have to worry about accidentally committing large ROM files.

## The Build Script

A `build.sh` script is provided to automate the build process and enforce safe ROM management.

### Usage

To build the ROM, run the script from the project root. You can optionally provide a version number.

**Build with a version number:**
```sh
./build.sh 1.0
```
This will create a patched ROM named `Roms/oos-v1.0.sfc`.

**Build without a version number:**
```sh
./build.sh
```
This will create a patched ROM named `Roms/oos-patched.sfc`.

### What it Does

1.  **Copies the ROM**: It creates a copy of `Roms/oos169.sfc`.
2.  **Applies the Patch**: It runs `asar` to apply the main patch file (`Oracle_main.asm`) to the newly created ROM copy.
3.  **Output**: The final, patched ROM is placed in the `Roms/` directory.

## Manual Build Process (Not Recommended)

If you need to run the build process manually, follow these steps:

1.  **Create a copy of the clean ROM**:
    ```sh
    cp Roms/oos169.sfc Roms/my_patched_rom.sfc
    ```

2.  **Run Asar**:
    ```sh
    asar Oracle_main.asm Roms/my_patched_rom.sfc
    ```

Using the `build.sh` script is highly recommended to avoid mistakes.
