import mesen2_registry

from mesen2_client_lib import bridge, cli
from mesen2_client_lib.paths import REPO_ROOT


def test_registry_defaults_share_repository_root(monkeypatch):
    monkeypatch.delenv("MESEN2_REGISTRY_DIR", raising=False)
    expected = (
        REPO_ROOT / ".context" / "scratchpad" / "mesen2" / "instances"
    ).resolve()

    assert mesen2_registry._registry_dir() == expected
    assert cli._registry_dir() == expected
    assert bridge._registry_dir() == expected
