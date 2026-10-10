#!/usr/bin/env python3
"""Shared Asar source parsing for Oracle tooling.

Evaluates `!define` assignments and `if`/`elseif`/`else`/`endif` blocks so
tools can walk only the active source lines. Used by generate_hooks_json.py
and generate_hack_manifest.py. Also owns their shared reachable include graph.
"""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Iterable, Optional

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


class SourceGraphError(RuntimeError):
    """Raised when reachable ASM source cannot be resolved safely."""


# Literal Asar source include. Paths may be quoted or bare; comments are
# stripped before matching so archived `; incsrc ...` lines stay unreachable.
INCSRC_RE = re.compile(
    r"^\s*incsrc\s+(?:\"([^\"]+)\"|'([^']+)'|([^\s;]+))",
    re.IGNORECASE,
)


def _parse_incsrc(line: str) -> Optional[str]:
    """Return a literal `incsrc` path from uncommented source text."""
    source = line.split(";", 1)[0]
    match = INCSRC_RE.match(source)
    if not match:
        return None
    return next(value for value in match.groups() if value is not None)


def _iter_active_incsrcs(
    lines: list[str],
    global_defines: dict[str, int],
) -> Iterable[tuple[int, str]]:
    """Yield literal includes whose enclosing Asar condition is active."""
    for line_index, line, _ in _iter_active_lines(lines, global_defines):
        include_text = _parse_incsrc(line)
        if include_text is not None:
            yield line_index + 1, include_text


def _is_case_exact_file(candidate: Path, root: Path) -> bool:
    """Return whether a candidate exists with repository-exact path casing."""
    normalized = Path(os.path.normpath(candidate))
    try:
        relative = normalized.relative_to(root)
    except ValueError:
        # Preserve the caller's existing outside-root diagnostic.
        return candidate.is_file()

    current = root
    for part in relative.parts:
        try:
            entries = {entry.name: entry for entry in current.iterdir()}
        except OSError:
            return False
        if part not in entries:
            return False
        current = entries[part]
    return current.is_file()


def collect_reachable_asm_sources(
    root: Path,
    entry_point: Path = Path("Oracle_main.asm"),
    defines: Optional[dict[str, int]] = None,
) -> list[Path]:
    """Collect the transitive literal `incsrc` graph for the build entry.

    Asar sources in this repository use both paths relative to the including
    file and repo-root-relative paths. Follow every feasible conditional edge,
    treat literal includes as authoritative regardless of directory name, and
    fail closed when a reachable include or cross-file global-define state
    cannot be resolved safely.
    """
    resolved_root = root.resolve()
    entry = entry_point if entry_point.is_absolute() else resolved_root / entry_point
    entry = entry.resolve()
    if not entry.is_file():
        raise SourceGraphError(f"ASM entry point not found: {entry}")
    if not entry.is_relative_to(resolved_root):
        raise SourceGraphError(
            f"ASM entry point is outside repo root: {entry}"
        )

    active_defines = (
        _load_global_defines(resolved_root)
        if defines is None
        else dict(defines)
    )
    pending = [entry]
    reachable: set[Path] = set()
    while pending:
        asm_path = pending.pop()
        if asm_path in reachable:
            continue
        reachable.add(asm_path)

        try:
            lines = asm_path.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines()
        except OSError as exc:
            raise SourceGraphError(
                f"Unable to read reachable ASM source {asm_path}: {exc}"
            ) from exc

        for line_number, include_text in _iter_active_incsrcs(
            lines, active_defines
        ):
            include_path = Path(include_text)
            candidates = (
                asm_path.parent / include_path,
                resolved_root / include_path,
            )
            included = next(
                (candidate.resolve() for candidate in candidates
                 if _is_case_exact_file(candidate, resolved_root)),
                None,
            )
            if included is None:
                rel = asm_path.relative_to(resolved_root)
                raise SourceGraphError(
                    f"{rel}:{line_number}: unresolved incsrc "
                    f"{include_text!r}"
                )
            if not included.is_relative_to(resolved_root):
                rel = asm_path.relative_to(resolved_root)
                raise SourceGraphError(
                    f"{rel}:{line_number}: incsrc escapes repo root: "
                    f"{include_text!r}"
                )
            pending.append(included)

    canonical_define_sources = {
        "Util/macros.asm",
        "Config/module_flags.asm",
        "Config/feature_flags.asm",
    }
    for asm_path in sorted(reachable):
        rel = asm_path.relative_to(resolved_root).as_posix()
        if rel in canonical_define_sources:
            continue
        try:
            lines = asm_path.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines()
        except OSError as exc:
            raise SourceGraphError(
                f"Unable to validate reachable ASM source {asm_path}: {exc}"
            ) from exc
        for line_index, line, _ in _iter_active_lines(lines, active_defines):
            assignment = DEFINE_ANY_ASSIGN_RE.match(line.split(";", 1)[0])
            if assignment and assignment.group(1) in active_defines:
                raise SourceGraphError(
                    f"{rel}:{line_index + 1}: reachable source reassigns "
                    f"preloaded global define !{assignment.group(1)} outside "
                    "the canonical define files; include-order state cannot "
                    "be resolved safely"
                )

    return sorted(reachable)
