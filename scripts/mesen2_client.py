#!/usr/bin/env python3
"""
Oracle of Secrets Mesen2 Socket Client

Thin entrypoint that delegates to the modularized CLI implementation.
"""

from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from mesen2_client_lib.cli import main


if __name__ == "__main__":
    main()
