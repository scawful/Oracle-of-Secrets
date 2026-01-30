"""
Pytest fixtures for Mesen2 socket client tests.
"""

from __future__ import annotations

import json
import os
import socket
import tempfile
import threading
from pathlib import Path

import pytest

import sys

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from mesen2_client_lib.bridge import MesenBridge


class MockSocketServer:
    """Mock Unix socket server for testing bridge communication."""

    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self.responses: dict[str, dict[str, object]] = {}
        self.received_commands: list[dict[str, object]] = []
        self._server_socket: socket.socket | None = None
        self._running = False
        self._thread: threading.Thread | None = None

    def set_response(self, command_type: str, response: dict[str, object]) -> None:
        self.responses[command_type] = response

    def start(self) -> None:
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

        self._server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_socket.bind(self.socket_path)
        self._server_socket.listen(1)
        self._server_socket.settimeout(1.0)
        self._running = True
        self._thread = threading.Thread(target=self._serve)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._server_socket:
            self._server_socket.close()
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

    def _serve(self) -> None:
        while self._running:
            try:
                conn, _ = self._server_socket.accept()
                self._handle_client(conn)
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_client(self, conn: socket.socket) -> None:
        try:
            data = conn.recv(4096).decode()
            if data:
                cmd = json.loads(data.strip())
                self.received_commands.append(cmd)
                cmd_type = cmd.get("type", "")
                response = self.responses.get(
                    cmd_type, {"success": False, "error": f"Unknown command: {cmd_type}"}
                )
                conn.sendall((json.dumps(response) + "\n").encode())
        finally:
            conn.close()


@pytest.fixture
def mock_socket_path() -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield os.path.join(tmpdir, "mesen2-test.sock")


@pytest.fixture
def mock_server(mock_socket_path: str) -> MockSocketServer:
    server = MockSocketServer(mock_socket_path)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def bridge(mock_socket_path: str) -> MesenBridge:
    return MesenBridge(socket_path=mock_socket_path)


def is_mesen_running() -> bool:
    import glob

    sockets = glob.glob("/tmp/mesen2-*.sock")
    if not sockets:
        return False
    try:
        bridge = MesenBridge()
        return bridge.is_connected()
    except Exception:
        return False


requires_mesen = pytest.mark.skipif(
    not is_mesen_running(), reason="Mesen2 emulator not running"
)
