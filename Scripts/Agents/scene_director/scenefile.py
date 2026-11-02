"""Scene files (JSON) and the RAM expression language. Offline; no emulator.

A scene is one JSON object:

    {
      "scene": "house-walk",
      "description": "optional",
      "steps": [
        {"load": {"srm": "save.srm", "fixtures": ["grant.json"], "entrance": "0x2A"}},
        {"walk_to": {"x": 120, "y": 200}},
        {"face": "up"},
        {"equip": "0x1C"},
        {"poke": {"writes": [{"addr": "0x7E0DD0", "type": "u8", "value": 0, "count": 16}]}},
        {"press": {"button": "Y", "frames": 2}},
        {"wait_until": {"expr": "u8(0x7E0010) == 7", "max_frames": 120}},
        {"check": {"expr": "room == 0x104", "label": "still in the house"}},
        {"hold": {"frames": 60}},
        {"record": "start"}
      ]
    }

Steps:
  load        First step only. "srm" cold-boots file 1 from a copied battery save;
              "state" loads a Mesen savestate instead. "fixtures" are existing fixture
              JSON files ({"writes": [{"addr", "type": u8|u16, "value"}]}), applied
              after the load with readback. Paths are relative to the scene file.
              "entrance" (0x00..0x84, optional) then loads that entrance with the
              oracle_cheats "reload" pokes and waits for module 7/9, submodule 0.
  walk_to     Room-local Link (x, y) as in goron97_cart_gate walk(): $22/$20 minus the
              room base. Optional: allow_doors, allow_hazard_edge, blocked [[col,row]...].
              The walker stops within 2 px (goron97 axis() tolerance).
  face        up|down|left|right: a one-frame D-pad tap (sets $2F; may nudge Link 1-2 px).
  equip       Item id (e.g. "0x1C" Bombchu): Start, Right until $0202 is the item, Start
              (new_items_prototype.equip by controller, so the HUD updates natively).
  poke        {"writes": [{"addr", "type"?, "value", "count"?}]}: fixture-format RAM
              writes with readback; "count" repeats a u8/u16 write over consecutive cells.
  press       {"button": "Y" | ["A","Up"], "frames": N (default 2)}, then 2 neutral frames.
  wait_until  {"expr", "max_frames"}: advance neutral frames until expr is true; fails otherwise.
  check       {"expr", "label"?}: fails the scene (nonzero exit) when false.
  hold        {"frames": N, "button"?}: hold a button, or nothing, for N frames.
  record      "start" | "stop". Between them every frame is captured (1-frame advances)
              to PNG and encoded to mp4. Without "stop", capture runs to the end.

Top-level "watch" (optional): {name: expr}, up to 32, evaluated after every frame
and logged as "watch" in frames.jsonl (diagnostics only; never changes the run).

Expressions: integers, + - * // % & | ^ << >> ~, comparisons, and/or/not,
u8(addr), u16(addr), and names: room lx ly x y layer module submodule hp frame
indoors dir. No other names, calls or attributes are accepted.
"""
from __future__ import annotations

import ast
import json
import operator
from dataclasses import dataclass
from pathlib import Path

BUTTONS = frozenset({"A", "B", "X", "Y", "L", "R", "Start", "Select", "Up", "Down", "Left", "Right"})
DIRECTIONS = {"up": "Up", "down": "Down", "left": "Left", "right": "Right"}
STEP_KINDS = ("load", "walk_to", "face", "equip", "poke", "press", "wait_until", "check", "hold", "record")
NAMES = frozenset({"room", "lx", "ly", "x", "y", "layer", "module", "submodule", "hp", "frame",
                   "indoors", "dir"})
MAX_FRAMES = 36000  # ten minutes at 60 fps; scenes are short takes


class SceneError(ValueError):
    """Malformed scene file or expression."""


_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.BitAnd: operator.and_,
        ast.BitOr: operator.or_, ast.BitXor: operator.xor, ast.LShift: operator.lshift,
        ast.RShift: operator.rshift}
