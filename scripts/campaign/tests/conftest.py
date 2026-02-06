"""Pytest configuration and shared fixtures for campaign tests."""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@pytest.fixture
def mock_mesen_bridge():
    """Create a mock MesenBridge for testing without emulator.

    This fixture provides a fully-mocked MesenBridge that simulates
    typical Mesen2 responses.
    """
    bridge = Mock()
    bridge.is_connected.return_value = True

    # Default memory values (overworld state)
    memory_map = {
        0x7E0010: 0x09,    # mode (overworld)
        0x7E0011: 0x00,    # submode
        0x7E001A: 0x0F,    # inidisp (screen on)
        0x7E001B: 0x00,    # indoors (false)
        0x7E008A: 0x29,    # area (village center)
        0x7E00A0: 0x00,    # room layout
        0x7E002F: 0x02,    # direction (down)
        0x7E005D: 0x00,    # state (standing)
        0x7EF36D: 24,      # health
        0x7EF36C: 24,      # max health
    }

    memory16_map = {
        0x7E0022: 384,     # link x
        0x7E0020: 512,     # link y
        0x7E0024: 0,       # link z
        0x7E00A4: 0,       # room id
    }

    bridge.read_memory.side_effect = lambda addr: memory_map.get(addr, 0)
    bridge.read_memory16.side_effect = lambda addr: memory16_map.get(addr, 0)
    bridge.read_memory24.return_value = 0

    bridge.send_command.return_value = {"success": True}

    return bridge


@pytest.fixture
def sample_overworld_state():
    """Sample overworld state data for testing."""
    from scripts.campaign.emulator_abstraction import GameStateSnapshot

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
        link_state=0x00,
        indoors=False,
        inidisp=0x0F,
        health=24,
        max_health=24,
    )


@pytest.fixture
def sample_dungeon_state():
    """Sample dungeon state data for testing."""
    from scripts.campaign.emulator_abstraction import GameStateSnapshot

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
        raw_data={"room_id": 0x27},
    )


@pytest.fixture
def sample_black_screen_state():
    """Sample black screen state for testing."""
    from scripts.campaign.emulator_abstraction import GameStateSnapshot

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
        inidisp=0x80,
        health=24,
        max_health=24,
    )
