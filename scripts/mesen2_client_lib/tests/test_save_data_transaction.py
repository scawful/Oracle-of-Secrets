from pathlib import Path

from mesen2_client_lib.cart_sram import (
    apply_inverse_checksum,
    read_slot_saveblock,
    resolve_active_slot,
    write_slot_saveblock,
)
from mesen2_client_lib.constants import ITEMS, SAVEFILE_WRAM_SIZE, SAVEFILE_WRAM_START, STORY_FLAGS
from mesen2_client_lib.save_data_profiles import SaveDataProfile
from mesen2_client_lib.save_data_transaction import apply_profile_transaction


class FakeBridge:
    def __init__(self):
        self.wram: dict[int, int] = {}
        self.sram = bytearray(0x2000)
        # Active slot table index value for slot 1 in ALTTP/OOS.
        self.write_memory16(0x701FFE, 0x0002)

    def read_memory(self, address: int, memtype: str | None = None) -> int:
        mt = (memtype or "WRAM").upper()
        if mt == "SRAM":
            if 0 <= address < len(self.sram):
                return self.sram[address]
            return 0
        return self.wram.get(address, 0)

    def read_memory16(self, address: int, memtype: str | None = None) -> int:
        lo = self.read_memory(address, memtype=memtype)
        hi = self.read_memory(address + 1, memtype=memtype)
        return lo | (hi << 8)

    def write_memory(self, address: int, value: int, memtype: str | None = None) -> bool:
        mt = (memtype or "WRAM").upper()
        byte = value & 0xFF
        if mt == "SRAM":
            if 0 <= address < len(self.sram):
                self.sram[address] = byte
                return True
            return False
        self.wram[address] = byte
        return True

    def write_memory16(self, address: int, value: int, memtype: str | None = None) -> bool:
        lo_ok = self.write_memory(address, value & 0xFF, memtype=memtype)
        hi_ok = self.write_memory(address + 1, (value >> 8) & 0xFF, memtype=memtype)
        return lo_ok and hi_ok

    def read_block(self, address: int, length: int, memtype: str | None = None) -> bytes:
        mt = (memtype or "WRAM").upper()
        if mt == "SRAM":
            return bytes(self.sram[address : address + length])
        return bytes(self.read_memory(address + i, memtype=memtype) for i in range(length))

    def write_block(self, address: int, data: bytes, memtype: str | None = None) -> bool:
        mt = (memtype or "WRAM").upper()
        if mt == "SRAM":
            end = address + len(data)
            if address < 0 or end > len(self.sram):
                return False
            self.sram[address:end] = data
            return True
        for i, byte in enumerate(data):
            self.write_memory(address + i, int(byte), memtype=memtype)
        return True


class FakeClient:
    def __init__(self):
        self.bridge = FakeBridge()

    def set_item(self, item_name: str, value: int) -> bool:
        addr, _, _ = ITEMS[item_name]
        if item_name == "rupees":
            return self.bridge.write_memory16(addr, value)
        return self.bridge.write_memory(addr, value)

    def set_flag(self, flag_name: str, value: int | bool) -> bool:
        addr, _, mask_or_values = STORY_FLAGS[flag_name]
        if isinstance(mask_or_values, int):
            current = self.bridge.read_memory(addr)
            if value:
                return self.bridge.write_memory(addr, current | mask_or_values)
            return self.bridge.write_memory(addr, current & (~mask_or_values & 0xFF))
        return self.bridge.write_memory(addr, int(value) & 0xFF)

    def active_save_slot(self) -> int:
        return resolve_active_slot(self.bridge)

    def read_save_data(self) -> bytes:
        return self.bridge.read_block(SAVEFILE_WRAM_START, SAVEFILE_WRAM_SIZE, memtype="WRAM")

    def write_save_data(self, blob: bytes) -> None:
        self.bridge.write_block(SAVEFILE_WRAM_START, blob, memtype="WRAM")

    def sync_wram_save_to_sram(self, slot: int | None = None) -> dict:
        slot_id = int(slot or self.active_save_slot())
        blob = apply_inverse_checksum(self.read_save_data())
        self.write_save_data(blob)
        write_slot_saveblock(self.bridge, slot_id, blob, write_mirror=True)
        return {"slot": slot_id, "bytes": len(blob)}


def test_profile_transaction_persists_flute_and_warns_for_volatile():
    client = FakeClient()
    profile = SaveDataProfile(
        path=Path("soaring_debug.json"),
        data={
            "version": 1,
            "id": "soaring_debug",
            "items": {
                "flute": 4,
                "ocarina_song": 3,
            },
        },
    )

    result = apply_profile_transaction(client, profile, persist=True, verify=True)

    assert result["ok"] is True
    assert result["persisted"] is True
    assert result["slot"] == 1
    assert result["targets"]["persistent"] == 1
    assert result["targets"]["volatile"] == 1
    assert result["warnings"]

    slot1 = read_slot_saveblock(client.bridge, 1)
    assert slot1[0x34C] == 0x04
    assert client.bridge.read_memory(0x7E030F) == 0x03


def test_profile_transaction_preserves_full_byte_flag_value():
    client = FakeClient()
    profile = SaveDataProfile(
        path=Path("story_state.json"),
        data={
            "version": 1,
            "id": "story_state",
            "flags": {
                "gamestate": 3,
            },
        },
    )

    result = apply_profile_transaction(client, profile, persist=True, verify=True)

    assert result["ok"] is True
    slot1 = read_slot_saveblock(client.bridge, 1)
    assert slot1[0x3C5] == 0x03
