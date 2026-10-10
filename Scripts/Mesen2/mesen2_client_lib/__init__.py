"""Shim: `import mesen2_client_lib` loads the package from mesen2-oos/tools/oos_client.

Set MESEN2_OOS_ROOT to override the sibling mesen2-oos checkout.
"""
import os
import sys
from pathlib import Path

_root = Path(os.environ.get("MESEN2_OOS_ROOT") or Path(__file__).resolve().parents[4] / "mesen2-oos")
_client_dir = _root / "tools" / "oos_client"
if not (_client_dir / "mesen2_client_lib").is_dir():
    raise ImportError(f"{_client_dir} not found; set MESEN2_OOS_ROOT to your mesen2-oos checkout")
__path__ = [str(_client_dir / "mesen2_client_lib")]
if str(_client_dir) not in sys.path:
    sys.path.append(str(_client_dir))  # for mesen2_registry
