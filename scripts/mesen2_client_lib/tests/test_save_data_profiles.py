from mesen2_client_lib.save_data_profiles import SaveDataProfile, apply_profile


class DummyBridge:
    def __init__(self):
        self.writes8 = []
        self.writes16 = []

    def write_memory(self, addr: int, value: int, memtype=None):
        self.writes8.append((addr, value, memtype))
        return True

    def write_memory16(self, addr: int, value: int, memtype=None):
        self.writes16.append((addr, value, memtype))
        return True


class DummyClient:
    def __init__(self):
        self.items = {}
        self.flags = {}
        self.bridge = DummyBridge()

    def set_item(self, name: str, value: int):
        self.items[name] = value
        return True

    def set_flag(self, name: str, value):
        self.flags[name] = bool(value)
        return True


def test_apply_profile_items_flags_writes(tmp_path):
    p = tmp_path / "p.json"
    prof = SaveDataProfile(
        path=p,
        data={
            "version": 1,
            "id": "t",
            "items": {"flute": 4, "rupees": 999},
            "flags": {"Story_IntroComplete": True},
            "writes": [
                {"addr": "0x7E030F", "type": "u8", "value": "0x03"},
                {"addr": "$7E0022", "type": "u16", "value": 0x1234, "memtype": "WRAM"},
            ],
        },
    )

    c = DummyClient()
    actions = apply_profile(c, prof, dry_run=False)

    assert c.items["flute"] == 4
    assert c.items["rupees"] == 999
    assert c.flags["Story_IntroComplete"] is True
    assert (0x7E030F, 0x03, None) in c.bridge.writes8
    assert (0x7E0022, 0x1234, "WRAM") in c.bridge.writes16
    assert any(a.startswith("item:flute=") for a in actions)
