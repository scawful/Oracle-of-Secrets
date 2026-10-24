#!/usr/bin/env python3
"""Native SongBits check: old learned-count saves load as one bit per song.

Adapted from PR #220 for the current four-song menu.
The caller launches one private headless Mesen2 instance per ROM and holds the
heavy lock. Fixture writes are limited to cart SRAM slot 1 (main + mirror,
checksum fixed), built from a copy of --base-srm with the case's $7EF34C,
SongBits ($7EF3B1) and SavedOcarinaSong ($7EF3AB); controller input; and one
`warp-entrance 0x6B` (Mask Salesman shop) for the teacher case. Each case
resets the console and loads file 1 through title and file select, so the
conversion runs on the native file-load path.

--mode control runs the same cases on the pre-change ROM: SongBits stays 0 and
the old count drives the menu, so converted saves must look the same there.
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import subprocess
import sys
import time

MODULE, SUBMODULE = 0x7E0010, 0x7E0011
FLUTE, BITS, SAVED, CURRENT = 0x7EF34C, 0x7EF3B1, 0x7EF3AB, 0x7E030F
CURSOR, MENU, PAGE, CHOICE = 0x7E020B, 0x7E0200, 0x7E0731, 0x7E1CE8
ROOM = 0x7E00A0
SRAM = "SnesSaveRam"
SLOT1, MIRROR = 0x0000, 0x0F00
SONG_SLOTS = range(11, 15)          # Equipment slots 11-14 = songs 1-4
REPO = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def count_to_bits(count):
    """The conversion rule: count >= 2 means songs 1..count-1, capped at four."""
    return 0 if count < 2 else (1 << (min(count, 5) - 1)) - 1


def lowest(bits):
    return next((song for song in range(1, 5) if bits >> (song - 1) & 1), 0)


class SongBitsRun:
    def __init__(self, args, bridge):
        self.a, self.b = args, bridge
        self.rom = args.rom.read_bytes()
        self.symbols = {}
        for line in args.symbols.read_text().splitlines():
            parts = line.split()
            if len(parts) == 2 and ":" in parts[0] and not parts[1].startswith(":"):
                bank, offset = parts[0].split(":")
                self.symbols[parts[1].removeprefix("Oracle_")] = int(bank + offset, 16)
        self.base = args.base_srm.read_bytes()
        require(len(self.base) >= 0x2000, "Base .srm is shorter than 8 KiB")
        self.result = dict(mode=args.mode, rom=str(args.rom), base_srm=str(args.base_srm),
                           cases=[], checks=[], passed=False)
        self.case = None

    # --- emulator plumbing -------------------------------------------------
    def r(self, address):
        return self.b.read_memory(address) & 0xFF

    def block(self, address, size, memtype=None):
        data = bytes(self.b.read_block(address, size, memtype))
        require(len(data) == size, f"Short read at {address:06X}")
        return data

    def paused(self):
        reply = self.b.send_command("STATE")
        state = reply.get("data", {})
        if isinstance(state, str):
            state = json.loads(state)
        return state.get("paused") is True

    def settle_pause(self):
        self.b.pause()
        until = time.monotonic() + 5
        while not self.paused() and time.monotonic() < until:
            time.sleep(.01)
        require(self.paused(), "Pause did not settle")

    def info(self):
        reply = self.b.send_command("ROMINFO")
        require(reply.get("success"), "ROMINFO rejected")
        info = reply.get("data", {})
        return json.loads(info) if isinstance(info, str) else info

    def frames(self):
        return int(self.info()["frameCount"])

    def advance(self, buttons="", count=2):
        require(self.paused(), "FRAME needs a paused CPU")
        reply = self.b.send_command("INPUT", {"buttons": buttons, "frames": "0", "player": "0"})
        require(reply.get("success"), "INPUT rejected")
        before = self.frames()
        require(self.b.send_command("FRAME", {"count": str(count)}).get("success"), "FRAME rejected")
        until = time.monotonic() + 10
        while time.monotonic() < until:
            if self.frames() >= before + count and self.paused():
                return
            time.sleep(.01)
        raise RuntimeError("FRAME timeout")

    def tap(self, button, settle=3):
        self.advance("", 2)
        self.advance(button, 2)
        self.advance("", settle)

    def until(self, predicate, label, frames=600, step=4):
        for _ in range(frames // step + 1):
            if predicate():
                return
            self.advance("", step)
        require(predicate(), label)

    def mode(self):
        return self.r(MODULE), self.r(SUBMODULE)

    def screen(self):
        if self.r(MODULE) != 0x0E:
            return "gameplay"
        if self.r(MENU) == 4:
            return "items"
        if self.r(MENU) == 6:
            return "equipment" if self.r(PAGE) else "quest"
        return f"menu-{self.r(MENU):02X}"

    def ready(self):
        self.until(lambda: self.r(MODULE) in (0x07, 0x09) and self.r(SUBMODULE) == 0,
                   "Gameplay did not settle", 1200)
        self.advance("", 30)

    def shot(self, name):
        path = self.a.output / f"{self.a.mode}-{name}.ppm"
        code = "local target=" + json.dumps(str(path)) + '''
local callback
callback=emu.addEventCallback(function()
  local size,pixels=emu.getScreenSize(),emu.getScreenBuffer()
  local out=assert(io.open(target,'wb'))
  out:write('P6\\n'..size.width..' '..size.height..'\\n255\\n')
  for y=0,size.height-1 do
    local row={}
    for x=0,size.width-1 do
      local p=pixels[y*size.width+x+1]
      row[#row+1]=string.char((p>>16)&255,(p>>8)&255,p&255)
    end
    out:write(table.concat(row))
  end
  out:close()
  emu.removeEventCallback(callback,emu.eventType.endFrame)
end,emu.eventType.endFrame)
'''
        reply = self.b.execute_lua(base64.b64encode(code.encode()).decode())
        require(reply.get("success"), "Rendered-frame callback rejected")
        self.advance("", 1)
        require(path.is_file() and path.stat().st_size > 100, "Rendered frame missing")
        self.case.setdefault("screenshots", []).append(path.name)

    # --- checks -------------------------------------------------------------
    def check(self, label, actual, expected):
        passed = actual == expected
        entry = dict(case=self.case["label"], name=label, actual=actual, expected=expected, passed=passed)
        self.result["checks"].append(entry)
        print(("PASS " if passed else "FAIL ") + f"[{self.case['label']}] {label}: {actual!r}"
              + ("" if passed else f" != {expected!r}"), flush=True)
        require(passed, f"{label}: {actual!r} != {expected!r}")

    def save_state_bytes(self):
        return dict(flute=self.r(FLUTE), bits=self.r(BITS), saved=self.r(SAVED), current=self.r(CURRENT))

    # --- fixtures -----------------------------------------------------------
    def write_slot1(self, flute, bits, saved):
        slot = bytearray(self.base[SLOT1:SLOT1 + 0x500])
        slot[0x34C], slot[0x3B1], slot[0x3AB] = flute, bits, saved
        total = sum(slot[i] | slot[i + 1] << 8 for i in range(0, 0x4FE, 2)) & 0xFFFF
        inverse = (0x5A5A - total) & 0xFFFF
        slot[0x4FE], slot[0x4FF] = inverse & 0xFF, inverse >> 8
        for base in (SLOT1, MIRROR):
            require(self.b.write_block(base, bytes(slot), SRAM), "SRAM write rejected")
            require(self.block(base, 0x500, SRAM) == bytes(slot), "SRAM readback differs")
        self.case["sram_fixture"] = dict(flute=flute, bits=bits, saved=saved, checksum=f"{inverse:04X}")

    def boot_file1(self):
        require(self.b.reset(), "Reset rejected")
        self.settle_pause()
        self.advance("", 120)
        self.until(lambda: self.mode() == (0, 8), "Title not reached", 3600, 60)
        self.tap("Start", 120)
        self.until(lambda: self.mode() == (1, 5), "File select not reached", 600)
        self.tap("Start", 180)
        self.ready()

    def start_case(self, label, **info):
        self.case = dict(label=label, **info)
        self.result["cases"].append(self.case)
        print(f"== {label}", flush=True)

    # --- menu ---------------------------------------------------------------
    def word(self, address):
        offset = ((address >> 16) & 0x7F) * 0x8000 + (address & 0x7FFF)
        return self.rom[offset] | self.rom[offset + 1] << 8

    def expected_icon(self, slot, variant):
        if variant == 0:
            gfx = self.symbols["NothingGFX"]
        else:
            table = self.word(self.symbols["Menu_Equipment_Gfx"] + slot * 2)
            gfx = (self.symbols["Menu_Equipment_Gfx"] & 0xFF0000) | table
            gfx += (variant - 1) * 8
        return [self.word(gfx + i) for i in range(0, 8, 2)]

    def icon(self, slot):
        x = self.word(self.symbols["Menu_Equipment_Pos"] + slot * 2)
        return [self.r(0x7E1108 + x + d) | self.r(0x7E1109 + x + d) << 8 for d in (0, 2, 0x40, 0x42)]

    def open_equipment(self):
        self.tap("Start")
        self.until(lambda: self.screen() == "items", "Items page not reached", 240)
        self.tap("L")
        self.until(lambda: self.screen() == "equipment", "Equipment page not reached", 240)
        self.advance("", 8)

    def close_menu(self):
        self.tap("Start")
        self.until(lambda: self.screen() == "gameplay", "Menu did not close", 400)
        self.ready()

    def song_row(self, songs, name):
        """Song row shows notes for learned songs only; cursor visits only them."""
        learned = [11 + s - 1 for s in songs]
        icons = {slot: self.icon(slot) for slot in SONG_SLOTS}
        expected = {slot: self.expected_icon(slot, slot - 9 if slot in learned else 0) for slot in SONG_SLOTS}
        self.check("song row icons (note = learned, blank = not)",
                   {f"{k}": [f"{w:04X}" for w in v] for k, v in icons.items()},
                   {f"{k}": [f"{w:04X}" for w in v] for k, v in expected.items()})
        self.shot(name)
        for _ in range(4):
            if self.r(CURSOR) in SONG_SLOTS:
                break
            self.tap("Down")
        if not learned:
            self.check("cursor never reaches an empty song row", self.r(CURSOR) in SONG_SLOTS, False)
            return []
        self.check("cursor reaches the song row", self.r(CURSOR) in learned, True)
        visited = [self.r(CURSOR)]
        for _ in range(len(learned)):
            self.tap("Right")
            visited.append(self.r(CURSOR))
        start = learned.index(visited[0])
        cycle = [learned[(start + i) % len(learned)] for i in range(len(learned) + 1)]
        self.check("Right cycles learned songs only, in order, with wrap", visited, cycle)
        return learned

    def select_song(self, song):
        for _ in range(7):
            if self.r(CURSOR) == 10 + song:
                break
            self.tap("Right")
        self.check(f"cursor on song {song}", self.r(CURSOR), 10 + song)
        self.tap("A")
        self.check("A selects current and saved song", [self.r(CURRENT), self.r(SAVED)], [song, song])

    # --- cases --------------------------------------------------------------
    def load_case(self, label, flute, bits, saved=0, out_of_order=False):
        self.start_case(label, kind="old save loaded" if not bits else "bits fixture")
        self.write_slot1(flute, bits, saved)
        self.boot_file1()
        state = self.save_state_bytes()
        self.case["after_load"] = state
        if self.a.mode == "candidate":
            want = bits or count_to_bits(flute)
            self.check("SongBits after file load", state["bits"], want)
            songs = [s for s in range(1, 5) if want >> (s - 1) & 1]
            self.check("count byte unchanged", state["flute"], flute)
            self.check("current/saved song bounded to lowest learned",
                       [state["current"], state["saved"]], [lowest(want)] * 2)
        else:
            self.check("SongBits untouched by old ROM", state["bits"], bits)
            songs = list(range(1, min(flute, 5))) if flute >= 2 else []
            self.check("count byte unchanged", state["flute"], flute)
        self.open_equipment()
        learned = self.song_row(songs, label)
        self.close_menu()
        return songs, learned

    def run(self):
        info = self.info()
        self.result["rom_info"] = {k: info.get(k) for k in ("sha1", "name", "frameCount")}
        self.settle_pause()
        cases = [(count, 0) for count in range(6)]
        for flute, bits in cases:
            self.load_case(f"count-{flute}" + ("-noocarina" if flute == 0 else ""), flute, bits)
        if self.a.mode == "candidate":
            # Zelda can teach Time before either Storms or Soaring.
            self.load_case("bits-09-healing-time", 2, 0x09)
        self.save_reopen()
        self.teacher()
        self.result["passed"] = True

    def save_reopen(self):
        self.start_case("save-quit-reopen", kind="native Save & Quit, reset, file 1")
        self.write_slot1(2, 0x09, 0) if self.a.mode == "candidate" else self.write_slot1(5, 0, 0)
        self.boot_file1()
        self.open_equipment()
        self.song_row([1, 4] if self.a.mode == "candidate" else [1, 2, 3, 4], "save-before")
        self.select_song(4)
        self.close_menu()
        before = self.save_state_bytes()
        self.case["before_save"] = before
        self.tap("Select", 90)
        for _ in range(4):
            if self.r(CHOICE) == 1:
                break
            self.tap("Down", 15)
        self.check("controller selects Save and Quit", self.r(CHOICE), 1)
        self.tap("A", 180)
        self.until(lambda: self.mode() == (0, 8), "Save and Quit did not reach title", 1800, 60)
        sram = self.block(SLOT1, 0x500, SRAM)
        self.case["sram_after_save"] = dict(flute=sram[0x34C], bits=sram[0x3B1], saved=sram[0x3AB])
        expected_bits = 0x09 if self.a.mode == "candidate" else 0
        expected_count = 2 if self.a.mode == "candidate" else 5
        self.check("saved SRAM slot 1 (count, bits, saved song)",
                   [sram[0x34C], sram[0x3B1], sram[0x3AB]], [expected_count, expected_bits, 4])
        self.boot_file1()
        after = self.save_state_bytes()
        self.case["after_reopen"] = after
        if self.a.mode == "candidate":
            self.check("reopen keeps count, bits, saved and current song",
                       [after["flute"], after["bits"], after["saved"], after["current"]],
                       [expected_count, expected_bits, 4, 4])
        else:
            self.check("reopen keeps count, bits and saved song",
                       [after["flute"], after["bits"], after["saved"]], [expected_count, expected_bits, 4])

    def teacher(self):
        self.start_case("teacher-mask-salesman", kind="warp-entrance 0x6B, teacher grants Healing")
        self.write_slot1(1, 0, 0)
        self.boot_file1()
        reply = subprocess.run([sys.executable, str(REPO / "Scripts/Mesen2/mesen2_client.py"),
                                "--socket", self.a.socket, "warp-entrance", "0x6B"],
                               capture_output=True, text=True, timeout=120)
        self.case["warp"] = reply.stdout.strip()[-400:]
        require(reply.returncode == 0, f"warp failed: {reply.stderr.strip()[-300:]}")
        self.settle_pause()
        self.until(lambda: self.r(ROOM) == 0x1F and self.r(ROOM + 1) == 0x01, "Not in room 0x011F", 600)
        self.advance("", 120)
        self.shot("teacher")
        state = self.save_state_bytes()
        self.case["after_teacher"] = state
        if self.a.mode == "candidate":
            self.check("Mask Salesman sets the Healing bit only", [state["flute"], state["bits"]], [1, 0x01])
        else:
            self.check("old ROM writes count 2", [state["flute"], state["bits"]], [2, 0])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--symbols", type=Path, required=True)
    parser.add_argument("--base-srm", type=Path, required=True)
    parser.add_argument("--mode", choices=("candidate", "control"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--client-root", type=Path,
                        default=Path.home() / "src/hobby/mesen2-oos/tools/oos_client")
    args = parser.parse_args()
    require("oos-rc-play" not in args.socket, "Never drive scawful's play window")
    args.output.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(args.client_root))
    from mesen2_client_lib.bridge import MesenBridge
    run = SongBitsRun(args, MesenBridge(args.socket, auto_reconnect=False, max_retries=0))
    try:
        run.run()
    except Exception as error:
        run.result["error"] = str(error)
        print("ERROR", error, flush=True)
    finally:
        (args.output / f"{args.mode}.json").write_text(json.dumps(run.result, indent=1))
    return 0 if run.result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
