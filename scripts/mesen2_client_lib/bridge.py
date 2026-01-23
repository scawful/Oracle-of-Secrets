"""Bridge import helper for mesen2-mcp."""

import os
import sys
from pathlib import Path


def _add_to_path(path: Path) -> None:
    if path.exists():
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


env_path = os.getenv("MESEN2_MCP_PATH")
if env_path:
    _add_to_path(Path(env_path).expanduser())
else:
    _add_to_path(Path.home() / "src" / "tools" / "mesen2-mcp")

try:
    from mesen2_mcp.bridge import MesenBridge
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "mesen2_mcp not found. Set MESEN2_MCP_PATH to the mesen2-mcp repo root."
    ) from exc

__all__ = ["MesenBridge"]
