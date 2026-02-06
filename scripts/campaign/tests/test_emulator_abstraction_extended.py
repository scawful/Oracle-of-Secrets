"""Extended tests for EmulatorAbstraction and emulator interface components.

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- C.1: Unified emulator abstraction

These tests verify the emulator abstraction system including status,
memory reads, game state, and the Mesen2 backend.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import time

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.emulator_abstraction import (
    EmulatorStatus, MemoryRead, GameStateSnapshot,
    EmulatorInterface, Mesen2Emulator, get_emulator
)


class TestEmulatorStatusEnum:
    """Test EmulatorStatus IntEnum."""

    def test_disconnected_value(self):
        """Test DISCONNECTED value is 0."""
        assert EmulatorStatus.DISCONNECTED == 0

    def test_connecting_value(self):
        """Test CONNECTING value is 1."""
        assert EmulatorStatus.CONNECTING == 1

    def test_connected_value(self):
        """Test CONNECTED value is 2."""
        assert EmulatorStatus.CONNECTED == 2

    def test_running_value(self):
        """Test RUNNING value is 3."""
        assert EmulatorStatus.RUNNING == 3

    def test_paused_value(self):
        """Test PAUSED value is 4."""
        assert EmulatorStatus.PAUSED == 4

    def test_error_value(self):
        """Test ERROR value is 5."""
        assert EmulatorStatus.ERROR == 5

    def test_all_values_distinct(self):
        """Test all values are distinct."""
        values = [s.value for s in EmulatorStatus]
        assert len(values) == len(set(values))


class TestMemoryReadCreation:
    """Test MemoryRead dataclass creation."""

    def test_basic_creation(self):
        """Test creating basic memory read."""
        read = MemoryRead(address=0x7E0010, value=0x09)
        assert read.address == 0x7E0010
        assert read.value == 0x09

    def test_default_size(self):
        """Test default size is 1."""
        read = MemoryRead(address=0x7E0010, value=0x09)
        assert read.size == 1

    def test_custom_size(self):
        """Test custom size."""
        read = MemoryRead(address=0x7E0010, value=0x1234, size=2)
        assert read.size == 2


class TestMemoryReadProperties:
    """Test MemoryRead properties."""

    def test_value16_with_size_2(self):
        """Test value16 with 2-byte read."""
        read = MemoryRead(address=0x7E0022, value=0x0180, size=2)
        assert read.value16 == 0x0180

    def test_value16_with_size_1(self):
        """Test value16 with 1-byte read returns value."""
        read = MemoryRead(address=0x7E0010, value=0x09, size=1)
        assert read.value16 == 0x09

    def test_value24_with_size_3(self):
        """Test value24 with 3-byte read."""
        read = MemoryRead(address=0x7E0000, value=0x123456, size=3)
        assert read.value24 == 0x123456

    def test_value24_with_size_1(self):
        """Test value24 with 1-byte read returns value."""
        read = MemoryRead(address=0x7E0010, value=0x09, size=1)
        assert read.value24 == 0x09


class TestGameStateSnapshotCreation:
    """Test GameStateSnapshot dataclass creation."""

    def test_basic_creation(self):
        """Test creating basic snapshot."""
        snapshot = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x09,
            submode=0x00,
            area=0x29,
            room=0x00,
            link_x=512,
            link_y=480,
            link_z=0,
            link_direction=2,
            link_state=0,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24
        )
        assert snapshot.mode == 0x09
        assert snapshot.link_x == 512

    def test_default_raw_data(self):
        """Test default raw_data is empty dict."""
        snapshot = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x09,
            submode=0x00,
            area=0x29,
            room=0x00,
            link_x=512,
            link_y=480,
            link_z=0,
            link_direction=2,
            link_state=0,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24
        )
        assert snapshot.raw_data == {}

    def test_with_raw_data(self):
        """Test snapshot with raw_data."""
        snapshot = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x09,
            submode=0x00,
            area=0x29,
            room=0x00,
            link_x=512,
            link_y=480,
            link_z=0,
            link_direction=2,
            link_state=0,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24,
            raw_data={"room_id": 0x0100}
        )
        assert snapshot.raw_data["room_id"] == 0x0100


class TestGameStateSnapshotIsPlaying:
    """Test GameStateSnapshot is_playing property."""

    def test_mode_09_is_playing(self):
        """Test mode 0x09 is playing."""
        snapshot = GameStateSnapshot(
            timestamp=1000.0, mode=0x09, submode=0x00, area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0, link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F, health=24, max_health=24
        )
        assert snapshot.is_playing is True

    def test_mode_07_is_playing(self):
        """Test mode 0x07 is playing."""
        snapshot = GameStateSnapshot(
            timestamp=1000.0, mode=0x07, submode=0x00, area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0, link_direction=2, link_state=0,
            indoors=True, inidisp=0x0F, health=24, max_health=24
        )
        assert snapshot.is_playing is True

    def test_mode_00_not_playing(self):
        """Test mode 0x00 is not playing."""
        snapshot = GameStateSnapshot(
            timestamp=1000.0, mode=0x00, submode=0x00, area=0x00, room=0x00,
            link_x=0, link_y=0, link_z=0, link_direction=0, link_state=0,
            indoors=False, inidisp=0x00, health=0, max_health=0
        )
        assert snapshot.is_playing is False


class TestGameStateSnapshotIsOverworld:
    """Test GameStateSnapshot is_overworld property."""

    def test_mode_09_is_overworld(self):
        """Test mode 0x09 is overworld."""
        snapshot = GameStateSnapshot(
            timestamp=1000.0, mode=0x09, submode=0x00, area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0, link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F, health=24, max_health=24
        )
        assert snapshot.is_overworld is True

    def test_mode_07_not_overworld(self):
        """Test mode 0x07 is not overworld."""
        snapshot = GameStateSnapshot(
            timestamp=1000.0, mode=0x07, submode=0x00, area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0, link_direction=2, link_state=0,
            indoors=True, inidisp=0x0F, health=24, max_health=24
        )
        assert snapshot.is_overworld is False


class TestGameStateSnapshotIsDungeon:
    """Test GameStateSnapshot is_dungeon property."""

    def test_mode_07_is_dungeon(self):
        """Test mode 0x07 is dungeon."""
        snapshot = GameStateSnapshot(
            timestamp=1000.0, mode=0x07, submode=0x00, area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0, link_direction=2, link_state=0,
            indoors=True, inidisp=0x0F, health=24, max_health=24
        )
        assert snapshot.is_dungeon is True

    def test_mode_09_not_dungeon(self):
        """Test mode 0x09 is not dungeon."""
        snapshot = GameStateSnapshot(
            timestamp=1000.0, mode=0x09, submode=0x00, area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0, link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F, health=24, max_health=24
        )
        assert snapshot.is_dungeon is False


class TestGameStateSnapshotIsBlackScreen:
    """Test GameStateSnapshot is_black_screen property."""

    def test_black_screen_mode_06(self):
        """Test black screen with mode 0x06 and INIDISP 0x80."""
        snapshot = GameStateSnapshot(
            timestamp=1000.0, mode=0x06, submode=0x00, area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0, link_direction=2, link_state=0,
            indoors=False, inidisp=0x80, health=24, max_health=24
        )
        assert snapshot.is_black_screen is True

    def test_black_screen_mode_07(self):
        """Test black screen with mode 0x07 and INIDISP 0x80."""
        snapshot = GameStateSnapshot(
            timestamp=1000.0, mode=0x07, submode=0x00, area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0, link_direction=2, link_state=0,
            indoors=True, inidisp=0x80, health=24, max_health=24
        )
        assert snapshot.is_black_screen is True

    def test_not_black_screen_normal_inidisp(self):
        """Test not black screen with normal INIDISP."""
        snapshot = GameStateSnapshot(
            timestamp=1000.0, mode=0x07, submode=0x00, area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0, link_direction=2, link_state=0,
            indoors=True, inidisp=0x0F, health=24, max_health=24
        )
        assert snapshot.is_black_screen is False

    def test_not_black_screen_wrong_mode(self):
        """Test not black screen with wrong mode."""
        snapshot = GameStateSnapshot(
            timestamp=1000.0, mode=0x09, submode=0x00, area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0, link_direction=2, link_state=0,
            indoors=False, inidisp=0x80, health=24, max_health=24
        )
        assert snapshot.is_black_screen is False


class TestGameStateSnapshotPosition:
    """Test GameStateSnapshot position property."""

    def test_position_tuple(self):
        """Test position returns (x, y) tuple."""
        snapshot = GameStateSnapshot(
            timestamp=1000.0, mode=0x09, submode=0x00, area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0, link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F, health=24, max_health=24
        )
        assert snapshot.position == (512, 480)


class TestMesen2EmulatorConstants:
    """Test Mesen2Emulator RAM address constants."""

    def test_ram_mode_address(self):
        """Test RAM_MODE address."""
        assert Mesen2Emulator.RAM_MODE == 0x7E0010

    def test_ram_submode_address(self):
        """Test RAM_SUBMODE address."""
        assert Mesen2Emulator.RAM_SUBMODE == 0x7E0011

    def test_ram_inidisp_address(self):
        """Test RAM_INIDISP address."""
        assert Mesen2Emulator.RAM_INIDISP == 0x7E001A

    def test_ram_indoors_address(self):
        """Test RAM_INDOORS address."""
        assert Mesen2Emulator.RAM_INDOORS == 0x7E001B

    def test_ram_area_id_address(self):
        """Test RAM_AREA_ID address."""
        assert Mesen2Emulator.RAM_AREA_ID == 0x7E008A

    def test_ram_link_x_address(self):
        """Test RAM_LINK_X address."""
        assert Mesen2Emulator.RAM_LINK_X == 0x7E0022

    def test_ram_link_y_address(self):
        """Test RAM_LINK_Y address."""
        assert Mesen2Emulator.RAM_LINK_Y == 0x7E0020

    def test_ram_health_address(self):
        """Test RAM_HEALTH address."""
        assert Mesen2Emulator.RAM_HEALTH == 0x7EF36D


class TestMesen2EmulatorCreation:
    """Test Mesen2Emulator creation."""

    def test_creation_default(self):
        """Test creating with default socket path."""
        emu = Mesen2Emulator()
        assert emu._socket_path is None

    def test_creation_with_socket_path(self):
        """Test creating with explicit socket path."""
        emu = Mesen2Emulator(socket_path="/tmp/test.sock")
        assert emu._socket_path == "/tmp/test.sock"

    def test_initial_status(self):
        """Test initial status is DISCONNECTED."""
        emu = Mesen2Emulator()
        assert emu._status == EmulatorStatus.DISCONNECTED

    def test_initial_bridge_none(self):
        """Test initial bridge is None."""
        emu = Mesen2Emulator()
        assert emu._bridge is None


class TestMesen2EmulatorDisconnect:
    """Test Mesen2Emulator disconnect method."""

    def test_disconnect_clears_bridge(self):
        """Test disconnect clears bridge."""
        emu = Mesen2Emulator()
        emu._bridge = Mock()
        emu.disconnect()
        assert emu._bridge is None

    def test_disconnect_sets_status(self):
        """Test disconnect sets DISCONNECTED status."""
        emu = Mesen2Emulator()
        emu._status = EmulatorStatus.CONNECTED
        emu.disconnect()
        assert emu._status == EmulatorStatus.DISCONNECTED


class TestMesen2EmulatorConnect:
    """Test Mesen2Emulator connect method."""

    def test_connect_sets_connecting(self):
        """Test connect sets CONNECTING status first."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_bridge = Mock()
            mock_bridge.is_connected.return_value = False
            mock_get_bridge.return_value = mock_bridge

            emu.connect()
            # After failed connect, status becomes ERROR

    def test_connect_success(self):
        """Test successful connect."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_bridge = Mock()
            mock_bridge.is_connected.return_value = True
            mock_get_bridge.return_value = mock_bridge

            result = emu.connect()
            assert result is True
            assert emu._status == EmulatorStatus.CONNECTED

    def test_connect_failure(self):
        """Test failed connect."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_bridge = Mock()
            mock_bridge.is_connected.return_value = False
            mock_get_bridge.return_value = mock_bridge

            result = emu.connect()
            assert result is False
            assert emu._status == EmulatorStatus.ERROR

    def test_connect_exception(self):
        """Test connect handles exception."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_get_bridge.side_effect = Exception("Connection error")

            result = emu.connect()
            assert result is False
            assert emu._status == EmulatorStatus.ERROR


class TestMesen2EmulatorIsConnected:
    """Test Mesen2Emulator is_connected method."""

    def test_is_connected_true(self):
        """Test is_connected returns True when connected."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_bridge = Mock()
            mock_bridge.is_connected.return_value = True
            mock_get_bridge.return_value = mock_bridge

            assert emu.is_connected() is True

    def test_is_connected_false(self):
        """Test is_connected returns False when not connected."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_bridge = Mock()
            mock_bridge.is_connected.return_value = False
            mock_get_bridge.return_value = mock_bridge

            assert emu.is_connected() is False

    def test_is_connected_exception(self):
        """Test is_connected returns False on exception."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_get_bridge.side_effect = Exception("Error")

            assert emu.is_connected() is False