_CMP = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le,
        ast.Gt: operator.gt, ast.GtE: operator.ge}
_UNARY = {ast.USub: operator.neg, ast.Invert: operator.invert, ast.Not: operator.not_,
          ast.UAdd: operator.pos}
_READERS = {"u8": 1, "u16": 2}


class Expr:
    """A validated RAM expression. Evaluate with a reader(addr, size) and a names dict."""

    def __init__(self, text: str):
        if not isinstance(text, str) or not text.strip():
            raise SceneError("expression must be a non-empty string")
        self.text = text
        try:
            self.tree = ast.parse(text, mode="eval").body
        except SyntaxError as error:
            raise SceneError(f"bad expression {text!r}: {error.msg}") from None
        self._validate(self.tree)

    def _validate(self, node):
        if isinstance(node, ast.Constant):
            if type(node.value) not in (int, bool):
                raise SceneError(f"{self.text!r}: only integer constants allowed")
        elif isinstance(node, ast.Name):
            if node.id not in NAMES:
                raise SceneError(f"{self.text!r}: unknown name {node.id!r}; allowed {sorted(NAMES)}")
        elif isinstance(node, ast.Call):
            if not (isinstance(node.func, ast.Name) and node.func.id in _READERS
                    and len(node.args) == 1 and not node.keywords):
                raise SceneError(f"{self.text!r}: only u8(addr) and u16(addr) calls allowed")
            self._validate(node.args[0])
        elif isinstance(node, ast.BinOp) and type(node.op) in _BIN:
            self._validate(node.left)
            self._validate(node.right)
        elif isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            self._validate(node.operand)
        elif isinstance(node, ast.BoolOp):
            for value in node.values:
                self._validate(value)
        elif isinstance(node, ast.Compare) and all(type(op) in _CMP for op in node.ops):
            self._validate(node.left)
            for value in node.comparators:
                self._validate(value)
        else:
            raise SceneError(f"{self.text!r}: unsupported syntax {type(node).__name__}")

    def evaluate(self, read, names):
        def ev(node):
            if isinstance(node, ast.Constant):
                return int(node.value)
            if isinstance(node, ast.Name):
                return int(names[node.id])
            if isinstance(node, ast.Call):
                return int(read(ev(node.args[0]), _READERS[node.func.id]))
            if isinstance(node, ast.BinOp):
                return _BIN[type(node.op)](ev(node.left), ev(node.right))
            if isinstance(node, ast.UnaryOp):
                return int(_UNARY[type(node.op)](ev(node.operand)))
            if isinstance(node, ast.BoolOp):
                values = (ev(v) for v in node.values)
                return int(all(values) if isinstance(node.op, ast.And) else any(values))
            left = ev(node.left)
            for op, comp in zip(node.ops, node.comparators):
                right = ev(comp)
                if not _CMP[type(op)](left, right):
                    return 0
                left = right
            return 1
        return ev(self.tree)


@dataclass
class Step:
    index: int
    kind: str
    args: dict

    def label(self):
        return f"step {self.index} {self.kind}"


@dataclass
class Scene:
    name: str
    path: Path
    steps: list
    description: str = ""
    watch: dict = None  # name -> Expr, logged every frame in frames.jsonl

    @property
    def load(self):
        return self.steps[0] if self.steps and self.steps[0].kind == "load" else None

    def uses_record(self):
        return any(step.kind == "record" for step in self.steps)


def _int(value, where, low=None, high=None):
    if type(value) is not int:
        raise SceneError(f"{where}: expected integer, got {value!r}")
    if (low is not None and value < low) or (high is not None and value > high):
        raise SceneError(f"{where}: {value} outside {low}..{high}")
    return value


def _hex(value, where):
    """Accept 28 or "0x1C" (scene files use hex strings for RAM and item ids)."""
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            raise SceneError(f"{where}: bad integer {value!r}") from None
    return value


