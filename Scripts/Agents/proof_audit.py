#!/usr/bin/env python3
"""Audit a native proof script against its proof contract.

A proof contract (JSON, next to the script) names the RAM/SRAM bytes that the
change under test is supposed to produce. A proof that writes those bytes
itself proves nothing. This tool reads the script statically (Python AST) and
reports:

1. FAIL: a write to a state-under-test byte outside a marked control block.
2. FAIL: a route function that never drives joypad input (directly or through
   local helpers).
3. FAIL: an incomplete contract (no routes, no control, fewer than 3 break-it
   cases for T3).
4. INFO: every other write (setup), savestate loads, and writes whose address
   could not be resolved, so a reviewer reads them in one list.

Markers in the proof script (`control` and `setup`, each with -begin/-end):
    w8(0x7EF3CC, 0x08)  # proof: control      baseline/side-by-side run only
    # proof: setup-begin                       reset start state before a route
    w8(0x7EF3CC, 0x00)
    # proof: setup-end
A setup-marked write to a state-under-test byte passes only when no input call
comes before it in the same function. Reviewers read every marked line.

Input is any call named in BASE_INPUT_NAMES or contract `input_functions`,
send_command("INPUT", ...), a `buttons=` style keyword, or a button string
argument such as case.tick(2, "up").

Contract format (`proof_contract.json`):
    {
      "row": "QUEUE220",
      "tier": "T2",
      "script": "run_crossing_check.py",
      "under_test": ["0x7EF3CC", "0x7EF3C9", "0x7EF3BD"],
      "setup": [{"addr": "0x7EF3CA", "why": "start in the Abyss"}],
      "routes": [{"name": "warp tile $6A -> $2A", "function": "route_warp_tile"}],
      "control": "baseline build, same routes; old behavior shown",
      "break_it": ["sword warp", "save and quit", "spawn menu"],
      "write_functions": ["case.w"],
      "input_functions": ["drive_route"]
    }

Addresses accept "0x7EF3CC", "$7EF3CC" or ranges "0x7E0DD0-0x7E0DDF".
Low RAM ($0000-$1FFF, banks $00-$3F/$80-$BF) is folded into $7E.

Usage:
    python3 Scripts/Agents/proof_audit.py path/to/proof_contract.json
    python3 Scripts/Agents/proof_audit.py contract.json --json
    python3 Scripts/Agents/proof_audit.py --template > proof_contract.json

Exit: 0 PASS, 1 FAIL (or unresolved writes with --strict), 2 bad input.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Calls that write emulator memory directly. Wrappers around these are found
# automatically (a local function that passes one of its parameters as the
# address becomes a write function too).
BASE_WRITE_NAMES = {
    "write_memory", "write_block", "write_mem", "mem_write", "poke", "poke8", "poke16",
    "write_ram", "write_wram", "write_sram", "write8", "write16", "write24",
    "write_u8", "write_u16", "w8", "w16", "w24", "wr8", "wr16",
}
# Calls that drive player input.
BASE_INPUT_NAMES = {
    "press_button", "press", "tap", "hold", "hold_buttons", "set_input", "input",
    "joypad", "walk", "walk_to", "walk_form", "release_buttons", "inputs",
}
SEND_COMMAND = "send_command"
STATE_LOAD_NAMES = {"load_state", "loadstate", "load_savestate"}
# Any call that carries a joypad button also drives input, e.g. case.tick(2, "up").
INPUT_KEYWORDS = {"buttons", "button", "keys", "pad", "joypad", "held"}
BUTTON = r"(up|down|left|right|a|b|x|y|l|r|start|select)"
BUTTON_TEXT = re.compile(rf"^\s*{BUTTON}(\s*[+,| ]\s*{BUTTON})*\s*$", re.IGNORECASE)


def marker(kind: str, suffix: str = "") -> re.Pattern:
    tail = rf"-{suffix}\b" if suffix else r"\b(?!-)"
    return re.compile(rf"#\s*proof:\s*{kind}{tail}")

TEMPLATE = {
    "row": "QUEUE000",
    "tier": "T2",
    "script": "run_proof.py",
    "under_test": ["0x7EF3CC"],
    "setup": [{"addr": "0x7EF3CA", "why": "start state: name a checkpoint id or save file"}],
    "routes": [{"name": "real player route 1", "function": "route_one"}],
    "control": "same steps on the baseline build show the old behavior",
    "break_it": [],
    "write_functions": [],
}


# ---------------------------------------------------------------- addresses

def fold(addr: int) -> int:
    """Fold SNES low-RAM mirrors into bank $7E."""
    bank, off = addr >> 16, addr & 0xFFFF
    if addr < 0x2000:
        return 0x7E0000 | addr
    if (bank <= 0x3F or 0x80 <= bank <= 0xBF) and off < 0x2000:
        return 0x7E0000 | off
    return addr


def parse_addr(text: str) -> int:
    t = str(text).strip().replace("$", "0x")
    return int(t, 16) if not t.lower().startswith("0x") else int(t, 0)


def parse_range(text: str) -> tuple[int, int]:
    parts = str(text).split("-")
    if len(parts) == 1:
        a = fold(parse_addr(parts[0]))
        return a, a
    if len(parts) == 2:
        return fold(parse_addr(parts[0])), fold(parse_addr(parts[1]))
    raise ValueError(f"bad address or range: {text!r}")


def fmt(addr: int) -> str:
    return f"${addr:06X}"


# ---------------------------------------------------------------- AST model

def call_name(node: ast.Call) -> str:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return ""


def dotted_name(node: ast.Call) -> str:
    parts = []
    f = node.func
    while isinstance(f, ast.Attribute):
        parts.append(f.attr)
        f = f.value
    if isinstance(f, ast.Name):
        parts.append(f.id)
    return ".".join(reversed(parts))


def width_from_name(name: str) -> int | None:
    if "24" in name:
        return 3
    if "16" in name or name.endswith("word"):
        return 2
    return None


class Constants:
    """Integer constants assigned exactly once (any scope) in the script."""

    def __init__(self, tree: ast.AST):
        seen: dict[str, list[ast.expr]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name):
                seen.setdefault(node.targets[0].id, []).append(node.value)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                    and node.value is not None:
                seen.setdefault(node.target.id, []).append(node.value)
        self.exprs = {k: v[0] for k, v in seen.items() if len(v) == 1}
        self.cache: dict[str, int | None] = {}

    def lookup(self, name: str, depth: int) -> int | None:
        if name in self.cache:
            return self.cache[name]
        if name not in self.exprs or depth > 8:
            return None
        self.cache[name] = None  # cycle guard
        value = self.eval(self.exprs[name], depth + 1)
        self.cache[name] = value
        return value

    def eval(self, node: ast.expr, depth: int = 0) -> int | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, int) \
                and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.Name):
            return self.lookup(node.id, depth)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            v = self.eval(node.operand, depth)
            return -v if v is not None else None
        if isinstance(node, ast.BinOp):
            a, b = self.eval(node.left, depth), self.eval(node.right, depth)
            if a is None or b is None:
                return None
            ops = {ast.Add: a + b, ast.Sub: a - b, ast.BitOr: a | b, ast.BitAnd: a & b,
                   ast.Mult: a * b}
            if isinstance(node.op, ast.LShift):
                return a << b
            if isinstance(node.op, ast.RShift):
                return a >> b
            return ops.get(type(node.op))
        return None


def names_in(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def enclosing_functions(tree: ast.AST) -> dict[int, ast.FunctionDef]:
    """Map id(call node) -> innermost enclosing function."""
    owner: dict[int, ast.FunctionDef] = {}

    def visit(node: ast.AST, fn):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, child)
            else:
                if isinstance(child, ast.Call) and fn is not None:
                    owner[id(child)] = fn
                visit(child, fn)

    visit(tree, None)
    return owner


def params(fn) -> list[str]:
    a = fn.args
    return [p.arg for p in a.posonlyargs + a.args if p.arg not in ("self", "cls")]


@dataclass
class WriteFn:
    addr_index: int          # positional index of the address argument at call sites
    width: int | None        # None = unknown (use 1)


@dataclass
class Write:
    line: int
    callee: str
    addrs: list[int] = field(default_factory=list)   # resolved, folded, all bytes
    text: str = ""
    control: bool = False
    setup: bool = False
    after_input: int | None = None   # line of an earlier input call in the same function


@dataclass
class Report:
    status: str = "PASS"
    script: str = ""
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    under_test_writes: list[dict] = field(default_factory=list)
    control_writes: list[dict] = field(default_factory=list)
    start_state_writes: list[dict] = field(default_factory=list)
    setup_writes: list[dict] = field(default_factory=list)
    unresolved_writes: list[dict] = field(default_factory=list)
    state_loads: list[int] = field(default_factory=list)
    routes: list[dict] = field(default_factory=list)


class Audit:
    def __init__(self, source: str, extra_write_names: set[str] | None = None):
        self.source = source
        self.lines = source.splitlines()
        self.tree = ast.parse(source)
        self.consts = Constants(self.tree)
        self.owner = enclosing_functions(self.tree)
        self.functions: dict[str, list] = {}
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.functions.setdefault(node.name, []).append(node)
        self.calls = [n for n in ast.walk(self.tree) if isinstance(n, ast.Call)]
        self.extra = set(extra_write_names or ())
        self.write_fns: dict[str, WriteFn] = {}
        for name in BASE_WRITE_NAMES:
            self.write_fns[name] = WriteFn(0, width_from_name(name))
        self.input_names = set(BASE_INPUT_NAMES)
        self.control_lines = self._marked("control")
        self.setup_lines = self._marked("setup")
        self._find_wrappers()

    # -- markers
    def _marked(self, kind: str) -> set[int]:
        line_re, begin, end = marker(kind), marker(kind, "begin"), marker(kind, "end")
        marked: set[int] = set()
        inside = False
        for i, line in enumerate(self.lines, start=1):
            if begin.search(line):
                inside = True
            if inside or line_re.search(line):
                marked.add(i)
            if end.search(line):
                inside = False
        return marked

    def in_lines(self, node: ast.Call, lines: set[int]) -> bool:
        end = getattr(node, "end_lineno", node.lineno) or node.lineno
        return any(n in lines for n in range(node.lineno, end + 1))

    def is_control(self, node: ast.Call) -> bool:
        return self.in_lines(node, self.control_lines)

    # -- input detection
    def is_input_call(self, n: ast.Call) -> bool:
        name = call_name(n)
        if name in self.input_names:
            return True
        if name == SEND_COMMAND and n.args and isinstance(n.args[0], ast.Constant) \
                and str(n.args[0].value).upper() == "INPUT":
            return True
        for kw in n.keywords:
            if kw.arg in INPUT_KEYWORDS and not (
                    isinstance(kw.value, ast.Constant) and kw.value.value in (None, "", 0)):
                return True
        for a in n.args:
            if isinstance(a, ast.Constant) and isinstance(a.value, str) \
                    and BUTTON_TEXT.match(a.value):
                return True
        return False

    def first_input_line(self, fn) -> int | None:
        lines = [n.lineno for n in ast.walk(fn) if isinstance(n, ast.Call)
                 and (self.is_input_call(n) or (call_name(n) in self.functions
                      and call_name(n) != fn.name and self.reaches_input(call_name(n))))]
        return min(lines) if lines else None

    # -- write detection
    def write_target(self, node: ast.Call) -> WriteFn | None:
        name = call_name(node)
        if dotted_name(node) in self.extra or name in self.extra:
            return WriteFn(0, width_from_name(name))
        if name == SEND_COMMAND and node.args and isinstance(node.args[0], ast.Constant) \
                and str(node.args[0].value).upper() in ("WRITE", "WRITE_MEMORY", "POKE"):
            return WriteFn(-1, 1)
        return self.write_fns.get(name)

    def addr_expr(self, node: ast.Call, wf: WriteFn) -> ast.expr | None:
        if wf.addr_index == -1:  # send_command("WRITE", {"addr": ...})
            if len(node.args) > 1 and isinstance(node.args[1], ast.Dict):
                for k, v in zip(node.args[1].keys, node.args[1].values):
                    if isinstance(k, ast.Constant) and k.value in ("addr", "address"):
                        return v
            return None
        if len(node.args) > wf.addr_index:
            return node.args[wf.addr_index]
        for kw in node.keywords:
            if kw.arg in ("addr", "address"):
                return kw.value
        return None

    def _find_wrappers(self) -> None:
        changed = True
        while changed:
            changed = False
            for call in self.calls:
                wf = self.write_target(call)
                fn = self.owner.get(id(call))
                if wf is None or fn is None or fn.name in self.write_fns \
                        or not self.wrapper_shaped(fn):
                    continue
                expr = self.addr_expr(call, wf)
                if expr is None:
                    continue
                ps = params(fn)
                used = [p for p in ps if p in names_in(expr)]
                if used:
                    width = width_from_name(fn.name) or wf.width
                    self.write_fns[fn.name] = WriteFn(ps.index(used[0]), width)
                    changed = True

    def wrapper_shaped(self, fn) -> bool:
        """A write wrapper is short, has no loops and drives no input.

        Route or helper functions that take an address-like parameter keep their
        writes visible instead of being folded into their call sites.
        """
        body = fn.body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            body = body[1:]
        if len(body) > 4:
            return False
        if any(isinstance(n, (ast.For, ast.While, ast.AsyncFor)) for n in ast.walk(fn)):
            return False
        return not self.reaches_input(fn.name)

    def is_wrapper_internal(self, call: ast.Call, expr: ast.expr) -> bool:
        fn = self.owner.get(id(call))
        return bool(fn and fn.name in self.write_fns and set(params(fn)) & names_in(expr))

    def writes(self) -> list[Write]:
        out = []
        first_input: dict[int, int | None] = {}
        for call in self.calls:
            wf = self.write_target(call)
            if wf is None:
                continue
            expr = self.addr_expr(call, wf)
            if expr is not None and self.is_wrapper_internal(call, expr):
                continue
            text = (ast.get_source_segment(self.source, call) or call_name(call)).strip()
            w = Write(call.lineno, call_name(call), text=" ".join(text.split())[:120],
                      control=self.is_control(call),
                      setup=self.in_lines(call, self.setup_lines))
            fn = self.owner.get(id(call))
            if fn is not None:
                if id(fn) not in first_input:
                    first_input[id(fn)] = self.first_input_line(fn)
                fi = first_input[id(fn)]
                if fi is not None and fi < call.lineno:
                    w.after_input = fi
            value = self.consts.eval(expr) if expr is not None else None
            if value is not None:
                width = wf.width or 1
                if call_name(call) == "write_block" and len(call.args) > 1:
                    v = call.args[1]
                    if isinstance(v, (ast.List, ast.Tuple)):
                        width = len(v.elts)
                    elif isinstance(v, ast.Constant) and isinstance(v.value, (bytes, str)):
                        width = len(v.value)
                w.addrs = [fold(value + i) for i in range(width)]
            out.append(w)
        return sorted(out, key=lambda w: w.line)

    # -- input reachability
    def calls_in(self, fn) -> set[str]:
        return {call_name(n) for n in ast.walk(fn) if isinstance(n, ast.Call)}

    def has_input(self, fn) -> bool:
        return any(isinstance(n, ast.Call) and self.is_input_call(n) for n in ast.walk(fn))

    def reaches_input(self, name: str) -> bool:
        seen, stack = set(), [name]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            for fn in self.functions.get(cur, []):
                if self.has_input(fn):
                    return True
                stack.extend(c for c in self.calls_in(fn) if c in self.functions)
        return False

    def state_loads(self) -> list[int]:
        return sorted(c.lineno for c in self.calls if call_name(c) in STATE_LOAD_NAMES)


# ---------------------------------------------------------------- contract

def load_contract(path: Path) -> dict:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("contract must be a JSON object")
    return data


def run(contract_path: Path, script_override: Path | None = None) -> Report:
    c = load_contract(contract_path)
    rep = Report()

    tier = str(c.get("tier", "")).upper()
    if tier not in ("T2", "T3"):
        rep.failures.append(f"tier must be T2 or T3 (got {c.get('tier')!r})")
    try:
        under = [parse_range(a) for a in c.get("under_test", [])]
    except ValueError as exc:
        raise ValueError(f"under_test: {exc}") from exc
    if not under:
        rep.failures.append("under_test is empty: list the bytes the change should produce")
    routes = c.get("routes", [])
    if not routes:
        rep.failures.append("routes is empty: list every real way a player reaches the behavior")
    if not str(c.get("control", "")).strip():
        rep.failures.append("control is empty: name the baseline run that shows the old behavior")
    if tier == "T3" and len(c.get("break_it", [])) < 3:
        rep.failures.append(f"T3 needs 3 break_it cases (got {len(c.get('break_it', []))})")
    setup_ok = set()
    for s in c.get("setup", []):
        lo, hi = parse_range(s.get("addr", ""))
        setup_ok.update(range(lo, hi + 1))
        if not str(s.get("why", "")).strip():
            rep.warnings.append(f"setup {s.get('addr')} has no 'why'")

    script = script_override or (contract_path.parent / c.get("script", ""))
    if not script.is_file():
        raise ValueError(f"script not found: {script}")
    rep.script = str(script)
    audit = Audit(script.read_text(), set(c.get("write_functions", [])))
    audit.input_names |= set(c.get("input_functions", []))

    def hits(addrs):
        return sorted({a for a in addrs for lo, hi in under if lo <= a <= hi})

    for w in audit.writes():
        row = {"line": w.line, "call": w.text, "bytes": [fmt(a) for a in w.addrs]}
        if not w.addrs:
            rep.unresolved_writes.append(row)
            continue
        bad = hits(w.addrs)
        if bad and w.control:
            rep.control_writes.append(row)
        elif bad and w.setup and w.after_input is None:
            row["under_test"] = [fmt(a) for a in bad]
            rep.start_state_writes.append(row)
        elif bad and w.setup:
            row["under_test"] = [fmt(a) for a in bad]
            rep.under_test_writes.append(row)
            rep.failures.append(
                f"line {w.line}: marked setup but runs after input (line {w.after_input}) "
                f"in the same function; writes {', '.join(fmt(a) for a in bad)}: {w.text}")
        elif bad:
            row["under_test"] = [fmt(a) for a in bad]
            rep.under_test_writes.append(row)
            rep.failures.append(
                f"line {w.line}: writes state under test {', '.join(fmt(a) for a in bad)}: {w.text}")
        else:
            row["declared"] = all(a in setup_ok for a in w.addrs)
            rep.setup_writes.append(row)
            if not row["declared"]:
                rep.warnings.append(
                    f"line {w.line}: setup write {', '.join(row['bytes'])} not listed in contract setup")

    for r in routes:
        fn = r.get("function")
        entry = {"name": r.get("name", ""), "function": fn}
        if not fn:
            entry["input"] = "not checked"
            rep.warnings.append(f"route {r.get('name')!r}: no function named; input not checked")
        elif fn not in audit.functions:
            entry["input"] = "missing"
            rep.failures.append(f"route {r.get('name')!r}: function {fn!r} not in script")
        else:
            ok = audit.reaches_input(fn)
            entry["input"] = "yes" if ok else "no"
            if not ok:
                rep.failures.append(f"route {r.get('name')!r}: {fn}() drives no joypad input")
        rep.routes.append(entry)

    rep.state_loads = audit.state_loads()
    if rep.state_loads:
        rep.warnings.append(
            f"{len(rep.state_loads)} savestate load(s) at lines {rep.state_loads}: "
            "a savestate can carry state under test; name its source in setup")
    if rep.unresolved_writes:
        rep.warnings.append(f"{len(rep.unresolved_writes)} write(s) with unresolved address")
    rep.status = "FAIL" if rep.failures else "PASS"
    return rep


def print_report(rep: Report) -> None:
    print(f"{rep.status}  {rep.script}")
    for f in rep.failures:
        print(f"  FAIL  {f}")
    for w in rep.warnings:
        print(f"  WARN  {w}")
    print(f"  under-test writes: {len(rep.under_test_writes)}  control: "
          f"{len(rep.control_writes)}  start-state: {len(rep.start_state_writes)}  "
          f"setup: {len(rep.setup_writes)}  unresolved: {len(rep.unresolved_writes)}")
    for s in rep.start_state_writes:
        print(f"  start-state line {s['line']}: {s['call']}")
    for r in rep.routes:
        print(f"  route {r['name']!r} -> {r['function']}: input {r['input']}")
    if rep.unresolved_writes:
        print("  unresolved writes (read these):")
        for u in rep.unresolved_writes[:20]:
            print(f"    line {u['line']}: {u['call']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("contract", nargs="?", type=Path, help="proof_contract.json")
    ap.add_argument("--script", type=Path, help="override the contract's script path")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--strict", action="store_true", help="unresolved write addresses fail")
    ap.add_argument("--template", action="store_true", help="print a contract template")
    args = ap.parse_args(argv)
    if args.template:
        print(json.dumps(TEMPLATE, indent=2))
        return 0
    if args.contract is None:
        ap.error("contract path required")
    try:
        rep = run(args.contract, args.script)
    except (ValueError, OSError, SyntaxError, json.JSONDecodeError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    if args.strict and rep.unresolved_writes and rep.status == "PASS":
        rep.status = "FAIL"
        rep.failures.append("--strict: unresolved write addresses")
    if args.json:
        print(json.dumps(rep.__dict__, indent=2))
    else:
        print_report(rep)
    return 0 if rep.status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
