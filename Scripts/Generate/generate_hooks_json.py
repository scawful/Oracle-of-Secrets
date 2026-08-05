#!/usr/bin/env python3
"""
Generate hooks.json by scanning ASM for org $XXXXXX directives.

Heuristic: capture the first instruction after each org to classify hook kind.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

ORG_RE = re.compile(r'^\s*org\s+\$([0-9A-Fa-f]{1,6})(?=\s*(?::|;|$))')
ORG_DIRECTIVE_RE = re.compile(r"^\s*org\s+([^:;]+)", re.IGNORECASE)
ORG_BANK_PROOF_RE = re.compile(
    r"@manifest-org-bank\s*=\s*\$?([0-9A-Fa-f]{2})\b",
    re.IGNORECASE,
)
LABEL_RE = re.compile(r'^\s*[A-Za-z0-9_\.\+\-]+:\s*$')
INSTR_RE = re.compile(r'^\s*([A-Za-z]{2,5})\b\s*(.*)$')
COMMENT_RE = re.compile(r'^\s*;')
DATA_LABEL_RE = re.compile(
    r'^(Pool_|RoomData|RoomDataTiles|RoomDataObjects|OverworldMap|DungeonMap|'
    r'Map16|Map32|Tile16|Tile32|Gfx|GFX|Pal|Palette|BG|OAM|Msg|Text|Font|'
    r'Sfx|Sound|Table|Tables|Data|Buffer|Lookup|LUT|Offset|Offsets|Index|'
    r'Indices|Pointer|Pointers|Ptrs|Ptr|List|Lists|Array|Arrays|Tiles|Tilemap|'
    r'TileMap|Map|Maps)'
)
DATA_LABEL_SUFFIXES = (
    '_data', '_table', '_tables', '_tiles', '_tilemap', '_map', '_maps',
    '_gfx', '_pal', '_palettes', '_pointers', '_ptrs', '_ptr', '_lut',
)
LONG_ENTRY_RE = re.compile(r'(FullLongEntry|_LongEntry|_Long)$')
ABI_RE = re.compile(r'@abi\s+([A-Za-z0-9_]+)', re.IGNORECASE)
NO_RETURN_RE = re.compile(r'@no_return\b', re.IGNORECASE)
MX_RE = re.compile(r'^m(8|16)x(8|16)$', re.IGNORECASE)
HOOK_DIRECTIVE_RE = re.compile(r'@hook\b(.*)', re.IGNORECASE)
HOOK_KV_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(\"[^\"]*\"|'[^']*'|\S+)")

DEFINE_ASSIGN_RE = re.compile(
    r"^\s*!([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$"
)
DEFINE_REF_RE = re.compile(r"!([A-Za-z_][A-Za-z0-9_]*)\b")
DEFINE_ANY_ASSIGN_RE = re.compile(
    r"^\s*!([A-Za-z_][A-Za-z0-9_]*)\s*(#=|=)\s*(.*?)\s*$"
)
HEX_LITERAL_RE = re.compile(r"\$([0-9A-Fa-f]+)\b")
IF_DIRECTIVE_RE = re.compile(r"^\s*(if|elseif)\b(.*)$", re.IGNORECASE)
ELSE_DIRECTIVE_RE = re.compile(r"^\s*else\b", re.IGNORECASE)
ENDIF_DIRECTIVE_RE = re.compile(r"^\s*endif\b", re.IGNORECASE)
MACRO_START_RE = re.compile(
    r"^\s*macro\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.IGNORECASE
)
MACRO_END_RE = re.compile(r"^\s*endmacro\b", re.IGNORECASE)
MACRO_INVOKE_RE = re.compile(r"^\s*%([A-Za-z_][A-Za-z0-9_]*)\s*\(")

SKIP_DIRS = {
    '.git', '.context', '.claude', '.cursor',
    'Roms', 'Docs', 'docs',
    'build', 'bin', 'obj', 'Tools', 'tools', 'tests', 'node_modules',
    'ZScreamNew',
}

MODULE_DISABLE_FLAGS = {
    "Music": "DISABLE_MUSIC",
    "Overworld": "DISABLE_OVERWORLD",
    "Dungeons": "DISABLE_DUNGEON",
    "Sprites": "DISABLE_SPRITES",
    "Masks": "DISABLE_MASKS",
    "Items": "DISABLE_ITEMS",
    "Menu": "DISABLE_MENU",
}

EXPECTED_MX = {
    0x008000: (8, 8),     # Reset
    0x0080C9: (8, 8),     # NMI
    0x008781: (None, 8),  # JumpTableLocal (requires X=8-bit for stack math)
    0x008891: (8, 8),     # APU sync wait
    0x028364: (8, 8),     # Bed cutscene color init
    0x028A5B: (8, 8),     # Follower transition
    0x028BE7: (8, 8),     # Sanctuary song check
    0x02C0C3: (16, 8),    # Overworld camera bounds (A 16-bit, X 8-bit)
}

EXPECTED_NAMES = {
    0x008000: "Reset",
    0x0080C9: "NMI_Handler",
    0x008781: "JumpTableLocal",
    0x008891: "APU_SyncWait",
    0x028364: "BedCutscene_ColorFix",
    0x028A5B: "CheckForFollowerIntraroomTransition",
    0x028BE7: "Sanctuary_Song_Disable",
    0x02C0C3: "Overworld_SetCameraBounds",
}

FORCE_ABI_ADDRESSES = set(EXPECTED_MX.keys())

KIND_PRIORITY = {
    'jsl': 3,
    'jml': 3,
    'jsr': 3,
    'jmp': 3,
    'patch': 2,
    'data': 1,
}
PROTECTED_SIZE_ESTIMATE = {
    "jsl": 4,
    "jml": 4,
    "jsr": 3,
    "jmp": 3,
    "data": 8,
    "patch": 4,
}

@dataclass
class HookEntry:
    address: int
    name: str
    kind: str
    target: Optional[str]
    source: str
    note: str = ''
    module: str = ''
    skip_abi: bool = False
    abi_class: str = ''
    expected_m: Optional[int] = None
    expected_x: Optional[int] = None
    expected_exit_m: Optional[int] = None
    expected_exit_x: Optional[int] = None
    protected_size: Optional[int] = None


@dataclass(frozen=True)
class OrgDirective:
    expression: str
    address: Optional[int]
    source: str
    proof_bank: Optional[int] = None
    macro_name: Optional[str] = None
    anchor_banks: tuple[int, ...] = ()


def _module_from_path(path: Path, root: Path) -> str:
    rel = path.relative_to(root)
    if not rel.parts:
        return "root"
    return rel.parts[0]


def _is_data_label(label: Optional[str]) -> bool:
    if not label:
        return False
    if label.startswith('$'):
        return False
    if DATA_LABEL_RE.match(label):
        return True
    lower = label.lower()
    if lower.startswith('oracle_pos') and re.search(r'pos\d_', lower):
        return True
    for suffix in DATA_LABEL_SUFFIXES:
        if lower.endswith(suffix):
            return True
    return False


def _abi_class(label: Optional[str]) -> str:
    if not label:
        return ''
    if LONG_ENTRY_RE.search(label):
        return 'long_entry'
    return ''


def _scan_annotations(lines: list[str], start_idx: int) -> tuple[str, bool, Optional[int], Optional[int]]:
    abi_class = ''
    no_return = False
    expected_m = None
    expected_x = None

    for j in range(start_idx, min(start_idx + 20, len(lines))):
        line = lines[j]
        if ORG_DIRECTIVE_RE.match(line) and j != start_idx:
            break
        if COMMENT_RE.match(line) or ';' in line:
            m = ABI_RE.search(line)
            if m:
                token = m.group(1).lower()
                if token in ('long', 'long_entry', 'fulllongentry', 'full_long_entry'):
                    abi_class = 'long_entry'
                else:
                    mx = MX_RE.match(token)
                    if mx:
                        expected_m = int(mx.group(1))
                        expected_x = int(mx.group(2))
            if NO_RETURN_RE.search(line):
                no_return = True
    return abi_class, no_return, expected_m, expected_x


def _parse_bool(value: str) -> Optional[bool]:
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "y"}:
        return True
    if lowered in {"0", "false", "no", "n"}:
        return False
    return None


def _parse_int(value: str) -> Optional[int]:
    token = value.strip()
    if not token:
        return None
    if token.startswith(('"', "'")) and token.endswith(('"', "'")):
        token = token[1:-1]
    if token.startswith("$"):
        token = "0x" + token[1:]
    try:
        return int(token, 0)
    except ValueError:
        return None


def _scan_hook_directive(lines: list[str], start_idx: int) -> dict:
    directive: dict[str, object] = {}
    for j in range(start_idx, min(start_idx + 20, len(lines))):
        line = lines[j]
        if ORG_DIRECTIVE_RE.match(line) and j != start_idx:
            break
        if ";" in line:
            comment = line.split(";", 1)[1]
            m = HOOK_DIRECTIVE_RE.search(comment)
            if m:
                tail = m.group(1).strip()
                for kv in HOOK_KV_RE.finditer(tail):
                    key = kv.group(1).lower()
                    val = kv.group(2)
                    if val.startswith(('"', "'")) and val.endswith(('"', "'")):
                        val = val[1:-1]
                    directive[key] = val
                directive.setdefault("_present", True)
    return directive


def _parse_define_assignment(
    line: str, defines: Optional[dict[str, int]] = None
) -> tuple[str, int] | None:
    source = line.split(";", 1)[0]
    m = DEFINE_ASSIGN_RE.match(source)
    if not m:
        return None
    name = m.group(1).strip()
    value = _eval_numeric_expression(m.group(2), defines or {})
    if value is None:
        return None
    return name, value


def _load_global_defines(root: Path) -> dict[str, int]:
    """Parse the macro + override files that are always included before code."""
    defines: dict[str, int] = {}
    for rel in ("Util/macros.asm", "Config/module_flags.asm", "Config/feature_flags.asm"):
        path = root / rel
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            parsed = _parse_define_assignment(line, defines)
            if parsed is None:
                continue
            name, value = parsed
            defines[name] = value
    return defines


_ALLOWED_BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.LShift: lambda a, b: a << b,
    ast.RShift: lambda a, b: a >> b,
    ast.BitOr: lambda a, b: a | b,
    ast.BitAnd: lambda a, b: a & b,
    ast.BitXor: lambda a, b: a ^ b,
}
_ALLOWED_UNARYOPS = {
    ast.UAdd: lambda a: +a,
    ast.USub: lambda a: -a,
    ast.Invert: lambda a: ~a,
}
_ALLOWED_CMPOPS = {
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
}


def _eval_ast(node: ast.AST) -> int | bool:
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, bool)):
            return node.value
        raise ValueError(f"unsupported constant: {node.value!r}")
    if isinstance(node, ast.UnaryOp):
        op = _ALLOWED_UNARYOPS.get(type(node.op))
        if op is None:
            raise ValueError(f"unsupported unary op: {type(node.op).__name__}")
        return op(int(_eval_ast(node.operand)))
    if isinstance(node, ast.BinOp):
        op = _ALLOWED_BINOPS.get(type(node.op))
        if op is None:
            raise ValueError(f"unsupported bin op: {type(node.op).__name__}")
        return op(int(_eval_ast(node.left)), int(_eval_ast(node.right)))
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(bool(_eval_ast(v)) for v in node.values)
        if isinstance(node.op, ast.Or):
            return any(bool(_eval_ast(v)) for v in node.values)
        raise ValueError(f"unsupported bool op: {type(node.op).__name__}")
    if isinstance(node, ast.Compare):
        left = int(_eval_ast(node.left))
        for op_node, comp in zip(node.ops, node.comparators):
            right = int(_eval_ast(comp))
            op = _ALLOWED_CMPOPS.get(type(op_node))
            if op is None:
                raise ValueError(f"unsupported cmp op: {type(op_node).__name__}")
            if not op(left, right):
                return False
            left = right
        return True
    raise ValueError(f"unsupported expr node: {type(node).__name__}")


def _eval_condition(expr: str, defines: dict[str, int]) -> Optional[bool]:
    """Evaluate a simple Asar `if` expression using known define values.

    If the expression references unknown defines or uses unsupported syntax,
    returns None (caller should treat as unknown).
    """
    raw = expr.split(";", 1)[0].strip()
    if not raw:
        return None
    raw = raw.replace("&&", " and ").replace("||", " or ")
    unknown = False

    def repl(m: re.Match) -> str:
        nonlocal unknown
        name = m.group(1)
        if name not in defines:
            unknown = True
            return "0"
        return str(defines[name])

    cooked = DEFINE_REF_RE.sub(repl, raw)
    if unknown:
        return None
    cooked = HEX_LITERAL_RE.sub(lambda m: f"0x{m.group(1)}", cooked)
    try:
        tree = ast.parse(cooked, mode="eval")
        return bool(_eval_ast(tree))
    except Exception:
        return None


def _eval_numeric_expression(
    expr: str, defines: dict[str, int]
) -> Optional[int]:
    """Evaluate a simple numeric Asar expression, or return None."""
    raw = expr.split(";", 1)[0].strip()
    if not raw:
        return None
    unknown = False

    def repl(m: re.Match) -> str:
        nonlocal unknown
        name = m.group(1)
        if name not in defines:
            unknown = True
            return "0"
        return str(defines[name])

    cooked = DEFINE_REF_RE.sub(repl, raw)
    if unknown:
        return None
    cooked = HEX_LITERAL_RE.sub(lambda m: f"0x{m.group(1)}", cooked)
    try:
        tree = ast.parse(cooked, mode="eval")
        value = _eval_ast(tree)
    except Exception:
        return None
    if isinstance(value, bool):
        return int(value)
    return int(value)


def _expression_address_anchor_banks(
    expr: str, defines: Optional[dict[str, int]] = None
) -> tuple[int, ...]:
    """Return physical LoROM banks named by literals or known defines."""
    banks: set[int] = set()
    for match in HEX_LITERAL_RE.finditer(expr):
        value = int(match.group(1), 16)
        if value <= 0xFFFFFF and (value & 0xFFFF) >= 0x8000:
            banks.add((value >> 16) & 0x7F)
    known_defines = defines or {}
    for match in DEFINE_REF_RE.finditer(expr):
        value = known_defines.get(match.group(1))
        if (
            value is not None
            and 0 <= value <= 0xFFFFFF
            and (value & 0xFFFF) >= 0x8000
        ):
            banks.add((value >> 16) & 0x7F)
    return tuple(sorted(banks))


def _inline_org_payload(line: str) -> tuple[str, Optional[str]] | None:
    """Return the opcode/target if the org payload is on the same line.

    Example: `org $01CC18 : JML CustomTag` should classify as (jml, CustomTag).
    """
    directive = line.split(";", 1)[0]
    if ":" not in directive:
        return None
    _, tail = directive.split(":", 1)
    payload = tail.strip()
    if not payload:
        return None
    m = INSTR_RE.match(payload)
    if not m:
        return None
    op = m.group(1).lower()
    operand = m.group(2).strip() if m.group(2) else ""
    if op in ("jsl", "jml", "jsr", "jmp"):
        target = operand.split()[0] if operand else None
        return op, target
    if op in ("db", "dw", "dl", "dd", "incbin", "incsrc", "fill", "pad"):
        return "data", None
    return "patch", None


def _first_instruction(lines: list[str], start_idx: int, defines: dict[str, int]) -> tuple[str, Optional[str]]:
    """Return (kind, target) based on first meaningful instruction after org."""
    inline = _inline_org_payload(lines[start_idx])
    if inline is not None:
        return inline

    defines = dict(defines)
    active = True
    stack: list[dict[str, object]] = []

    for j in range(start_idx + 1, min(start_idx + 40, len(lines))):
        raw_line = lines[j]
        line = raw_line.strip()
        if not line or COMMENT_RE.match(line):
            continue

        # Conditional compilation (best-effort) so hooks.json matches the
        # ROM when feature/module flags toggle org payloads.
        directive = raw_line.split(";", 1)[0].strip()
        m_if = IF_DIRECTIVE_RE.match(directive)
        if m_if:
            kind = m_if.group(1).lower()
            expr = m_if.group(2).strip()
            parent_active = active
            cond = _eval_condition(expr, defines)
            if cond is None:
                # The payload could be any feasible branch. Use the largest
                # protected-size classification rather than understate it.
                return "data", None
            cond_val = bool(cond) if cond is not None else True
            if kind == "if":
                branch_taken = parent_active and cond_val
                active = parent_active and cond_val
                stack.append({"parent_active": parent_active, "branch_taken": branch_taken})
            else:  # elseif
                if not stack:
                    continue
                frame = stack[-1]
                parent_active = bool(frame["parent_active"])
                already = bool(frame["branch_taken"])
                if not parent_active or already:
                    active = False
                else:
                    active = parent_active and cond_val
                    frame["branch_taken"] = active
            continue
        if ELSE_DIRECTIVE_RE.match(directive):
            if not stack:
                continue
            frame = stack[-1]
            parent_active = bool(frame["parent_active"])
            already = bool(frame["branch_taken"])
            active = parent_active and not already
            frame["branch_taken"] = True
            continue
        if ENDIF_DIRECTIVE_RE.match(directive):
            if not stack:
                continue
            frame = stack.pop()
            active = bool(frame["parent_active"])
            continue

        if not active:
            continue

        parsed_define = _parse_define_assignment(raw_line, defines)
        if parsed_define is not None:
            name, value = parsed_define
            defines[name] = value
            continue
        assignment = DEFINE_ANY_ASSIGN_RE.match(
            raw_line.split(";", 1)[0]
        )
        if assignment:
            defines.pop(assignment.group(1), None)
            continue

        if LABEL_RE.match(line):
            continue
        # skip assembler directives
        if line.lower().startswith(('pushpc', 'pullpc', 'org', 'macro')):
            continue
        m = INSTR_RE.match(line)
        if not m:
            continue
        op = m.group(1).lower()
        operand = m.group(2).strip() if m.group(2) else ''

        if op in ('jsl', 'jml', 'jsr', 'jmp'):
            target = operand.split()[0] if operand else None
            return op, target
        if op in ('db', 'dw', 'dl', 'dd', 'incbin', 'incsrc', 'fill', 'pad'):
            return 'data', None
        return 'patch', None
    return 'patch', None


def _score_entry(entry: HookEntry) -> int:
    return KIND_PRIORITY.get(entry.kind, 0)


def _should_skip(path: Path) -> bool:
    for part in path.parts:
        if part in SKIP_DIRS:
            return True
    return False


def filter_active_asm_sources(
    root: Path,
    asm_paths: Iterable[Path],
    defines: Optional[dict[str, int]] = None,
) -> list[Path]:
    """Remove top-level modules disabled by the current build flags."""
    root = root.resolve()
    active_defines = _load_global_defines(root) if defines is None else defines
    disabled_roots = {
        source_root
        for source_root, flag in MODULE_DISABLE_FLAGS.items()
        if active_defines.get(flag) == 1
    }

    active_sources: list[Path] = []
    for source_path in asm_paths:
        asm_path = source_path.resolve()
        try:
            rel = asm_path.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                f"ASM source is outside repo root: {asm_path}"
            ) from exc
        if rel.parts and rel.parts[0] in disabled_roots:
            continue
        if (
            active_defines.get("DISABLE_PATCHES") == 1
            and rel.as_posix() == "Core/patches.asm"
        ):
            continue
        active_sources.append(asm_path)
    return active_sources


def _iter_active_lines(
    lines: list[str], initial_defines: dict[str, int]
) -> Iterable[tuple[int, str, dict[str, int]]]:
    """Yield active source lines with the numeric define state at that line."""
    defines = dict(initial_defines)
    active = True
    stack: list[dict[str, object]] = []
    for idx, line in enumerate(lines):
        directive = line.split(";", 1)[0].strip()
        m_if = IF_DIRECTIVE_RE.match(directive)
        if m_if:
            kind = m_if.group(1).lower()
            condition_defines = (
                dict(stack[-1]["entry_defines"])
                if kind == "elseif" and stack
                else defines
            )
            cond = _eval_condition(
                m_if.group(2).strip(), condition_defines
            )
            if kind == "if":
                parent_active = active
                active = parent_active and cond is not False
                stack.append(
                    {
                        "parent_active": parent_active,
                        "entry_defines": dict(defines),
                        "branch_states": [],
                        "current_branch_active": active,
                        "fallthrough_possible": (
                            parent_active and cond is not True
                        ),
                    }
                )
            elif stack:
                frame = stack[-1]
                if bool(frame["current_branch_active"]):
                    frame["branch_states"].append(dict(defines))
                defines = dict(frame["entry_defines"])
                fallthrough = bool(frame["fallthrough_possible"])
                active = fallthrough and cond is not False
                frame["current_branch_active"] = active
                frame["fallthrough_possible"] = (
                    fallthrough and cond is not True
                )
            continue
        if ELSE_DIRECTIVE_RE.match(directive):
            if stack:
                frame = stack[-1]
                if bool(frame["current_branch_active"]):
                    frame["branch_states"].append(dict(defines))
                defines = dict(frame["entry_defines"])
                active = bool(frame["fallthrough_possible"])
                frame["current_branch_active"] = active
                frame["fallthrough_possible"] = False
            continue
        if ENDIF_DIRECTIVE_RE.match(directive):
            if stack:
                frame = stack.pop()
                branch_states = frame["branch_states"]
                if bool(frame["current_branch_active"]):
                    branch_states.append(dict(defines))
                if bool(frame["fallthrough_possible"]):
                    branch_states.append(dict(frame["entry_defines"]))
                if branch_states:
                    common_names = set(branch_states[0])
                    for state in branch_states[1:]:
                        common_names.intersection_update(state)
                    defines = {
                        name: branch_states[0][name]
                        for name in common_names
                        if all(
                            state[name] == branch_states[0][name]
                            for state in branch_states[1:]
                        )
                    }
                else:
                    defines = dict(frame["entry_defines"])
                active = bool(frame["parent_active"])
            continue
        if not active:
            continue

        parsed = _parse_define_assignment(line, defines)
        if parsed is not None:
            name, value = parsed
            defines[name] = value
        else:
            assigned = DEFINE_ANY_ASSIGN_RE.match(line.split(";", 1)[0])
            if assigned:
                defines.pop(assigned.group(1), None)
        yield idx, line, dict(defines)


def scan_org_directives(
    root: Path,
    asm_paths: Optional[Iterable[Path]] = None,
) -> list[OrgDirective]:
    """Scan active literal/computed org directives with explicit proofs.

    Org directives inside macro definitions are considered active only when
    that macro is reachable from a real invocation in active source. This
    keeps unused macro templates from becoming false hooks while ensuring an
    invoked unresolved template cannot silently bypass manifest validation.
    """
    root = root.resolve()
    explicit_sources = asm_paths is not None
    global_defines = _load_global_defines(root)
    source_paths = list(root.rglob("*.asm") if asm_paths is None else asm_paths)
    active_sources = (
        list(source_paths)
        if explicit_sources
        else filter_active_asm_sources(root, source_paths, global_defines)
    )
    records_by_path: dict[
        Path, list[tuple[int, str, dict[str, int]]]
    ] = {}
    for source_path in active_sources:
        asm_path = source_path.resolve()
        if not explicit_sources and _should_skip(asm_path):
            continue
        try:
            lines = asm_path.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines()
        except OSError:
            if explicit_sources:
                raise
            continue
        records_by_path[asm_path] = list(
            _iter_active_lines(lines, global_defines)
        )

    root_invocations: set[str] = set()
    macro_edges: dict[str, set[str]] = {}
    for records in records_by_path.values():
        macro_name: Optional[str] = None
        for _, line, _ in records:
            source = line.split(";", 1)[0]
            macro_start = MACRO_START_RE.match(source)
            if macro_start:
                macro_name = macro_start.group(1).lower()
                macro_edges.setdefault(macro_name, set())
                continue
            if MACRO_END_RE.match(source):
                macro_name = None
                continue
            invocation = MACRO_INVOKE_RE.match(source)
            if not invocation:
                continue
            invoked = invocation.group(1).lower()
            if macro_name is None:
                root_invocations.add(invoked)
            else:
                macro_edges.setdefault(macro_name, set()).add(invoked)

    active_macros = set(root_invocations)
    pending = list(root_invocations)
    while pending:
        macro_name = pending.pop()
        for invoked in macro_edges.get(macro_name, set()):
            if invoked not in active_macros:
                active_macros.add(invoked)
                pending.append(invoked)

    directives: list[OrgDirective] = []
    for asm_path, records in records_by_path.items():
        macro_name = None
        for idx, line, defines in records:
            source_text = line.split(";", 1)[0]
            macro_start = MACRO_START_RE.match(source_text)
            if macro_start:
                macro_name = macro_start.group(1).lower()
                continue
            if MACRO_END_RE.match(source_text):
                macro_name = None
                continue
            match = ORG_DIRECTIVE_RE.match(source_text)
            if not match or (
                macro_name is not None and macro_name not in active_macros
            ):
                continue
            expression = match.group(1).strip()
            proof_match = ORG_BANK_PROOF_RE.search(line)
            proof_bank = (
                int(proof_match.group(1), 16) if proof_match else None
            )
            directives.append(
                OrgDirective(
                    expression=expression,
                    address=_eval_numeric_expression(expression, defines),
                    source=f"{asm_path.relative_to(root)}:{idx + 1}",
                    proof_bank=proof_bank,
                    macro_name=macro_name,
                    anchor_banks=_expression_address_anchor_banks(
                        expression, defines
                    ),
                )
            )
    return directives


def scan_hooks(
    root: Path,
    asm_paths: Optional[Iterable[Path]] = None,
) -> list[HookEntry]:
    root = root.resolve()
    hooks_by_addr: dict[int, HookEntry] = {}
    explicit_sources = asm_paths is not None

    global_defines = _load_global_defines(root)
    source_paths = root.rglob('*.asm') if asm_paths is None else asm_paths
    active_sources = (
        list(source_paths)
        if explicit_sources
        else filter_active_asm_sources(root, source_paths, global_defines)
    )
    active_macros = {
        directive.macro_name
        for directive in scan_org_directives(root, active_sources)
        if directive.macro_name is not None
    }
    for source_path in active_sources:
        asm_path = source_path.resolve()
        if not explicit_sources and _should_skip(asm_path):
            continue
        try:
            asm_path.relative_to(root)
        except ValueError:
            if explicit_sources:
                raise ValueError(
                    f"Explicit ASM source is outside repo root: {asm_path}"
                )
            continue
        try:
            lines = asm_path.read_text(encoding='utf-8', errors='ignore').splitlines()
        except OSError:
            if explicit_sources:
                raise
            continue

        macro_name: Optional[str] = None
        for idx, line, defines in _iter_active_lines(lines, global_defines):
            source_text = line.split(";", 1)[0]
            macro_start = MACRO_START_RE.match(source_text)
            if macro_start:
                macro_name = macro_start.group(1).lower()
                continue
            if MACRO_END_RE.match(source_text):
                macro_name = None
                continue
            m = ORG_DIRECTIVE_RE.match(source_text)
            if not m or (
                macro_name is not None and macro_name not in active_macros
            ):
                continue
            addr = _eval_numeric_expression(m.group(1), defines)
            if addr is None:
                continue
            kind, target = _first_instruction(lines, idx, defines)
            abi_class_note, no_return, ann_m, ann_x = _scan_annotations(lines, idx)
            hook_directive = _scan_hook_directive(lines, idx)
            source = f"{asm_path.relative_to(root)}:{idx + 1}"
            directive_name = hook_directive.get("name")
            directive_kind = hook_directive.get("kind")
            directive_target = hook_directive.get("target")
            name = (directive_name or target or f"hook_{addr:06X}")
            if directive_kind:
                kind = str(directive_kind).lower()
            if directive_target:
                target = str(directive_target)
            module = _module_from_path(asm_path, root)
            skip_abi = (
                kind == 'data'
                or kind in ('jmp', 'jml')
                or _is_data_label(name)
                or _is_data_label(target)
                or (kind == 'patch' and name.startswith('hook_'))
                or name.startswith('.')
                or name.startswith('$')
            )
            directive_skip = hook_directive.get("skip_abi")
            if directive_skip is not None:
                parsed = _parse_bool(str(directive_skip))
                if parsed is not None:
                    skip_abi = parsed
            if addr in EXPECTED_NAMES and (name.startswith('hook_') or name.startswith('.') or name.startswith('$')):
                name = EXPECTED_NAMES[addr]
            directive_abi = hook_directive.get("abi") or hook_directive.get("abi_class")
            if directive_abi:
                abi_class = str(directive_abi)
            else:
                abi_class = abi_class_note or _abi_class(name or target)
            if no_return:
                skip_abi = True
            if addr in FORCE_ABI_ADDRESSES:
                skip_abi = False
            directive_expected_m = _parse_int(str(hook_directive.get("expected_m"))) if hook_directive.get("expected_m") is not None else None
            directive_expected_x = _parse_int(str(hook_directive.get("expected_x"))) if hook_directive.get("expected_x") is not None else None
            if directive_expected_m is not None:
                ann_m = directive_expected_m
            if directive_expected_x is not None:
                ann_x = directive_expected_x
            # Explicit exit expectations from @hook directive
            ann_exit_m = _parse_int(str(hook_directive.get("expected_exit_m"))) if hook_directive.get("expected_exit_m") is not None else None
            ann_exit_x = _parse_int(str(hook_directive.get("expected_exit_x"))) if hook_directive.get("expected_exit_x") is not None else None
            directive_module = hook_directive.get("module")
            if directive_module:
                module = str(directive_module)
            note = ''
            directive_note = hook_directive.get("note")
            if directive_note:
                note = str(directive_note)
            entry = HookEntry(
                address=addr,
                name=name,
                kind=kind,
                target=target,
                source=source,
                note=note,
                module=module,
                skip_abi=skip_abi,
                abi_class=abi_class,
                expected_m=ann_m,
                expected_x=ann_x,
                expected_exit_m=ann_exit_m,
                expected_exit_x=ann_exit_x,
                protected_size=PROTECTED_SIZE_ESTIMATE.get(kind, 4),
            )

            existing = hooks_by_addr.get(addr)
            if existing:
                maximum_size = max(
                    existing.protected_size or 4,
                    entry.protected_size or 4,
                )
                existing.protected_size = maximum_size
                entry.protected_size = maximum_size
            if not existing or _score_entry(entry) > _score_entry(existing):
                hooks_by_addr[addr] = entry

    return sorted(hooks_by_addr.values(), key=lambda e: e.address)


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate hooks.json from ASM org directives')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2],
                        help='Oracle repo root (default: repo root)')
    parser.add_argument('-o', '--output', type=Path, default=Path('Roms/hooks.json'),
                        help='Output hooks.json path (default: Roms/hooks.json)')
    parser.add_argument('--rom', type=Path, default=Path('Roms/oos168x.sfc'),
                        help='ROM path for metadata (optional)')
    args = parser.parse_args()

    root = args.root.resolve()
    output = (root / args.output).resolve() if not args.output.is_absolute() else args.output

    hooks = scan_hooks(root)

    rom_meta = {}
    rom_path = (root / args.rom).resolve() if not args.rom.is_absolute() else args.rom
    if rom_path.exists():
        rom_meta['path'] = str(rom_path.relative_to(root))
        try:
            sha1 = hashlib.sha1(rom_path.read_bytes()).hexdigest()
            rom_meta['sha1'] = sha1
        except Exception:
            pass

    data = {
        'version': 1,
        'rom': rom_meta,
        'hooks': []
    }

    for entry in hooks:
        hook = {
            'name': entry.name,
            'address': f"0x{entry.address:06X}",
            'kind': entry.kind,
            'source': entry.source,
            'module': entry.module,
            'skip_abi': bool(entry.skip_abi),
        }
        if entry.abi_class:
            hook['abi_class'] = entry.abi_class

        # Resolve entry register-width expectations
        eff_m = entry.expected_m
        eff_x = entry.expected_x
        if eff_m is None and entry.address in EXPECTED_MX:
            eff_m = EXPECTED_MX[entry.address][0]
        if eff_x is None and entry.address in EXPECTED_MX:
            eff_x = EXPECTED_MX[entry.address][1]
        if eff_m is not None:
            hook['expected_m'] = eff_m
        if eff_x is not None:
            hook['expected_x'] = eff_x

        # Resolve exit register-width expectations.
        # Explicit @hook values take priority. Otherwise, auto-propagate:
        # hooks that redirect to or return to vanilla code (jsl, jml) should
        # restore the caller's register width on exit.
        exit_m = entry.expected_exit_m
        exit_x = entry.expected_exit_x
        if exit_m is None and entry.kind in ('jsl', 'jml') and eff_m is not None:
            exit_m = eff_m
        if exit_x is None and entry.kind in ('jsl', 'jml') and eff_x is not None:
            exit_x = eff_x
        if exit_m is not None:
            hook['expected_exit_m'] = exit_m
        if exit_x is not None:
            hook['expected_exit_x'] = exit_x

        if entry.target:
            hook['target'] = entry.target
        if entry.note:
            hook['note'] = entry.note
        data['hooks'].append(hook)

    output.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Wrote {len(hooks)} hooks to {output}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