def _buttons(value, where):
    items = value if isinstance(value, list) else [value]
    if not items or any(item not in BUTTONS for item in items):
        raise SceneError(f"{where}: buttons must be from {sorted(BUTTONS)}, got {value!r}")
    return ",".join(items)


def _path(base: Path, value, where):
    if not isinstance(value, str) or not value:
        raise SceneError(f"{where}: expected a path string")
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path).resolve()


def _normalize(index, kind, raw, base: Path):
    where = f"step {index} {kind}"
    if kind == "load":
        if not isinstance(raw, dict) or ("srm" in raw) == ("state" in raw):
            raise SceneError(f"{where}: give exactly one of 'srm' or 'state'")
        unknown = set(raw) - {"srm", "state", "fixtures", "entrance"}
        if unknown:
            raise SceneError(f"{where}: unknown keys {sorted(unknown)}")
        out = {k: _path(base, raw[k], where) for k in ("srm", "state") if k in raw}
        fixtures = raw.get("fixtures", [])
        if not isinstance(fixtures, list):
            raise SceneError(f"{where}: fixtures must be a list")
        out["fixtures"] = [_path(base, f, where) for f in fixtures]
        if "entrance" in raw:
            out["entrance"] = _int(_hex(raw["entrance"], where + ".entrance"), where + ".entrance", 0, 0x84)
        return out
    if kind == "walk_to":
        if not isinstance(raw, dict):
            raise SceneError(f"{where}: expected {{'x': .., 'y': ..}}")
        unknown = set(raw) - {"x", "y", "allow_doors", "allow_hazard_edge", "blocked"}
        if unknown:
            raise SceneError(f"{where}: unknown keys {sorted(unknown)}")
        blocked = raw.get("blocked", [])
        if not all(isinstance(c, list) and len(c) == 2 and all(type(v) is int for v in c) for c in blocked):
            raise SceneError(f"{where}: blocked must be [[col,row], ...]")
        return {"x": _int(raw.get("x"), where + ".x", 0, 511), "y": _int(raw.get("y"), where + ".y", -8, 511),
                "allow_doors": bool(raw.get("allow_doors", False)),
                "allow_hazard_edge": bool(raw.get("allow_hazard_edge", False)),
                "blocked": [tuple(c) for c in blocked]}
    if kind == "face":
        value = raw.get("dir") if isinstance(raw, dict) else raw
        if value not in DIRECTIONS:
            raise SceneError(f"{where}: direction must be one of {sorted(DIRECTIONS)}")
        return {"dir": value, "button": DIRECTIONS[value]}
    if kind == "equip":
        value = raw.get("item") if isinstance(raw, dict) else raw
        return {"item": _int(_hex(value, where + ".item"), where + ".item", 1, 0xFF)}
    if kind == "poke":
        if not isinstance(raw, dict) or set(raw) != {"writes"}:
            raise SceneError(f"{where}: expected {{'writes': [...]}}")
        return {"writes": parse_writes(raw["writes"], where, allow_count=True)}
    if kind == "press":
        if not isinstance(raw, dict) or "button" not in raw:
            raise SceneError(f"{where}: expected {{'button': .., 'frames': N}}")
        return {"button": _buttons(raw["button"], where),
                "frames": _int(raw.get("frames", 2), where + ".frames", 1, MAX_FRAMES)}
    if kind in ("wait_until", "check"):
        if not isinstance(raw, dict) or "expr" not in raw:
            raise SceneError(f"{where}: expected {{'expr': ..}}")
        out = {"expr": Expr(raw["expr"]), "label": str(raw.get("label", raw["expr"]))}
        if kind == "wait_until":
            out["max_frames"] = _int(raw.get("max_frames"), where + ".max_frames", 1, MAX_FRAMES)
        return out
    if kind == "hold":
        if not isinstance(raw, dict):
            raise SceneError(f"{where}: expected {{'frames': N}}")
        button = raw.get("button")
        return {"frames": _int(raw.get("frames"), where + ".frames", 1, MAX_FRAMES),
                "button": _buttons(button, where) if button else ""}
    if kind == "record":
        value = raw.get("action") if isinstance(raw, dict) else raw
        if value not in ("start", "stop"):
            raise SceneError(f"{where}: expected 'start' or 'stop'")
        return {"action": value}
    raise SceneError(f"{where}: unknown step kind")


