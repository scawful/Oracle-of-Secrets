"""
Unit tests for the Mesen2 socket bridge module.
"""

import json

import pytest

from mesen2_client_lib.bridge import MesenBridge


class TestBridgeConnection:
    def test_socket_path_discovery(self, mock_socket_path, mock_server):
        bridge = MesenBridge(socket_path=mock_socket_path)
        assert bridge.socket_path == mock_socket_path

    def test_is_connected_when_server_responds(self, mock_server, mock_socket_path):
        mock_server.set_response("PING", {"success": True, "data": '"PONG"'})
        bridge = MesenBridge(socket_path=mock_socket_path)
        assert bridge.is_connected() is True

    def test_is_connected_when_no_server(self, mock_socket_path):
        # Create a placeholder so the bridge doesn't auto-discover other sockets.
        from pathlib import Path
        Path(mock_socket_path).touch()
        bridge = MesenBridge(socket_path=mock_socket_path)
        assert bridge.is_connected() is False

    def test_socket_path_resolves_from_instance_registry(self, tmp_path, monkeypatch):
        registry_dir = tmp_path / "instances"
        registry_dir.mkdir(parents=True, exist_ok=True)
        (registry_dir / "oos-target.json").write_text(
            json.dumps({"instance": "oos-target", "socket": "/tmp/mesen2-oos-target.sock"})
        )

        monkeypatch.delenv("MESEN2_SOCKET_PATH", raising=False)
        monkeypatch.setenv("MESEN2_INSTANCE", "oos-target")
        monkeypatch.setenv("MESEN2_REGISTRY_DIR", str(registry_dir))

        bridge = MesenBridge()
        assert bridge.socket_path == "/tmp/mesen2-oos-target.sock"


