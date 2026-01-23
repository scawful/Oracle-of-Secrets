"""Filesystem paths for the Oracle Mesen2 client."""

from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPT_DIR.parent
MANIFEST_PATH = REPO_ROOT / "Docs" / "Testing" / "save_state_library.json"
LIBRARY_ROOT = REPO_ROOT / "Roms" / "SaveStates" / "library"