def parse_scene(data: dict, path: Path) -> Scene:
    if not isinstance(data, dict):
        raise SceneError("scene file must be a JSON object")
    unknown = set(data) - {"scene", "description", "steps", "version", "watch"}
    if unknown:
        raise SceneError(f"unknown top-level keys {sorted(unknown)}")
    if data.get("version", 1) != 1:
        raise SceneError("only scene version 1 is supported")
    name = data.get("scene")
    if not isinstance(name, str) or not name:
        raise SceneError("'scene' must name the scene")
    raw_steps = data.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise SceneError("'steps' must be a non-empty list")
    steps = []
    for index, raw in enumerate(raw_steps):
        if not isinstance(raw, dict) or len(raw) != 1:
            raise SceneError(f"step {index}: each step is one {{kind: args}} object")
        (kind, args), = raw.items()
        if kind not in STEP_KINDS:
            raise SceneError(f"step {index}: unknown kind {kind!r}; allowed {list(STEP_KINDS)}")
        if kind == "load" and index != 0:
            raise SceneError(f"step {index}: load must be the first step")
        steps.append(Step(index, kind, _normalize(index, kind, args, path.parent)))
    raw_watch = data.get("watch", {})
    if not isinstance(raw_watch, dict) or len(raw_watch) > 32:
        raise SceneError("'watch' must be an object of at most 32 {name: expr}")
    watch = {}
    for key, text in raw_watch.items():
        try:
            watch[str(key)] = Expr(text)
        except SceneError as error:
            raise SceneError(f"watch {key}: {error}") from None
    return Scene(name=name, path=path, steps=steps, description=str(data.get("description", "")),
                 watch=watch)


def load_scene(path) -> Scene:
    path = Path(path).resolve()
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as error:
        raise SceneError(f"{path}: invalid JSON: {error}") from None
    return parse_scene(data, path)


def parse_writes(writes, where, allow_count=False):
    """[{"addr": "0x7EF3AD", "type": "u8", "value": 1, "count"?: N}] -> [(addr, kind, value)]."""
    if not isinstance(writes, list) or not writes:
        raise SceneError(f"{where}: needs a non-empty 'writes' list")
    out = []
    for i, write in enumerate(writes):
        if not isinstance(write, dict):
            raise SceneError(f"{where}: write {i}: expected an object")
        kind = write.get("type", "u8")
        if kind not in ("u8", "u16"):
            raise SceneError(f"{where}: write {i}: type must be u8 or u16")
        addr = _hex(write.get("addr"), f"{where}: write {i}")
        value = _hex(write.get("value"), f"{where}: write {i}")
        if type(addr) is not int or type(value) is not int or not 0 <= value < (256 if kind == "u8" else 65536):
            raise SceneError(f"{where}: write {i}: bad addr/value")
        if "count" in write and not allow_count:
            raise SceneError(f"{where}: write {i}: count is only allowed in poke steps")
        count = _int(write.get("count", 1), f"{where}: write {i}.count", 1, 256)
        size = 1 if kind == "u8" else 2
        if allow_count and not 0x7E0000 <= addr <= 0x800000 - count * size:
            raise SceneError(f"{where}: write {i}: {addr:#x} is outside WRAM $7E0000-$7FFFFF")
        out.extend((addr + n * size, kind, value) for n in range(count))
    return out


def load_fixture(path: Path):
    """Existing fixture JSON: {"writes": [{"addr": "0x7EF3AD", "type": "u8", "value": 1}]}."""
    data = json.loads(Path(path).read_text())
    return parse_writes(data.get("writes") if isinstance(data, dict) else None, str(path))
