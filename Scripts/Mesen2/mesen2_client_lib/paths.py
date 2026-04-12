"""Filesystem paths for the Oracle Mesen2 client."""

from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPT_DIR.parent
MANIFEST_PATH = REPO_ROOT / "Docs" / "Debugging" / "Testing" / "save_state_library.json"
LIBRARY_ROOT = REPO_ROOT / "Roms" / "SaveStates" / "library"

# Save-data (SRAM/WRAM savefile mirror) library.
SAVE_DATA_MANIFEST_PATH = REPO_ROOT / "Docs" / "Debugging" / "Testing" / "save_data_library.json"
SAVE_DATA_LIBRARY_ROOT = REPO_ROOT / "Roms" / "SaveData" / "library"

# Human-editable save-data "profiles" (item/flag loadouts) live in-repo.
SAVE_DATA_PROFILE_DIR = REPO_ROOT / "Docs" / "Debugging" / "Testing" / "save_data_profiles"
