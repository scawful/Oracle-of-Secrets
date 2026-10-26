# t2kit — native T2 checks as short scenarios

A T2 check (AGENTS.md rule 1) runs the changed behavior once in headless Mesen2-OOS on a
candidate ROM and on a control ROM. t2kit holds the shared parts: instance launch on its own
socket and profile, save loading, warps, RAM and collision fixtures, controller walking,
breakpoint capture, screenshots and `result.json`. A scenario file holds only the route and
the checks.

## Run a scenario

```bash
python3 Scripts/Validate/run_t2.py keyblock --candidate HEAD --control origin/master --out /tmp/t2-keyblock
```

1. Each ref is built in its own detached temporary worktree: the base ROM (default: the main
   checkout's `Roms/oos168.sfc`, read only) is copied in as-is, then
   `Scripts/Build/build_rom.sh 168` runs there. Two refs at the same commit build once.
2. Each episode (one case on one ROM) takes the heavy lock through
   `Scripts/Agents/heavy_lock.py`, waits up to `--lock-wait` seconds (default 3600) when another
   agent holds it, and releases it when the episode ends or fails.
3. The runner prints `| case | candidate | control | verdict |` and writes `<out>/summary.json`.
   Exit 0 when every candidate case passes.

Other options: `--candidate-rom` / `--control-rom` (prebuilt ROMs, no build), `--control none`,
`--cases a,b`, `--srm` (another copy of the fixture save; its sha256 must match the registry),
`--app`, `--base-rom`, `--owner`.

Verdicts: a scenario always expects the new or fixed behavior, so a control that lacks it reads
`pass (control fails)`. `REGRESSION (control passes)` means the candidate broke something the
control does.

## Write a scenario

Put a file in `t2kit/scenarios/<name>.py` with `FIXTURE`, `CASES` and `run(t, case)`. `t` is a
booted `Session` on the fixture save, with Link in play and the no-damage flag set on first input.

```python
FIXTURE = 'goron-mines-open'          # name in t2kit/fixtures.json
CASES = ('hot_floor',)

HEALTH = 0x7EF36D
HOT = 0x07FFA0                         # TileBehavior_HotFloor (PR 278)


def run(t, case):
    t.warp(0x26, room=0x4A, label='D1 Mushroom Grotto, room $4A')
    t.clear_enemies()
    t.invincible = False
    t.fixture_ram(0x7E037B, 0, 'no-damage flag cleared')
    x, y = t.link()
    cells = [(tx, ((y & 0x1FF) >> 3) - 1) for tx in range((x & 0x1FF) >> 3, ((x & 0x1FF) >> 3) + 2)]
    t.fixture_collision(cells, 0xDE, 'hot floor north of Link')
    h0 = t.r(HEALTH)
    hits = t.record_breaks({HOT: 'TileBehavior_HotFloor'}, ['up', 'up'], 'step north')
    t.expect_breakpoint(hits, HOT, 'hot floor handler ran')
    t.check('health dropped', t.r(HEALTH) < h0, True)
```

Main `Session` calls:

| Call | Does |
|---|---|
| `warp(entrance, room=)`, `warp_area(area)` | warp and wait for play; wrong room raises |
| `fixture_ram(addr, value, why)`, `fixture_collision(cells, type, why)` | write and record a fixture in `result.json` |
| `travel(goal, bounds)`, `walk_to(x, y)`, `through_door(button, room)` | controller movement with a route on `$7F2000` |
| `press(button, frames)`, `guard()` | controller input; `guard` keeps Link from taking damage |
| `record_breaks(bps, presses, label)`, `breaks(bps, timeout)` | exec breakpoints with RAM snapshots per hit |
| `expect_breakpoint(hits, addr, name)`, `expect_ram(addr, value, name)`, `check(name, got, want)` | recorded checks |
| `screenshot(label)`, `event(name, **data)`, `alive(label)` | evidence |

Rules the kit follows: headless only, own instance name and socket, stop only the owned PID
with SIGTERM, ROM copy named without "test" or "oos<digits>", SRAM hash checked against the
registry. It never touches the `oos-rc-play` instance.

## Fixtures

`fixtures.json` maps a name to an SRAM path outside git, its sha256, the file slot and what the
save contains. A run refuses a save whose hash does not match. Add an entry when a scenario needs
a new save; do not commit `.srm` files.

## Tests

`python3 -m unittest discover -s Scripts/Validate/tests -p 'test_t2kit.py'` covers the registry,
verdict table, lock and route finder without Mesen.