class TestMesen2EmulatorGetStatus:
    """Test Mesen2Emulator get_status method."""

    def test_get_status_connected(self):
        """Test get_status returns CONNECTED when connected."""
        emu = Mesen2Emulator()

        with patch.object(emu, 'is_connected') as mock_connected:
            mock_connected.return_value = True

            assert emu.get_status() == EmulatorStatus.CONNECTED

    def test_get_status_not_connected(self):
        """Test get_status returns stored status when not connected."""
        emu = Mesen2Emulator()
        emu._status = EmulatorStatus.ERROR

        with patch.object(emu, 'is_connected') as mock_connected:
            mock_connected.return_value = False

            assert emu.get_status() == EmulatorStatus.ERROR


class TestMesen2EmulatorReadMemory:
    """Test Mesen2Emulator read_memory method."""

    def test_read_memory_size_1(self):
        """Test reading 1 byte."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_bridge = Mock()
            mock_bridge.read_memory.return_value = 0x09
            mock_get_bridge.return_value = mock_bridge

            result = emu.read_memory(0x7E0010, size=1)
            assert result.address == 0x7E0010
            assert result.value == 0x09
            assert result.size == 1

    def test_read_memory_size_2(self):
        """Test reading 2 bytes."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_bridge = Mock()
            mock_bridge.read_memory16.return_value = 0x0180
            mock_get_bridge.return_value = mock_bridge

            result = emu.read_memory(0x7E0022, size=2)
            assert result.value == 0x0180
            assert result.size == 2

    def test_read_memory_size_3(self):
        """Test reading 3 bytes."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_bridge = Mock()
            mock_bridge.read_memory24.return_value = 0x123456
            mock_get_bridge.return_value = mock_bridge

            result = emu.read_memory(0x7E0000, size=3)
            assert result.value == 0x123456
            assert result.size == 3

    def test_read_memory_invalid_size(self):
        """Test reading with invalid size raises error."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_bridge = Mock()
            mock_get_bridge.return_value = mock_bridge

            with pytest.raises(ValueError):
                emu.read_memory(0x7E0010, size=4)


