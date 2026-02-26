import argparse
import json
from pathlib import Path

import pytest

from mesen2_client_lib import cli


class DummyClient:
    def __init__(self, labels, rom_sha1=""):
        self._usdasm_labels = labels
        self._rom_sha1 = rom_sha1
        self.bridge = None

    def load_usdasm_labels(self):
        return len(self._usdasm_labels)

    def get_rom_info(self):
        if not self._rom_sha1:
            return {}
        return {"sha1": self._rom_sha1}


class DummyBridge:
    def __init__(self):
        self.calls = []
        self.loaded_payload = None

    def send_command(self, command, params):
        self.calls.append((command, params))
        if command == "SYMBOLS_LOAD":
            payload = json.loads(Path(params["file"]).read_text())
            self.loaded_payload = payload
            return {"success": True}
        return {"success": False, "error": "unsupported"}


def test_build_usdasm_symbol_payload_filters_non_rom():
    client = DummyClient(
        {
            "RomLabel": 0x128000,
            "WramLabel": 0x7E1234,
            "LowRomLabel": 0x057000,
        }
    )
    symbols_data, filtered, total, error = cli._build_usdasm_symbol_payload(client)

    assert error == ""
    assert total == 3
    assert filtered == 2
    assert symbols_data is not None
    assert "RomLabel" in symbols_data
    assert "WramLabel" not in symbols_data
    assert "LowRomLabel" not in symbols_data


def test_sync_usdasm_labels_loads_filtered_payload():
    bridge = DummyBridge()
    client = DummyClient({"RomLabel": 0x128000, "WramLabel": 0x7E1234})
    client.bridge = bridge

    result = cli._sync_usdasm_labels(client, clear=True)

    assert result["success"] is True
    assert result["count"] == 1
    assert bridge.loaded_payload is not None
    assert "RomLabel" in bridge.loaded_payload
    assert "WramLabel" not in bridge.loaded_payload


def test_resolve_slot_or_path_with_slot_string():
    slot, path, error = cli._resolve_slot_or_path("7", None)
    assert error is None
    assert slot == 7
    assert path is None


def test_resolve_slot_or_path_with_positional_path():
    slot, path, error = cli._resolve_slot_or_path("Roms/SaveStates/oos168x/oos168x_1.mss", None)
    assert error is None
    assert slot is None
    assert path == "Roms/SaveStates/oos168x/oos168x_1.mss"


def test_resolve_slot_or_path_rejects_conflicting_target_and_path():
    slot, path, error = cli._resolve_slot_or_path("7", "foo.mss")
    assert slot is None
    assert path is None
    assert error is not None


def test_resolve_slot_or_path_missing_target():
    slot, path, error = cli._resolve_slot_or_path(None, None)
    assert slot is None
    assert path is None
    assert error == "Missing slot or path"


def test_normalize_filesystem_path_makes_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = cli._normalize_filesystem_path("states/test.mss")
    assert out == str((tmp_path / "states" / "test.mss").resolve())


def test_preflight_socket_instance_clears_stale_socket_env(tmp_path, monkeypatch):
    registry_dir = tmp_path / "instances"
    registry_dir.mkdir(parents=True, exist_ok=True)
    (registry_dir / "oos-codex-target.json").write_text(
        json.dumps({"instance": "oos-codex-target", "socket": "/tmp/mesen2-oos-codex-target.sock"})
    )

    monkeypatch.setenv("MESEN2_SOCKET_PATH", "/tmp/mesen2-stale.sock")
    monkeypatch.delenv("MESEN2_INSTANCE", raising=False)
    monkeypatch.setenv("MESEN2_REGISTRY_DIR", str(registry_dir))
    args = argparse.Namespace(socket=None, instance="oos-codex-target")

    cli._preflight_socket(args)

    assert cli.os.environ.get("MESEN2_SOCKET_PATH") == "/tmp/mesen2-oos-codex-target.sock"
    assert cli.os.environ.get("MESEN2_INSTANCE") == "oos-codex-target"


def test_preflight_socket_instance_missing_fails_fast(monkeypatch):
    monkeypatch.delenv("MESEN2_SOCKET_PATH", raising=False)
    monkeypatch.setenv("MESEN2_INSTANCE", "oos-codex-stale")
    args = argparse.Namespace(socket=None, instance="oos-instance-does-not-exist")

    with pytest.raises(SystemExit) as exc:
        cli._preflight_socket(args)

    assert exc.value.code == 2


def test_validate_state_freshness_rejects_missing_meta_for_library(tmp_path):
    state_path = tmp_path / "Roms" / "SaveStates" / "library" / "oos168x" / "state.mss"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_bytes(b"state")

    ok, message = cli._validate_state_freshness(state_path, DummyClient({}))
    assert ok is False
    assert "missing meta" in message.lower()


def test_validate_state_freshness_accepts_non_library_without_meta(tmp_path):
    state_path = tmp_path / "tmp" / "scratch.mss"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_bytes(b"state")

    ok, message = cli._validate_state_freshness(state_path, DummyClient({}))
    assert ok is True
    assert message == ""


def test_validate_state_freshness_rejects_rom_sha_mismatch(tmp_path):
    state_path = tmp_path / "Roms" / "SaveStates" / "library" / "oos168x" / "state.mss"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = b"state"
    state_path.write_bytes(payload)
    state_sha1 = cli._sha1_file(state_path)
    meta_path = Path(str(state_path) + ".meta.json")
    meta_path.write_text(
        json.dumps(
            {
                "schema": "mesen_state_meta/v1",
                "state_sha1": state_sha1,
                "rom_sha1": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            }
        )
    )

    ok, message = cli._validate_state_freshness(
        state_path, DummyClient({}, rom_sha1="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    )
    assert ok is False
    assert "rom sha1 mismatch" in message.lower()
