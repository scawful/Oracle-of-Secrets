"""Tests for emulator_abstraction module.

These tests verify the campaign infrastructure without requiring
a running emulator (mock-based tests).
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
import tempfile

# Import the modules we're testing
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.emulator_abstraction import (
    EmulatorInterface,
    EmulatorStatus,
    GameStateSnapshot,
    Mesen2Emulator,
    MemoryRead,
    get_emulator,
)


class TestMemoryRead:
    """Tests for MemoryRead dataclass."""

    def test_basic_read(self):
        """Test basic memory read creation."""
        read = MemoryRead(address=0x7E0010, value=0x09, size=1)
        assert read.address == 0x7E0010
        assert read.value == 0x09
        assert read.size == 1

    def test_value16_property(self):
        """Test 16-bit value interpretation."""
        read = MemoryRead(address=0x7E0022, value=0x0180, size=2)
        assert read.value16 == 0x0180

    def test_value24_property(self):
        """Test 24-bit value interpretation."""
        read = MemoryRead(address=0x7E0000, value=0x123456, size=3)
        assert read.value24 == 0x123456


class TestGameStateSnapshot:
    """Tests for GameStateSnapshot dataclass."""

    @pytest.fixture
    def overworld_state(self):
        """Create an overworld game state."""
        return GameStateSnapshot(
            timestamp=1000.0,
            mode=0x09,
            submode=0x00,
            area=0x29,
            room=0x00,
            link_x=384,
            link_y=512,
            link_z=0,
            link_direction=0x02,
            link_state=0x01,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )

    @pytest.fixture
    def dungeon_state(self):
        """Create a dungeon game state."""
        return GameStateSnapshot(
            timestamp=1001.0,
            mode=0x07,
            submode=0x00,
            area=0x00,
            room=0x27,
            link_x=256,
            link_y=320,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=True,
            inidisp=0x0F,
            health=20,
            max_health=24,
        )

    @pytest.fixture
    def black_screen_state(self):
        """Create a black screen state."""
        return GameStateSnapshot(
            timestamp=1002.0,
            mode=0x07,
            submode=0x0F,
            area=0x00,
            room=0x12,
            link_x=0,
            link_y=0,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=True,
            inidisp=0x80,  # Screen forced off
            health=24,
            max_health=24,
        )

    def test_is_playing_overworld(self, overworld_state):
        """Test is_playing on overworld."""
        assert overworld_state.is_playing is True

    def test_is_playing_dungeon(self, dungeon_state):
        """Test is_playing in dungeon."""
        assert dungeon_state.is_playing is True

    def test_is_overworld(self, overworld_state, dungeon_state):
        """Test is_overworld detection."""
        assert overworld_state.is_overworld is True
        assert dungeon_state.is_overworld is False

    def test_is_dungeon(self, overworld_state, dungeon_state):
        """Test is_dungeon detection."""
        assert dungeon_state.is_dungeon is True
        assert overworld_state.is_dungeon is False

    def test_is_black_screen(self, black_screen_state, overworld_state):
        """Test black screen detection."""
        assert black_screen_state.is_black_screen is True
        assert overworld_state.is_black_screen is False

    def test_position_tuple(self, overworld_state):
        """Test position property."""
        assert overworld_state.position == (384, 512)


class TestEmulatorStatus:
    """Tests for EmulatorStatus enum."""

    def test_status_values(self):
        """Test all status values exist."""
        assert EmulatorStatus.DISCONNECTED == 0
        assert EmulatorStatus.CONNECTING == 1
        assert EmulatorStatus.CONNECTED == 2
        assert EmulatorStatus.RUNNING == 3
        assert EmulatorStatus.PAUSED == 4
        assert EmulatorStatus.ERROR == 5


class TestMesen2EmulatorWithMocks:
    """Tests for Mesen2Emulator using mocks."""

    @pytest.fixture
    def mock_bridge(self):
        """Create a mock MesenBridge."""
        bridge = Mock()
        bridge.is_connected.return_value = True
        bridge.read_memory.return_value = 0x09
        bridge.read_memory16.return_value = 0x0180
        bridge.read_memory24.return_value = 0x123456
        bridge.press_button.return_value = True
        bridge.send_command.return_value = {"success": True}
        return bridge

    @pytest.fixture
    def emulator_with_mock(self, mock_bridge):
        """Create Mesen2Emulator with mocked bridge."""
        emu = Mesen2Emulator()
        emu._bridge = mock_bridge
        return emu

    def test_is_connected(self, emulator_with_mock):
        """Test connection check."""
        assert emulator_with_mock.is_connected() is True

    def test_read_memory_byte(self, emulator_with_mock, mock_bridge):
        """Test reading a single byte."""
        result = emulator_with_mock.read_memory(0x7E0010, size=1)
        assert result.value == 0x09
        mock_bridge.read_memory.assert_called_with(0x7E0010)

    def test_read_memory_word(self, emulator_with_mock, mock_bridge):
        """Test reading a 16-bit word."""
        result = emulator_with_mock.read_memory(0x7E0022, size=2)
        assert result.value == 0x0180
        mock_bridge.read_memory16.assert_called_with(0x7E0022)

    def test_read_memory_long(self, emulator_with_mock, mock_bridge):
        """Test reading a 24-bit value."""
        result = emulator_with_mock.read_memory(0x7E0000, size=3)
        assert result.value == 0x123456
        mock_bridge.read_memory24.assert_called_with(0x7E0000)

    def test_read_state(self, emulator_with_mock, mock_bridge):
        """Test reading full game state."""
        # Setup mock return values for state reading
        mock_bridge.read_memory.side_effect = lambda addr: {
            0x7E0010: 0x09,  # mode
            0x7E0011: 0x00,  # submode
            0x7E008A: 0x29,  # area
            0x7E00A0: 0x00,  # room
            0x7E002F: 0x02,  # direction
            0x7E005D: 0x01,  # state
            0x7E001B: 0x00,  # indoors
            0x7E001A: 0x0F,  # inidisp
            0x7EF36D: 24,    # health
            0x7EF36C: 24,    # max_health
        }.get(addr, 0)

        mock_bridge.read_memory16.side_effect = lambda addr: {
            0x7E0022: 384,   # x
            0x7E0020: 512,   # y
            0x7E0024: 0,     # z
            0x7E00A4: 0,     # room_id
        }.get(addr, 0)

        state = emulator_with_mock.read_state()

        assert state.mode == 0x09
        assert state.area == 0x29
        assert state.link_x == 384
        assert state.link_y == 512
        assert state.is_overworld is True

    def test_inject_input(self, emulator_with_mock, mock_bridge):
        """Test input injection."""
        result = emulator_with_mock.inject_input(["RIGHT"], frames=30)
        assert result is True
        mock_bridge.press_button.assert_called_with("Right", frames=30)

    def test_save_state(self, emulator_with_mock, mock_bridge):
        """Test state saving."""
        mock_bridge.save_state.return_value = True
        result = emulator_with_mock.save_state("test")
        expected = str(Path(tempfile.gettempdir()) / "oos_campaign" / "states" / "test.mss")
        assert result == expected
        mock_bridge.save_state.assert_called_with(path=expected)

    def test_p_watch_start(self, emulator_with_mock, mock_bridge):
        """Test P register watch (Mesen2-OOS extension)."""
        result = emulator_with_mock.p_watch_start(depth=500)
        assert result is True
        mock_bridge.send_command.assert_called_with("P_WATCH_START", {"depth": 500})


class TestGetEmulatorFactory:
    """Tests for the get_emulator factory function."""

    def test_get_mesen2(self):
        """Test creating Mesen2 emulator."""
        emu = get_emulator("mesen2")
        assert isinstance(emu, Mesen2Emulator)

    def test_get_unknown_raises(self):
        """Test unknown backend raises ValueError."""
        with pytest.raises(ValueError, match="Unknown emulator backend"):
            get_emulator("unknown")


class TestRAMAddresses:
    """Tests that RAM address constants are correct."""

    def test_mode_address(self):
        """Verify GameMode address."""
        assert Mesen2Emulator.RAM_MODE == 0x7E0010

    def test_submode_address(self):
        """Verify Submodule address."""
        assert Mesen2Emulator.RAM_SUBMODE == 0x7E0011

    def test_inidisp_address(self):
        """Verify INIDISP address."""
        assert Mesen2Emulator.RAM_INIDISP == 0x7E001A

    def test_link_position_addresses(self):
        """Verify Link position addresses."""
        assert Mesen2Emulator.RAM_LINK_X == 0x7E0022
        assert Mesen2Emulator.RAM_LINK_Y == 0x7E0020
        assert Mesen2Emulator.RAM_LINK_Z == 0x7E0024
