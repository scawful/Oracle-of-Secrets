import json
from pathlib import Path

from mesen2_client_lib import cli


class DummyClient:
    def __init__(self, labels):
        self._usdasm_labels = labels
        self.bridge = None

    def load_usdasm_labels(self):
        return len(self._usdasm_labels)


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
