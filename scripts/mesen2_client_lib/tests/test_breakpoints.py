"""
Tests for breakpoint functionality.
"""

import pytest

from mesen2_client_lib.bridge import MesenBridge

class TestBreakpointCommands:
    def test_add_breakpoint_basic(self, mock_server, mock_socket_path):
        mock_server.set_response("BREAKPOINT", {"success": True, "data": {"id": 1}})
        bridge = MesenBridge(socket_path=mock_socket_path)

        bp_id = bridge.add_breakpoint(0x008000)

        assert bp_id == 1
        cmd = mock_server.received_commands[-1]
        assert cmd["type"] == "BREAKPOINT"
        assert cmd["action"] == "add"
        assert cmd["addr"] == "0x008000"
        assert cmd["bptype"] == "exec"

    def test_add_breakpoint_with_type(self, mock_server, mock_socket_path):
        mock_server.set_response("BREAKPOINT", {"success": True, "data": {"id": 2}})
        bridge = MesenBridge(socket_path=mock_socket_path)

        bp_id = bridge.add_breakpoint(0x7E0000, bptype="rw")

        assert bp_id == 2
        cmd = mock_server.received_commands[-1]
        assert cmd["bptype"] == "rw"

    def test_add_breakpoint_with_range(self, mock_server, mock_socket_path):
        mock_server.set_response("BREAKPOINT", {"success": True, "data": {"id": 3}})
        bridge = MesenBridge(socket_path=mock_socket_path)

        bp_id = bridge.add_breakpoint(
            0x7E0000, bptype="rw", end_address=0x7E00FF, memtype="WRAM"
        )

        assert bp_id == 3
        cmd = mock_server.received_commands[-1]
        assert cmd["addr"] == "0x7E0000"
        assert cmd["endaddr"] == "0x7E00FF"
        assert cmd["memtype"] == "WRAM"

    def test_add_breakpoint_with_condition(self, mock_server, mock_socket_path):
        mock_server.set_response("BREAKPOINT", {"success": True, "data": {"id": 4}})
        bridge = MesenBridge(socket_path=mock_socket_path)

        bp_id = bridge.add_breakpoint(0x008000, condition="A == 0x42")

        assert bp_id == 4
        cmd = mock_server.received_commands[-1]
        assert cmd["condition"] == "A == 0x42"

    def test_add_breakpoint_failure(self, mock_server, mock_socket_path):
        mock_server.set_response(
            "BREAKPOINT", {"success": False, "error": "No ROM loaded"}
        )
        bridge = MesenBridge(socket_path=mock_socket_path)

        bp_id = bridge.add_breakpoint(0x008000)

        assert bp_id == -1

    def test_remove_breakpoint(self, mock_server, mock_socket_path):
        mock_server.set_response("BREAKPOINT", {"success": True, "data": '"OK"'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.remove_breakpoint(1)

        assert result is True
        cmd = mock_server.received_commands[-1]
        assert cmd["action"] == "remove"
        assert cmd["id"] == "1"

    def test_remove_breakpoint_not_found(self, mock_server, mock_socket_path):
        mock_server.set_response(
            "BREAKPOINT", {"success": False, "error": "Breakpoint not found: 999"}
        )
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.remove_breakpoint(999)

        assert result is False

    def test_list_breakpoints_empty(self, mock_server, mock_socket_path):
        mock_server.set_response(
            "BREAKPOINT", {"success": True, "data": {"breakpoints": []}}
        )
        bridge = MesenBridge(socket_path=mock_socket_path)

        breakpoints = bridge.list_breakpoints()

        assert breakpoints == []

    def test_list_breakpoints_with_data(self, mock_server, mock_socket_path):
        mock_server.set_response(
            "BREAKPOINT",
            {
                "success": True,
                "data": {
                    "breakpoints": [
                        {"id": 1, "addr": "0x008000", "type": 1, "enabled": True},
                        {
                            "id": 2,
                            "addr": "0x7E0000",
                            "endaddr": "0x7E00FF",
                            "type": 6,
                            "enabled": True,
                        },
                    ]
                },
            },
        )
        bridge = MesenBridge(socket_path=mock_socket_path)

        breakpoints = bridge.list_breakpoints()

        assert len(breakpoints) == 2
        assert breakpoints[0]["id"] == 1
        assert breakpoints[0]["addr"] == "0x008000"
        assert breakpoints[1]["id"] == 2
        assert breakpoints[1]["endaddr"] == "0x7E00FF"

    def test_enable_breakpoint(self, mock_server, mock_socket_path):
        mock_server.set_response("BREAKPOINT", {"success": True, "data": '"OK"'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.enable_breakpoint(1)

        assert result is True
        cmd = mock_server.received_commands[-1]
        assert cmd["action"] == "enable"
        assert cmd["id"] == "1"

    def test_disable_breakpoint(self, mock_server, mock_socket_path):
        mock_server.set_response("BREAKPOINT", {"success": True, "data": '"OK"'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.disable_breakpoint(1)

        assert result is True
        cmd = mock_server.received_commands[-1]
        assert cmd["action"] == "disable"
        assert cmd["id"] == "1"

    def test_clear_breakpoints(self, mock_server, mock_socket_path):
        mock_server.set_response("BREAKPOINT", {"success": True, "data": '"OK"'})
        bridge = MesenBridge(socket_path=mock_socket_path)

        result = bridge.clear_breakpoints()

        assert result is True
        cmd = mock_server.received_commands[-1]
        assert cmd["action"] == "clear"


class TestBreakpointTypeFlags:
    def test_exec_type(self, mock_server, mock_socket_path):
        mock_server.set_response("BREAKPOINT", {"success": True, "data": {"id": 1}})
        bridge = MesenBridge(socket_path=mock_socket_path)

        bridge.add_breakpoint(0x008000, bptype="exec")
        cmd = mock_server.received_commands[-1]
        assert cmd["bptype"] == "exec"

    def test_read_type(self, mock_server, mock_socket_path):
        mock_server.set_response("BREAKPOINT", {"success": True, "data": {"id": 1}})
        bridge = MesenBridge(socket_path=mock_socket_path)

        bridge.add_breakpoint(0x7E0000, bptype="read")
        cmd = mock_server.received_commands[-1]
        assert cmd["bptype"] == "read"

    def test_write_type(self, mock_server, mock_socket_path):
        mock_server.set_response("BREAKPOINT", {"success": True, "data": {"id": 1}})
        bridge = MesenBridge(socket_path=mock_socket_path)

        bridge.add_breakpoint(0x7E0000, bptype="write")
        cmd = mock_server.received_commands[-1]
        assert cmd["bptype"] == "write"

    def test_read_write_type(self, mock_server, mock_socket_path):
        mock_server.set_response("BREAKPOINT", {"success": True, "data": {"id": 1}})
        bridge = MesenBridge(socket_path=mock_socket_path)

        bridge.add_breakpoint(0x7E0000, bptype="rw")
        cmd = mock_server.received_commands[-1]
        assert cmd["bptype"] == "rw"
