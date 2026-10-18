#!/usr/bin/env python3
"""Attach-only palette regression; caller owns the private paused emulator.

All six songs are selected with controller input. Only the seven declared
inventory/selection bytes are fixture writes, restored in finally. No ROM,
SRAM file, CPU, position, cursor, story or save-state writes are performed.
--describe is file-only; this script never launches or stops Mesen.
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import subprocess
import sys
import time

sys.dont_write_bytecode = True
import new_items_prototype as items

native, menu = items.native, items.menu
FLUTE, SAVED = 0x7EF34C, 0x7EF3AB
FIXTURES = {FLUTE: 7, 0x7EF3A9: 1, 0x7EF348: 1, 0x7EF3AF: 1,
            0x7EF38B: 3, 0x7EF38D: 4}
ALLOWED = set(FIXTURES) | {SAVED}
BLUE = [0x2CD4, 0x2CD5, 0x2CE4, 0x2CE5]
# Fixed pre-song Menu_Palette contract, independent of the candidate ROM.
LEGACY_RGB = [0x814F16, 0x552903, 0, 0, 0xD51D00, 0xF9F9F9, 0, 0,
              0xD0A050, 0xF9F9F9, 0, 0, 0x5987E0, 0xF9F9F9, 0, 0,
              0x7B7B83, 0xBBBBBB, 0, 0, 0xA58100, 0xDFB93F, 0, 0,
              0x814F16, 0x013E6E, 0, 0, 0x15CD34, 0xF9F9F9, 0]
LEGACY_CGRAM = [((rgb >> 19) & 31) | (((rgb >> 11) & 31) << 5)
                | (((rgb >> 3) & 31) << 10) for rgb in LEGACY_RGB]
LEGACY_ICONS = {
    "Goldstar": (7, 20, [0x2C17, 0x3531, 0x2D40, 0x3541]),
    "Bunny Hood": (17, 10, [0x3469, 0x7469, 0x3479, 0x7479]),
    "Garo": (23, 10, [0x340D, 0x340E, 0x340F, 0x3425]),
    "Banana": (7, 22, [0x341E, 0x341F, 0x342E, 0x342F]),
    "Pineapple": (10, 22, [0x3D7C, 0x3D7D, 0x356C, 0x756C]),
}


def describe():
    return dict(native_executed=False, fixtures={f"{a:06X}": v for a, v in FIXTURES.items()},
                restored_bytes=[f"{a:06X}" for a in sorted(ALLOWED)],
                checks=["All 31 original BG3 palette words and five legacy icons",
                        "Six controller-selected songs retain blue Items/HUD ocarina",
                        "Time note uses four BG3 hole glyphs and purple OBJ pixels",
                        "Per-frame page-scroll/close palette trace and final blue HUD"],
                limits="Private fixture only; no acquisition, audio, save/reopen or crowded-room lease proof")


class SongColors(items.NewItemsFlow):
    def __init__(self, args, bridge):
        super().__init__(args, bridge)
        self.original = {}
        self.result.update(scope=describe(), transitions=[])
        self.result["scope"]["song_ids"] = list(range(args.first_song, 7))

    def write(self, address, value, reason):
        self.check_owner()
        native.require(address in ALLOWED and 0 <= value <= 255 and self.paused(),
                       "Write outside paused song-color inventory fixture")
        entry = dict(address=f"{address:06X}", before=self.r(address), value=value, reason=reason)
        self.result["writes"].append(entry)
        native.require(self.b.write_memory(address, value), "Fixture write rejected")
        entry["readback"] = self.r(address)
        native.require(entry["readback"] == value, "Fixture readback differs")

    def word(self, address, memory=None):
        data = self.b.read_block(address, 2, memory)
        native.require(len(data) == 2, "Short word read")
        return int.from_bytes(data, "little")

    def palette(self):
        data = self.b.read_block(2, 62, "CGRAM")
        native.require(len(data) == 62, "Short hardware CGRAM read")
        return [int.from_bytes(data[i:i + 2], "little") for i in range(0, 62, 2)]

    def legacy_icon(self, name):
        x, y, expected = LEGACY_ICONS[name]
        self.check(name + " original tile/palette words",
                   self.words(x, y, 2) + self.words(x, y + 1, 2), expected)

    def blue_hud(self, label):
        self.check(label, [self.word(a) for a in (0x7EC776, 0x7EC778, 0x7EC7B6, 0x7EC7B8)], BLUE)

    def blue_items(self):
        self.check("Items ocarina remains blue", self.words(7, 17, 2) + self.words(7, 18, 2), BLUE)

    def select_song(self, song):
        native.require(self.screen() == "equipment", "Need Equipment screen")
        for _ in range(4):
            if 12 <= self.r(menu.CURSOR) <= 17:
                break
            self.tap("Down")
        native.require(12 <= self.r(menu.CURSOR) <= 17, "Song row is unreachable")
        for _ in range(6):
            if self.r(menu.CURSOR) == song + 11:
                break
            self.tap("Right")
        self.check("Song cursor", self.r(menu.CURSOR), song + 11)
        self.tap("A")
        self.check("Controller selects current/saved song", [self.r(0x7E030F), self.r(SAVED)], [song, song])
        names = ("SONG: HEALING", "SONG: STORMS", "SONG: SOARING", "SONG: TIME",
                 "SONG: SECRETS", "ELEGY: STONE")
        self.check("Selected song footer", self.text(9, 26, 14).strip(), names[song - 1])

    def purple_note(self):
        # FRAME can pause during NMI itself, between restoring a lease and
        # uploading this frame's note. Execute to the native post-update point
        # without modifying CPU state, then sample completed hardware uploads.
        self.check_owner()
        self.input("")
        before = native.number(self.b.get_rom_info()["frameCount"])
        cpu = self.run_to({0x008144})
        after = native.number(self.b.get_rom_info()["frameCount"])
        self.result.setdefault("display_boundaries", []).append(dict(before_frame=before, after_frame=after, cpu=cpu))
        # Mutable tracker/lease fields remain diagnostic only.
        self.result.setdefault("tracker_snapshots", []).append(self.block(0x7F5700, 64).hex())
        address = (0x6C00 + 0x4A2 // 2) * 2
        self.check("Hardware Time note hole glyphs",
                   [self.word(a, "VRAM") for a in (address, address + 2, address + 64, address + 66)],
                   [0x2D80, 0x2D81, 0x2D82, 0x2D83])
        oam = self.b.read_block(0, 544, "OAM")
        native.require(len(oam) == 544, "Short hardware OAM read")
        x, y = oam[0] | ((oam[512] & 1) << 8), oam[1] + 1
        self.check("Displayed Time note position and16x16 size", [x, y, oam[512] & 2], [136, 126, 2])
        self.check("Displayed Time note OBJ priority", oam[3] & 0x30, 0x30)
        chosen = (oam[3] >> 1) & 7
        purple = self.word((0x88 + chosen * 16) * 2, "CGRAM")
        self.check("Leased OBJ foreground is Time purple", purple, 0x6DD5)
        raw = self.b.screenshot()
        native.require(bool(raw), "Missing Time note screenshot")
        path = self.a.output / "time-purple-note.png"
        path.write_bytes(raw)
        self.result["screenshots"].append(str(path))
        from PIL import Image
        picture = Image.open(io.BytesIO(raw)).convert("RGB")
        self.check("Unfiltered screenshot dimensions", list(picture.size), [256, 224])
        # Mesen color conversion can expand five bits by replication or shift.
        expected = tuple(((purple >> shift) & 31) * 8 for shift in (0, 5, 10))
        hits = sum(all(abs(channel - target) <= 7 for channel, target in zip(pixel, expected))
                   for pixel in picture.crop((x, y, x + 16, y + 16)).getdata())
        self.check("All 40 note foreground pixels are purple", hits, 40)
        self.result["purple_lease"] = dict(palette=chosen, cgram_word=purple, x=x, y=y,
                                          tile=oam[2] | ((oam[3] & 1) << 8), pixels=hits)

    def trace_transition(self, button, destination, label):
        # One FRAME at a time so a temporary palette stomp cannot hide between
        # stable screenshots. Input stays held for two frames, then releases.
        trace = []
        self.result["transitions"].append(dict(label=label, frames=trace))
        self.advance("", 2)
        for step in range(180):
            self.advance(button if step < 2 else "", 1)
            sample = dict(frame=step, screen=self.screen(), module=self.r(0x7E0010),
                          state=self.r(menu.MENU), palette=self.palette(),
                          active=[self.word(0x7F5712), self.word(0x7F5714)])
            trace.append(sample)
            if step == 12:
                self.shot(label.lower().replace(" ", "-") + "-frame12")
            if sample["module"] == 0x0E:
                native.require(sample["palette"] == LEGACY_CGRAM,
                               f"Original BG3 palette changed during {label}, frame {step}")
            if step > 1 and sample["screen"] == destination:
                break
        self.check(label + " destination", self.screen(), destination)
        self.advance("", 2)
        if destination == "gameplay":
            self.blue_hud("Close rebuild retains blue HUD")

    def run(self):
        self.ready()
        native.require(self.r(0x7E02B2) in (0, 6), "Start unmasked; mask HUD is a separate contract")
        self.original = {address: self.r(address) for address in ALLOWED}
        for address, value in FIXTURES.items():
            self.write(address, value, "Declared private song-color inventory fixture")
        self.equip(0x0D)
        for song in range(self.a.first_song, 7):
            self.tap("Start"); self.wait_screen("items")
            self.blue_items()
            if song == self.a.first_song:
                self.legacy_icon("Goldstar")
                self.check("All 31 original Items CGRAM words", self.palette(), LEGACY_CGRAM)
            self.tap("L"); self.wait_screen("equipment")
            self.select_song(song)
            self.check("All 31 original Equipment CGRAM words", self.palette(), LEGACY_CGRAM)
            if song == 4:
                for name in ("Bunny Hood", "Garo", "Banana", "Pineapple"):
                    self.legacy_icon(name)
                self.purple_note()
                self.trace_transition("R", "items", "Equipment to Items")
                self.blue_items()
                self.trace_transition("L", "equipment", "Items to Equipment")
                self.purple_note()
                self.trace_transition("Start", "gameplay", "Time Equipment close")
            else:
                self.tap("Start"); self.wait_screen("gameplay")
            self.blue_hud(f"Song {song} retains blue HUD")
        # The next loop's Items page checked songs1..5; check song6 explicitly.
        self.tap("Start"); self.wait_screen("items")
        self.blue_items()
        self.tap("Start"); self.wait_screen("gameplay")
        self.result["runtime_checks_passed"] = True

    def restore(self):
        # Ownership is rechecked before each write; never touch a replaced session.
        for address, value in self.original.items():
            self.write(address, value, "Restore exact pre-test inventory/selection byte")
        self.result["fixture_cleanup"].append(dict(restored=[f"{a:06X}" for a in self.original]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--execute-fixtures", action="store_true")
    parser.add_argument("--session-json", "--session", type=Path, dest="session_json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--first-song", type=int, choices=(1, 4), default=1,
                        help="Use4 to finish Time/Secrets/Stone after retained1..3 evidence")
    parser.add_argument("--client-root", type=Path,
                        default=Path.home() / "src/hobby/mesen2-oos/tools/oos_client")
    args = parser.parse_args()
    if args.describe:
        print(json.dumps(describe(), indent=2)); return 0
    native.require(args.execute_fixtures and args.session_json and args.output,
                   "Require --execute-fixtures, --session-json and a new --output directory")
    session = json.loads(args.session_json.read_text())
    for key in ("socket", "pid", "owner", "rom_sha1"):
        setattr(args, key, session[key])
    args.pid = native.number(args.pid)
    for key in ("status_file", "owner_file", "owned_rom", "symbols"):
        setattr(args, key, Path(session[key]).resolve())
    native.require(args.socket.startswith("/tmp/mesen2-portal-songs-")
                   and args.owner.startswith("codex-portal-songs-") and "oos-rc-play" not in str(args),
                   "Only the explicit task-owned portal/songs session is admitted")
    native.require(native.digest(args.owned_rom.read_bytes(), "sha1") == args.rom_sha1.lower(),
                   "Private ROM differs from the session SHA1")
    args.rom_sha256 = native.digest(args.owned_rom.read_bytes())
    args.symbols_sha256 = native.digest(args.symbols.read_bytes())
    if session.get("symbols_sha256"):
        native.require(args.symbols_sha256 == session["symbols_sha256"], "Symbols hash differs")
    command = subprocess.check_output(["ps", "-o", "command=", "-p", str(args.pid)], text=True)
    native.require("--headless" in command and str(args.owned_rom) in command,
                   "PID is not the explicit private headless ROM process")
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.client_root))
    from mesen2_client_lib.bridge import MesenBridge
    flow = SongColors(args, MesenBridge(args.socket, auto_reconnect=False, max_retries=0))
    flow.result["inputs"] = vars(args)
    admitted = False
    try:
        flow.check_owner()
        native.require(flow.paused() and not flow.b.list_breakpoints(),
                       "Need paused private session with no breakpoints")
        admitted = True
        flow.run()
    except Exception as error:
        flow.result["error"] = repr(error)
    finally:
        if admitted:
            try:
                flow.check_owner(); flow.input("")
                if not flow.paused():
                    native.require(flow.b.pause(), "Cleanup pause rejected")
                until = time.monotonic() + 5
                while not flow.paused() and time.monotonic() < until:
                    time.sleep(.01)
                native.require(flow.paused(), "Cleanup pause did not complete")
                flow.restore()
            except Exception as error:
                flow.result["cleanup_errors"].append(repr(error))
        flow.result["passed"] = bool(flow.result.get("runtime_checks_passed")
                                     and not flow.result["cleanup_errors"])
        (args.output / "RESULT.json").write_text(json.dumps(flow.result, indent=2, default=str) + "\n")
    print(json.dumps(dict(passed=flow.result["passed"], result=str(args.output / "RESULT.json"))))
    return 0 if flow.result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