class TestMesen2EmulatorWriteMemory:
    """Test Mesen2Emulator write_memory method."""

    def test_write_memory_size_1(self):
        """Test writing 1 byte."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_bridge = Mock()
            mock_get_bridge.return_value = mock_bridge

            result = emu.write_memory(0x7E0010, 0x09, size=1)
            assert result is True
            mock_bridge.write_memory.assert_called_once_with(0x7E0010, 0x09)

    def test_write_memory_size_2(self):
        """Test writing 2 bytes (little-endian)."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_bridge = Mock()
            mock_get_bridge.return_value = mock_bridge

            result = emu.write_memory(0x7E0022, 0x0180, size=2)
            assert result is True
            # Should write low byte then high byte
            assert mock_bridge.write_memory.call_count == 2

    def test_write_memory_invalid_size(self):
        """Test writing with invalid size returns False."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_bridge = Mock()
            mock_get_bridge.return_value = mock_bridge

            result = emu.write_memory(0x7E0010, 0x09, size=4)
            assert result is False

    def test_write_memory_exception(self):
        """Test write handles exception."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_bridge = Mock()
            mock_bridge.write_memory.side_effect = Exception("Write error")
            mock_get_bridge.return_value = mock_bridge

            result = emu.write_memory(0x7E0010, 0x09)
            assert result is False


