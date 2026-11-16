#!/usr/bin/env python3
"""D1-D8 dungeon smoke for a candidate build: enter, no blackout, boss loads, exit warp.

One case per dungeon. Each case runs inside its own
`Scripts/Agents/native_session.py run` (heavy lock, owned Mesen PIDs,
deadline, teardown), so a failed or hung case cannot leave a Mesen behind.

Per case (all RAM pokes on a copy of the ROM; the ROM file is never written):
  1. boot   - the SRAM seed (default: all-items fixture.srm) in a private Mesen
              home; press Start until play (module $07/$09).
  2. enter  - clear the boss room's save-flag word and the follower, then the
              entrance reload (module $05 with $010E = entrance). PASS when
              module $07/00, room = the entrance table's room ($0F:8000+2*id),
              $040C = 2*slot, INIDISP mirror $13 = $0F.
  3. light  - three samples 0.5 s apart: module $07, $13 = $0F, frame counter
              $1A moving. Catches blackouts and hangs after the room load.
  4. boss   - stair-load the boss room ($A2/$A0, submodule $0E, the D8 boss-run
              method), place Link and the camera in the NW quadrant. PASS when
              module $07, room = boss room, and a sprite id from the room's own
              ROM sprite list is active in $0E20/$0DD0.
  5. exit   - module $08 with $A0 = the entrance room (OracleCheats area-warp
              pokes). PASS when module $09/00 lands on the exit table's area
              for that room ($02:DD8A) and $13 = $0F.

Modes:
  --dry-run          offline: resolve the table from --rom, check the seed,
                     print the plan and every native_session command. No Mesen.
  (default)          loop native_session.py over the cases, write
                     results.json + results.md in --out.
  --case Dn          one case; run by the loop inside native_session.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "Scripts" / "Generate"))
sys.path.insert(0, str(REPO / "Scripts" / "Agents"))
from dungeon_maps import MapRom, SLOTS  # noqa: E402

SCRATCH = Path.home() / "src/hobby/oracle-of-secrets-scratch"
DEFAULT_SEED = SCRATCH / "claude-d8-boss-20261116/fixture.srm"
DEFAULT_OUT = SCRATCH / "claude-dungeon-smoke-build-l"
OWNER = "Claude-Dungeon-Smoke"

# id, main overworld entrance (Data/debug/warps.json labels), boss-room pin.
# Boss rooms come from the dungeon-map table (BOSS_ROOMS) unless pinned.
# D8 is pinned: its map word read $C8 (D6's room) on e51f9e9d; the D8 boss
# native (2026-11-16) proved $96.
DUNGEONS = (
    ("D1", 0x26, None),  # Mushroom Grotto
    ("D2", 0x15, None),  # Tail Palace
    ("D3", 0x2B, None),  # Kalyxo Castle (main)
    ("D4", 0x25, None),  # Zora Temple
    ("D5", 0x34, None),  # Glacia Estate
    ("D6", 0x27, None),  # Goron Mines
    ("D7", 0x35, None),  # Dragon Ship
    ("D8", 0x29, 0x96),  # Sky Tower
)

ENTRANCE_ROOMS = 0x0F8000        # live ZScream table, word per entrance
EXIT_ROOMS, EXIT_COUNT = 0x02DD8A, 0x4F
SPRITE_TABLE_OPERAND_PC = 0x4C298
SPRITE_IDS_NOT_BOSS = {0xE4}     # key drop marker

M = dict(module=0x7E0010, sub=0x7E0011, indoors=0x7E001B, bright=0x7E0013, frame=0x7E001A,
         room=0x7E00A0, prev_room=0x7E00A2, quadrant=0x7E00A9, area=0x7E008A, subsub=0x7E00B0,
         dungeon=0x7E040C, entrance=0x7E010E, cont=0x7E010A, respawn=0x7E04AA, hdma=0x7E009B,
         world=0x7EF3CA, world_flag=0x7E0FFF, follower=0x7EF3CC, link_x=0x7E0022, link_y=0x7E0020,
         sprite_type=0x7E0E20, sprite_state=0x7E0DD0)


def pc(address: int) -> int:
    return ((address >> 16) & 0x7F) * 0x8000 + (address & 0x7FFF)


def word(rom: bytes, at: int) -> int:
    return rom[at] | rom[at + 1] << 8


def exit_area(rom: bytes, room: int):
    base = pc(EXIT_ROOMS)
    for index in range(EXIT_COUNT - 1, -1, -1):
        if word(rom, base + index * 2) == room:
            return rom[base + EXIT_COUNT * 2 + index]
    return None


def room_sprites(rom: bytes, room: int) -> list[int]:
    table = pc(0x090000 | word(rom, SPRITE_TABLE_OPERAND_PC))
    at = pc(0x090000 | word(rom, table + room * 2)) + 1  # skip the sort byte
    ids = []
    while rom[at] != 0xFF:
        b0, b1, sid = rom[at:at + 3]
        if not ((b1 & 0xE0) == 0xE0 and (b0 & 0x60) == 0x60) and sid not in SPRITE_IDS_NOT_BOSS:
            ids.append(sid)  # overlords skipped
        at += 3
    return ids


def plan(rom: bytes) -> list[dict]:
    maps = MapRom(rom)
    cases = []
    for name, entrance, pin in DUNGEONS:
        slot = SLOTS[name]
        map_boss = maps.dungeon(slot)["boss_room"]
        boss = pin if pin is not None else map_boss
        room = word(rom, pc(ENTRANCE_ROOMS) + entrance * 2)
        cases.append(dict(
            dungeon=name, slot=slot, dungeon_id=slot * 2, entrance=entrance, entrance_room=room,
            boss_room=boss, map_boss_room=map_boss, boss_sprites=sorted(set(room_sprites(rom, boss))),
            exit_area=exit_area(rom, room),
            notes=[f"map boss word ${map_boss:02X} != pinned ${boss:02X}"] if map_boss != boss else []))
    return cases


def hexcase(case: dict) -> str:
    sprites = ",".join(f"${s:02X}" for s in case["boss_sprites"]) or "-"
    ex = "none" if case["exit_area"] is None else f"${case['exit_area']:02X}"
    return (f"{case['dungeon']}: entrance ${case['entrance']:02X} -> room ${case['entrance_room']:03X} "
            f"(id ${case['dungeon_id']:02X}), boss room ${case['boss_room']:03X} sprites {sprites}, "
            f"exit area {ex}" + (f"  NOTE {'; '.join(case['notes'])}" if case["notes"] else ""))


# ---------------------------------------------------------------- live client
class Client:
    def __init__(self, socket: Path):
        self.socket = socket
        self.env = dict(os.environ)
        if not (REPO.parent / "mesen2-oos").is_dir():
            self.env.setdefault("MESEN2_OOS_ROOT", str(Path.home() / "src/hobby/mesen2-oos"))

    def __call__(self, *args: str) -> str:
        return subprocess.run([sys.executable, str(REPO / "Scripts/Mesen2/mesen2_client.py"),
                               "--socket", str(self.socket), *args],
                              capture_output=True, text=True, env=self.env, timeout=60).stdout

    def read(self, addr: int, n: int = 1) -> bytes:
        out = self("mem-read", hex(addr), "--len", str(n))
        return bytes.fromhex("".join(l.split(":", 1)[1] for l in out.strip().splitlines() if ":" in l)
                             .replace(" ", ""))

    def b(self, addr: int) -> int:
        return self.read(addr)[0]

    def w16(self, addr: int) -> int:
        data = self.read(addr, 2)
        return data[0] | data[1] << 8

    def poke(self, pairs) -> None:
        for addr, value in pairs:
            self("mem-write", hex(addr), value if isinstance(value, str) else f"{value:02X}")

    def state(self) -> dict:
        return dict(module=self.b(M["module"]), sub=self.b(M["sub"]), room=self.w16(M["room"]),
                    area=self.b(M["area"]), indoors=self.b(M["indoors"]), bright=self.b(M["bright"]),
                    dungeon=self.b(M["dungeon"]), frame=self.b(M["frame"]))

    def wait_for(self, modules, timeout: float) -> dict:
        end = time.time() + timeout
        while True:
            s = self.state()
            if s["module"] in modules and s["sub"] == 0:
                return s
            if time.time() > end:
                return s
            time.sleep(0.4)

    def active_sprites(self) -> list[int]:
        types, states = self.read(M["sprite_type"], 16), self.read(M["sprite_state"], 16)
        return [types[i] for i in range(16) if states[i]]


def fmt(s: dict) -> str:
    return ("mod {module:02X}/{sub:02X} room {room:03X} area {area:02X} in {indoors} "
            "bright {bright:02X} id {dungeon:02X}").format(**s)


def run_case(case: dict, rom_path: Path, seed: Path, out: Path) -> int:
    from native_session import NativeSession
    out.mkdir(parents=True, exist_ok=True)
    rom = out / "smoke.sfc"
    shutil.copyfile(rom_path, rom)
    home = out / "home"
    (home / "Saves").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(seed, home / "Saves" / "smoke.srm")
    result = dict(case, checks={}, log=[])
    log = result["log"].append

    def check(name: str, ok: bool, detail: str) -> bool:
        result["checks"][name] = {"ok": bool(ok), "detail": detail}
        log(f"{name}: {'PASS' if ok else 'FAIL'} {detail}")
        return ok

    with NativeSession(OWNER, f"dungeon smoke {case['dungeon']}", out, deadline=240) as session:
        _pid, socket = session.launch_mesen(rom, home=home)
        c = Client(socket)
        for _ in range(60):
            if socket.exists():
                break
            time.sleep(1)
        time.sleep(3)
        try:
            # 1. boot
            c("resume")
            for _ in range(40):
                module = c.b(M["module"])
                if module in (0x07, 0x09):
                    break
                c("press", "start", "--frames", "4")
                time.sleep(0.6)
                if module == 0x01:
                    c("press", "a", "--frames", "4")
                    time.sleep(0.6)
            time.sleep(2)
            s = c.state()
            if check("boot", s["module"] in (0x07, 0x09, 0x0B), fmt(s)):
                # 2. enter
                boss_flag = 0x7EF000 + case["boss_room"] * 2
                c("pause")
                c.poke([(boss_flag, "00 00"), (M["follower"], 0), (M["world"], 0), (M["world_flag"], 0),
                        (0x7E02B2, 0), (0x7E00BC, 0x10), (M["entrance"], case["entrance"]), (M["entrance"] + 1, 0),
                        (M["cont"], 1), (M["respawn"], 0), (M["indoors"], 1), (M["sub"], 0), (M["subsub"], 0),
                        (M["module"], 0x05)])
                c("resume")
                s = c.wait_for((0x07,), 10)
                c("screenshot", "--out", str(out / "1_enter.png"))
                entered = check("enter", s["module"] == 0x07 and s["sub"] == 0 and s["room"] == case["entrance_room"]
                                and s["dungeon"] == case["dungeon_id"] and s["bright"] == 0x0F, fmt(s))
                # 3. light
                samples = []
                for _ in range(3):
                    samples.append(c.state())
                    time.sleep(0.5)
                frames = {x["frame"] for x in samples}
                check("no_blackout", all(x["module"] == 0x07 and x["bright"] == 0x0F for x in samples)
                      and len(frames) > 1, "; ".join(fmt(x) for x in samples))
                if entered:
                    # 4. boss
                    room = case["boss_room"]
                    bx, by = (room & 0x0F) << 9, (room & 0xF0) << 5
                    c("pause")
                    c.poke([(M["prev_room"], c.b(M["room"])), (M["room"], room & 0xFF), (M["room"] + 1, room >> 8),
                            (M["sub"], 0x0E), (M["subsub"], 3)])
                    c("resume")
                    time.sleep(3)
                    c("pause")
                    xy = lambda v: f"{v & 0xFF:02X} {v >> 8:02X}"  # noqa: E731
                    c.poke([(M["link_x"], xy(bx + 0x78)), (M["link_y"], xy(by + 0x40)), (M["quadrant"], "00 00"),
                            (0x7E0600, " ".join([xy(by)] * 2 + [xy(by + 0x10)] * 2 + [xy(bx)] * 4)),
                            (0x7E00E0, xy(bx)), (0x7E00E2, xy(bx)), (0x7E00E6, xy(by)), (0x7E00E8, xy(by))])
                    c("resume")
                    time.sleep(1.5)
                    c("pause")
                    s = c.state()
                    active = c.active_sprites()
                    c("screenshot", "--out", str(out / "2_boss.png"))
                    hit = sorted(set(active) & set(case["boss_sprites"]))
                    # Module $0E/$02 is a message box: a boss that opens with intro text
                    # (D5 $CE) is loaded, not hung.
                    alive = s["module"] == 0x07 or (s["module"], s["sub"]) == (0x0E, 0x02)
                    check("boss_loads", alive and s["room"] == room and bool(hit),
                          f"{fmt(s)} active {[f'{x:02X}' for x in active]} matched {[f'{x:02X}' for x in hit]}")
                    # 5. exit
                    er = case["entrance_room"]
                    c.poke([(M["room"], er & 0xFF), (M["room"] + 1, er >> 8), (M["cont"], 0), (M["respawn"], 0),
                            (M["bright"], 0x80), (M["hdma"], 0), (M["sub"], 0), (M["subsub"], 0),
                            (M["module"], 0x08)])
                    c("resume")
                    s = c.wait_for((0x09, 0x0B), 12)
                    time.sleep(1)
                    s = c.state()
                    c("screenshot", "--out", str(out / "3_exit.png"))
                    check("exit_warp", s["module"] in (0x09, 0x0B) and s["sub"] == 0
                          and case["exit_area"] is not None and s["area"] == case["exit_area"]
                          and s["bright"] == 0x0F, f"{fmt(s)} expected area "
                          + ("none" if case["exit_area"] is None else f"{case['exit_area']:02X}"))
        except Exception as error:  # noqa: BLE001 - recorded, then teardown
            check("error", False, f"{type(error).__name__}: {error}")
    names = ("boot", "enter", "no_blackout", "boss_loads", "exit_warp")
    result["status"] = "PASS" if all(result["checks"].get(n, {}).get("ok") for n in names) else "FAIL"
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(result["status"], hexcase(case))
    return 0 if result["status"] == "PASS" else 1


def table(results: list[dict]) -> str:
    rows = ["| Dungeon | Entrance | Room | Boss room | Enter | No blackout | Boss loads | Exit warp | Result |",
            "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        cell = lambda n: {True: "PASS", False: "FAIL"}.get(r.get("checks", {}).get(n, {}).get("ok"), "-")  # noqa: E731
        rows.append(f"| {r['dungeon']} | ${r['entrance']:02X} | ${r['entrance_room']:03X} | ${r['boss_room']:03X} "
                    f"| {cell('enter')} | {cell('no_blackout')} | {cell('boss_loads')} | {cell('exit_warp')} "
                    f"| {r.get('status', 'NO RESULT')} (rc {r.get('rc', '-')}) |")
    return "\n".join(rows) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rom", type=Path, required=True, help="candidate build ROM (read only; copied per case)")
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED, help="SRAM seed (.srm)")
    parser.add_argument("--out", type=Path, help="run directory (default: scratch/<stamp>)")
    parser.add_argument("--only", help="comma list, e.g. D1,D8")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--case", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if not args.rom.is_file():
        parser.error(f"ROM not found: {args.rom}")
    if not args.seed.is_file():
        parser.error(f"seed not found: {args.seed}")
    rom = args.rom.read_bytes()
    cases = plan(rom)
    if args.only:
        wanted = {x.strip().upper() for x in args.only.split(",")}
        cases = [c for c in cases if c["dungeon"] in wanted]
    out = args.out or DEFAULT_OUT / dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if args.case:
        case = next(c for c in cases if c["dungeon"] == args.case.upper())
        return run_case(case, args.rom, args.seed, out)

    print(f"ROM {args.rom} sha256 {hashlib.sha256(rom).hexdigest()[:16]}")
    print(f"seed {args.seed} sha256 {hashlib.sha256(args.seed.read_bytes()).hexdigest()[:16]}")
    commands = []
    for case in cases:
        print(hexcase(case))
        commands.append([sys.executable, str(REPO / "Scripts/Agents/native_session.py"), "run",
                         "--owner", OWNER, "--purpose", f"dungeon smoke {case['dungeon']}; never oos-rc-play",
                         "--run-dir", str(out / case["dungeon"]), "--deadline", "300", "--",
                         sys.executable, str(Path(__file__).resolve()), "--rom", str(args.rom.resolve()),
                         "--seed", str(args.seed.resolve()), "--out", str(out / case["dungeon"]),
                         "--case", case["dungeon"]])
    problems = [c["dungeon"] for c in cases if c["exit_area"] is None or not c["boss_sprites"]]
    if args.dry_run:
        for cmd in commands:
            print("  " + " ".join(cmd))
        print("dry run: no Mesen started" + (f"; table gaps in {problems}" if problems else ""))
        return 1 if problems else 0

    out.mkdir(parents=True, exist_ok=True)
    results = []
    for case, cmd in zip(cases, commands):
        rc = subprocess.run(cmd).returncode
        receipt = out / case["dungeon"] / "result.json"
        result = json.loads(receipt.read_text()) if receipt.is_file() else dict(case)
        result["rc"] = rc
        results.append(result)
        if rc == 3:
            print("heavy lock wait ran out; stopping the loop")
            break
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    (out / "results.md").write_text(table(results))
    print(table(results))
    return 0 if all(r.get("status") == "PASS" for r in results) and len(results) == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
