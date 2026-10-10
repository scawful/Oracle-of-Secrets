#!/usr/bin/env python3
"""Shim: run the Mesen2 client from the sibling mesen2-oos checkout.

The client lives in mesen2-oos/tools/oos_client. Set MESEN2_OOS_ROOT to override.
This file also serves as mesen2_registry.py (same code, target picked by file name).
"""
import os
import runpy
import sys
from pathlib import Path

root = Path(os.environ.get("MESEN2_OOS_ROOT") or Path(__file__).resolve().parents[3] / "mesen2-oos")
target = root / "tools" / "oos_client" / Path(__file__).name
if not target.is_file():
    sys.exit(f"error: {target} not found; set MESEN2_OOS_ROOT to your mesen2-oos checkout")
if __name__ == "__main__":
    sys.argv[0] = str(target)
    runpy.run_path(str(target), run_name="__main__")