class TestMesen2EmulatorPauseResume:
    """Test Mesen2Emulator pause/resume methods."""

    def test_pause_success(self):
        """Test pause returns True on success."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_bridge = Mock()
            mock_bridge.send_command.return_value = {"success": True}
            mock_get_bridge.return_value = mock_bridge

            result = emu.pause()
            assert result is True

    def test_pause_failure(self):
        """Test pause returns False on failure."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_bridge = Mock()
            mock_bridge.send_command.return_value = {"success": False}
            mock_get_bridge.return_value = mock_bridge

            result = emu.pause()
            assert result is False

    def test_resume_success(self):
        """Test resume returns True on success."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_bridge = Mock()
            mock_bridge.send_command.return_value = {"success": True}
            mock_get_bridge.return_value = mock_bridge

            result = emu.resume()
            assert result is True


class TestMesen2EmulatorStepFrame:
    """Test Mesen2Emulator step_frame method."""

    def test_step_frame_default(self):
        """Test step_frame with default count."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_bridge = Mock()
            mock_bridge.send_command.return_value = {"success": True}
            mock_get_bridge.return_value = mock_bridge

            result = emu.step_frame()
            assert result is True
            mock_bridge.send_command.assert_called_with("STEP", {"frames": 1})

    def test_step_frame_custom_count(self):
        """Test step_frame with custom count."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_bridge = Mock()
            mock_bridge.send_command.return_value = {"success": True}
            mock_get_bridge.return_value = mock_bridge

            result = emu.step_frame(count=60)
            assert result is True
            mock_bridge.send_command.assert_called_with("STEP", {"frames": 60})


class TestMesen2EmulatorInjectInput:
    """Test Mesen2Emulator inject_input method."""

    def test_inject_input_single_button(self):
        """Test injecting single button."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_bridge = Mock()
            mock_bridge.press_button.return_value = True
            mock_get_bridge.return_value = mock_bridge

            result = emu.inject_input(["A"])
            assert result is True

    def test_inject_input_normalizes_case(self):
        """Test input normalizes button case."""
        emu = Mesen2Emulator()

        with patch.object(emu, '_get_bridge') as mock_get_bridge:
            mock_bridge = Mock()
            mock_bridge.press_button.return_value = True
            mock_get_bridge.return_value = mock_bridge

            emu.inject_input(["up"])
            # Should normalize 'up' to 'Up'
            mock_bridge.press_button.assert_called_once()