class TestBridgeCommands:
    def test_send_command_success(self, mock_server, mock_socket_path):
        mock_server.set_response("STATE", {"success": True, "data": '{"running": true}'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.send_command("STATE")

        assert result["success"] is True
        assert mock_server.received_commands[-1]["type"] == "STATE"

    def test_send_command_with_params(self, mock_server, mock_socket_path):
        mock_server.set_response("READ", {"success": True, "data": '"0x42"'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.send_command("READ", {"addr": "0x7E0000"})

        assert result["success"] is True
        cmd = mock_server.received_commands[-1]
        assert cmd["type"] == "READ"
        assert cmd["addr"] == "0x7E0000"

    def test_send_command_error_response(self, mock_server, mock_socket_path):
        mock_server.set_response("INVALID", {"success": False, "error": "Unknown command"})
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.send_command("INVALID")

        assert result["success"] is False
        assert "error" in result


class TestMemoryOperations:
    def test_read_memory(self, mock_server, mock_socket_path):
        mock_server.set_response("READ", {"success": True, "data": '"0x42"'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        value = bridge.read_memory(0x7E0000)

        assert value == 0x42

    def test_read_memory16(self, mock_server, mock_socket_path):
        mock_server.set_response("READ16", {"success": True, "data": '"0x1234"'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        value = bridge.read_memory16(0x7E0000)

        assert value == 0x1234

    def test_write_memory(self, mock_server, mock_socket_path):
        mock_server.set_response("WRITE", {"success": True, "data": '"OK"'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.write_memory(0x7E0000, 0xFF)

        assert result is True
        cmd = mock_server.received_commands[-1]
        assert cmd["addr"] == "0x7E0000"
        assert cmd["value"] == "0xFF"

    def test_read_block(self, mock_server, mock_socket_path):
        mock_server.set_response("READBLOCK", {"success": True, "data": '"0102030405"'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        data = bridge.read_block(0x7E0000, 5)

        assert data == bytes([1, 2, 3, 4, 5])

    def test_memory_size(self, mock_server, mock_socket_path):
        mock_server.set_response(
            "MEMORY_SIZE",
            {"success": True, "data": {"memtype": "wram", "size": 131072}},
        )
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.memory_size("wram")

        assert result["success"] is True
        cmd = mock_server.received_commands[-1]
        assert cmd["memtype"] == "wram"


class TestEmulationControl:
    def test_pause(self, mock_server, mock_socket_path):
        mock_server.set_response("PAUSE", {"success": True, "data": '"OK"'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.pause()

        assert result is True

    def test_resume(self, mock_server, mock_socket_path):
        mock_server.set_response("RESUME", {"success": True, "data": '"OK"'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.resume()

        assert result is True

    def test_reset(self, mock_server, mock_socket_path):
        mock_server.set_response("RESET", {"success": True, "data": '"OK"'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.reset()

        assert result is True

    def test_step(self, mock_server, mock_socket_path):
        mock_server.set_response("STEP", {"success": True, "data": '"OK"'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.step(count=10, mode="over")

        assert result is True
        cmd = mock_server.received_commands[-1]
        assert cmd["count"] == "10"
        assert cmd["mode"] == "over"


class TestStateManagement:
    def test_save_state_to_slot(self, mock_server, mock_socket_path):
        mock_server.set_response("SAVESTATE", {"success": True, "data": '"OK"'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.save_state(slot=1)

        assert result is True
        cmd = mock_server.received_commands[-1]
        assert cmd["slot"] == "1"

    def test_load_state_from_slot(self, mock_server, mock_socket_path):
        mock_server.set_response("LOADSTATE", {"success": True, "data": '"OK"'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.load_state(slot=1)

        assert result is True

    def test_save_state_to_path(self, mock_server, mock_socket_path):
        mock_server.set_response("SAVESTATE", {"success": True, "data": '"OK"'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.save_state(path="/tmp/test.mss")

        assert result is True
        cmd = mock_server.received_commands[-1]
        assert cmd["path"] == "/tmp/test.mss"


class TestRomInfo:
    def test_get_rom_info(self, mock_server, mock_socket_path):
        mock_server.set_response(
            "ROMINFO",
            {
                "success": True,
                "data": {
                    "filename": "test.sfc",
                    "format": "SFC",
                    "consoleType": "Snes",
                    "crc32": "12345678",
                },
            },
        )
        bridge = MesenBridge(socket_path=mock_socket_path)

        info = bridge.get_rom_info()

        assert info["filename"] == "test.sfc"
        assert info["format"] == "SFC"


class TestObservabilityCommands:
    def test_capabilities(self, mock_server, mock_socket_path):
        mock_server.set_response("CAPABILITIES", {"success": True, "data": {"api": "2.1"}})
        bridge = MesenBridge(socket_path=mock_socket_path)

        res = bridge.capabilities()

        assert res["success"] is True
        cmd = mock_server.received_commands[-1]
        assert cmd["type"] == "CAPABILITIES"

    def test_metrics(self, mock_server, mock_socket_path):
        mock_server.set_response("METRICS", {"success": True, "data": {"latency_ms": 2}})
        bridge = MesenBridge(socket_path=mock_socket_path)

        res = bridge.metrics()

        assert res["success"] is True
        cmd = mock_server.received_commands[-1]
        assert cmd["type"] == "METRICS"

    def test_command_history(self, mock_server, mock_socket_path):
        mock_server.set_response("COMMAND_HISTORY", {"success": True, "data": {"entries": []}})
        bridge = MesenBridge(socket_path=mock_socket_path)

        res = bridge.command_history(count=15)

        assert res["success"] is True
        cmd = mock_server.received_commands[-1]
        assert cmd["type"] == "COMMAND_HISTORY"
        assert cmd["count"] == "15"

    def test_register_agent(self, mock_server, mock_socket_path):
        mock_server.set_response("AGENT_REGISTER", {"success": True, "data": {"registered": True}})
        bridge = MesenBridge(socket_path=mock_socket_path)

        res = bridge.register_agent("agent-1", agent_name="Test Agent", version="1.0")

        assert res["success"] is True
        cmd = mock_server.received_commands[-1]
        assert cmd["type"] == "AGENT_REGISTER"
        assert cmd["agentId"] == "agent-1"
        assert cmd["agentName"] == "Test Agent"
        assert cmd["version"] == "1.0"


class TestCheatManagement:
    def test_add_cheat(self, mock_server, mock_socket_path):
        mock_server.set_response("CHEAT", {"success": True, "data": '"OK"'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.add_cheat("7E0DBE:99", format="ProActionReplay")

        assert result is True
        cmd = mock_server.received_commands[-1]
        assert cmd["action"] == "add"
        assert cmd["code"] == "7E0DBE:99"

    def test_list_cheats(self, mock_server, mock_socket_path):
        mock_server.set_response(
            "CHEAT",
            {
                "success": True,
                "data": {"cheats": [{"code": "7E0DBE:99", "type": "ProActionReplay"}]},
            },
        )
        bridge = MesenBridge(socket_path=mock_socket_path)

        cheats = bridge.list_cheats()

        assert len(cheats) == 1
        assert cheats[0]["code"] == "7E0DBE:99"

    def test_clear_cheats(self, mock_server, mock_socket_path):
        mock_server.set_response("CHEAT", {"success": True, "data": '"OK"'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.clear_cheats()

        assert result is True
        cmd = mock_server.received_commands[-1]
        assert cmd["action"] == "clear"


class TestMemoryAnalysis:
    def test_search_memory(self, mock_server, mock_socket_path):
        mock_server.set_response(
            "SEARCH",
            {"success": True, "data": {"matches": ["0x7E0100", "0x7E0200"]}},
        )
        bridge = MesenBridge(socket_path=mock_socket_path)

        matches = bridge.search_memory("A9 00 8D", memtype="WRAM")

        assert len(matches) == 2
        assert 0x7E0100 in matches
        assert 0x7E0200 in matches

    def test_create_snapshot(self, mock_server, mock_socket_path):
        mock_server.set_response("SNAPSHOT", {"success": True, "data": '"OK"'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.create_snapshot("before_action", memtype="WRAM")

        assert result is True
        cmd = mock_server.received_commands[-1]
        assert cmd["name"] == "before_action"

    def test_diff_snapshot(self, mock_server, mock_socket_path):
        mock_server.set_response(
            "DIFF",
            {
                "success": True,
                "data": {
                    "changes": [
                        {"addr": "0x7E0100", "old": "0x00", "new": "0xFF"},
                        {"addr": "0x7E0200", "old": "0x10", "new": "0x20"},
                    ]
                },
            },
        )
        bridge = MesenBridge(socket_path=mock_socket_path)

        changes = bridge.diff_snapshot("before_action")

        assert len(changes) == 2
        assert changes[0]["addr"] == 0x7E0100
        assert changes[0]["old"] == 0x00
        assert changes[0]["new"] == 0xFF


class TestLabelManagement:
    def test_set_label(self, mock_server, mock_socket_path):
        mock_server.set_response("LABELS", {"success": True, "data": '"OK"'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.set_label(0x7E0100, "player_hp", comment="Player health")

        assert result is True
        cmd = mock_server.received_commands[-1]
        assert cmd["action"] == "set"
        assert cmd["label"] == "player_hp"

    def test_get_label(self, mock_server, mock_socket_path):
        mock_server.set_response(
            "LABELS",
            {"success": True, "data": {"label": "player_hp", "comment": "Player health"}},
        )
        bridge = MesenBridge(socket_path=mock_socket_path)

        label_info = bridge.get_label(0x7E0100)

        assert label_info is not None
        assert label_info["label"] == "player_hp"

    def test_lookup_label(self, mock_server, mock_socket_path):
        mock_server.set_response(
            "LABELS", {"success": True, "data": {"addr": "0x7E0100"}}
        )
        bridge = MesenBridge(socket_path=mock_socket_path)

        addr = bridge.lookup_label("player_hp")

        assert addr == 0x7E0100


class TestEvalAndPc:
    def test_eval_expression(self, mock_server, mock_socket_path):
        mock_server.set_response(
            "EVAL",
            {"success": True, "data": {"value": 5, "hex": "0x5", "type": "numeric"}},
        )
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.eval_expression("A", cpu_type="snes", use_cache=False)

        assert result["success"] is True
        cmd = mock_server.received_commands[-1]
        assert cmd["expression"] == "A"
        assert cmd["cpu"] == "snes"
        assert cmd["cache"] == "false"

    def test_set_pc(self, mock_server, mock_socket_path):
        mock_server.set_response("SET_PC", {"success": True, "data": {"pc": "0x008000"}})
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.set_pc(0x008000)

        assert result["success"] is True
        cmd = mock_server.received_commands[-1]
        assert cmd["addr"] == "0x008000"


class TestDrawPath:
    def test_draw_path(self, mock_server, mock_socket_path):
        mock_server.set_response("DRAW_PATH", {"success": True, "data": '"OK"'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.draw_path("10,10,20,20", color="0x00FF00", frames=30)

        assert result["success"] is True
        cmd = mock_server.received_commands[-1]
        assert cmd["points"] == "10,10,20,20"
        assert cmd["color"] == "0x00FF00"
        assert cmd["frames"] == "30"
