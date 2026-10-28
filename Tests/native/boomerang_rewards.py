"""Attach-only Boomerang reward checks on an owned, paused native session.

The caller owns launch, a private inherited SRAM fixture, native Save/reopen and
cleanup. Menu recovery uses controller input only. Receipt checks explicitly use
synthetic CPU/register/WRAM fixtures against the compiled receipt helper; they
are routine evidence, not naturally earned chest rewards.
"""
from __future__ import annotations

import base64
import json
import re
import time


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def symbol(text, name):
    found = {int(a + b, 16) for a, b in re.findall(
        r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(?:Oracle_)?"
        + re.escape(name) + r"\s*$", text, re.M)}
    require(len(found) == 1, "Missing/ambiguous symbol: " + name)
    return found.pop()


def menu_recovery(active, expected):
    before = active.saved()
    active.step(2, "START")
    for _ in range(40):
        if active.b.read_memory(0x7E0010) == 14 and active.b.read_memory(0x7E0200) == 4:
            break
        active.step(4)
    else:
        raise AssertionError("Inventory menu did not open within160 frames")
    opened = active.saved()
    require(opened[0x341] == expected, "Menu recovery gave the wrong Boomerang tier")
    for at in (0x82, 0x83, 0x1D0, 0x1D1):
        require(opened[at] == before[at], "Recovery changed a saved chest flag")
    active.step(2, "START")
    for _ in range(40):
        if active.b.read_memory(0x7E0010) == 7 and active.b.read_memory(0x7E0011) == 0:
            break
        active.step(4)
    else:
        raise AssertionError("Inventory menu did not close within160 frames")
    return {"expected_tier": expected, "actual_tier": opened[0x341],
            "before_hex": before.hex(), "after_hex": active.saved().hex(),
            "chest_flags_preserved": True, "input_only": True}


def receipt_matrix(active, symbols, guarded=True):
    """Execute the actual helper via a private WRAM JSL; leave paused/disposable."""
    entry = symbol(symbols, "ItemReceipt_KeepGoldstar")
    migrate = symbol(symbols, "GoldstarInventoryVersion")
    b = active.b
    cases = [("blue-first", 0x0C, 0x7EF341, 0, 1, 1),
             ("blue-repeat", 0x0C, 0x7EF341, 1, 1, 1),
             ("blue-after-red", 0x0C, 0x7EF341, 2, 1, 2 if guarded else 1),
             ("red-after-blue", 0x2A, 0x7EF341, 1, 2, 2),
             ("red-repeat", 0x2A, 0x7EF341, 2, 2, 2),
             ("glove-first", 0x1B, 0x7EF354, 0, 1, 1),
             ("glove-after-mitt", 0x1B, 0x7EF354, 2, 1, 2 if guarded else 1),
             ("mitt-upgrade", 0x1C, 0x7EF354, 1, 2, 2)]
    results = []
    for name, item, target, prior, value, expected in cases:
        active.session.pause()
        b.write_memory(target, prior)
        b.write_memory(migrate, 0xA5)
        b.write_block(0x7E0000, target.to_bytes(3, "little"))
        b.write_block(0x7F8000, bytes([0x22, *entry.to_bytes(3, "little"), 0xEA]))
        bp = b.add_breakpoint(0x7F8004)
        require(isinstance(bp, int) and bp >= 0, "Receipt return breakpoint failed")
        state = {"cpu.a": 0xAB00 | value, "cpu.x": 0x23, "cpu.y": item,
                 "cpu.ps": 0x34, "cpu.sp": 0x1FFF, "cpu.d": 0,
                 "cpu.dbr": 0x09, "cpu.k": 0x7F, "cpu.pc": 0x8000,
                 "cpu.emulationMode": False}
        lua = "emu.setState({" + ",".join(
            "[" + json.dumps(k) + "]=" + (str(v).lower() if isinstance(v, bool) else str(v))
            for k, v in state.items()) + "})"
        try:
            reply = b.execute_lua(base64.b64encode(lua.encode()).decode())
            require(reply.get("success"), "Native CPU fixture setup refused")
            require(b.resume(), "Receipt execution did not resume")
            deadline = time.monotonic() + 5
            while not active.session.client.is_paused():
                require(time.monotonic() < deadline, "Receipt helper did not return")
                time.sleep(0.01)
            cpu = b.get_cpu_state()
            require(int(str(cpu["pc"]), 0) == 0x7F8004,
                    "Receipt paused before its real RTL return")
            require(int(str(cpu["sp"]), 0) == 0x1FFF,
                    "Receipt helper changed stack balance")
            actual = b.read_memory(target)
            require(actual == expected, name + ": wrong inventory tier")
            results.append({"name": name, "before": prior, "after": actual,
                            "expected": expected, "cpu": cpu, "passed": True})
        finally:
            require(b.remove_breakpoint(bp), "Owned receipt breakpoint cleanup failed")
    return {"cases": results, "passed": True, "synthetic_cpu_fixture": True}