class TestGetEmulatorFactory:
    """Test get_emulator factory function."""

    def test_get_mesen2_emulator(self):
        """Test getting Mesen2 emulator."""
        emu = get_emulator(backend="mesen2")
        assert isinstance(emu, Mesen2Emulator)

    def test_get_mesen2_with_kwargs(self):
        """Test getting Mesen2 with kwargs."""
        emu = get_emulator(backend="mesen2", socket_path="/tmp/test.sock")
        assert emu._socket_path == "/tmp/test.sock"

    def test_get_unknown_backend(self):
        """Test unknown backend raises ValueError."""
        with pytest.raises(ValueError):
            get_emulator(backend="unknown")


class TestEmulatorInterfaceAbstract:
    """Test EmulatorInterface abstract base class."""

    def test_cannot_instantiate_directly(self):
        """Test EmulatorInterface cannot be instantiated."""
        with pytest.raises(TypeError):
            EmulatorInterface()

    def test_mesen2_is_emulator_interface(self):
        """Test Mesen2Emulator is instance of EmulatorInterface."""
        emu = Mesen2Emulator()
        assert isinstance(emu, EmulatorInterface)


class TestGameStateSnapshotAllFields:
    """Test GameStateSnapshot with all fields."""

    def test_all_fields_accessible(self):
        """Test all fields are accessible."""
        snapshot = GameStateSnapshot(
            timestamp=1234.5,
            mode=0x09,
            submode=0x05,
            area=0x29,
            room=0x10,
            link_x=512,
            link_y=480,
            link_z=16,
            link_direction=2,
            link_state=0x05,
            indoors=False,
            inidisp=0x0F,
            health=48,
            max_health=64
        )
        assert snapshot.timestamp == 1234.5
        assert snapshot.mode == 0x09
        assert snapshot.submode == 0x05
        assert snapshot.area == 0x29
        assert snapshot.room == 0x10
        assert snapshot.link_x == 512
        assert snapshot.link_y == 480
        assert snapshot.link_z == 16
        assert snapshot.link_direction == 2
        assert snapshot.link_state == 0x05
        assert snapshot.indoors is False
        assert snapshot.inidisp == 0x0F
        assert snapshot.health == 48
        assert snapshot.max_health == 64
