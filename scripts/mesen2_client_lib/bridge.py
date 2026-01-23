"""Bridge import helper for mesen2-mcp."""

import sys
from pathlib import Path

MESEN2_MCP_PATH = Path("/Users/scawful/src/tools/mesen2-mcp")
if MESEN2_MCP_PATH.exists():
    mesen2_mcp_path = str(MESEN2_MCP_PATH)
    if mesen2_mcp_path not in sys.path:
        sys.path.insert(0, mesen2_mcp_path)

from mesen2_mcp.bridge import MesenBridge

__all__ = ["MesenBridge"]
