#!/usr/bin/env python3
"""Tag org blocks with @hook when the first instruction is a jump/call.

This targets org blocks that are not inlined (no ':' on the org line).
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ORG_RE = re.compile(r'^(\s*org\s+\$[0-9A-Fa-f]{6})(\s*(?:;.*)?)$')
INSTR_RE = re.compile(r'^\s*([A-Za-z]{2,5}(?:\.[A-Za-z]+)?)\b\s*(.*)$')
LABEL_RE = re.compile(r'^\s*[A-Za-z0-9_\.\+\-]+:\s*$')
COMMENT_RE = re.compile(r'^\s*;')
HOOK_DIRECTIVE_RE = re.compile(r'@hook\b', re.IGNORECASE)
HOOK_KV_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(\"[^\"]*\"|'[^']*'|\S+)")
DIRECTIVE_PREFIXES = (
    'pushpc', 'pullpc', 'org', 'if', 'endif', 'else', 'macro',
    'db', 'dw', 'dl', 'dd', 'incbin', 'incsrc', 'fill', 'pad', 'assert',
)
SKIP_DIRS = {'.git', '.context', 'Roms', 'build', 'bin', 'obj', 'tools', 'tests', 'node_modules'}


def _should_skip(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def _normalize_op(op: str) -> str:
    op = op.strip()
    if '.' in op:
        op = op.split('.', 1)[0]
    return op.upper()


def _find_first_instruction(lines: list[str], start_idx: int) -> tuple[str | None, str | None]:
    for j in range(start_idx + 1, min(start_idx + 20, len(lines))):
        line = lines[j].strip()
        if not line or COMMENT_RE.match(line):
            continue
        if LABEL_RE.match(line):
            continue
        lower = line.lower()
        if lower.startswith(DIRECTIVE_PREFIXES):
            continue
        m = INSTR_RE.match(line)
        if not m:
            continue
        op = _normalize_op(m.group(1))
        operand = m.group(2).strip() if m.group(2) else ''
        return op, operand.split()[0] if operand else None
    return None, None


def _module_from_path(path: Path, root: Path) -> str:
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    if not rel.parts:
        return "root"
    return rel.parts[0]


def _format_hook_comment(kv: dict[str, str]) -> str:
    if not kv:
        return "@hook"
    order = [
        "module", "name", "kind", "target", "note",
        "expected_m", "expected_x", "skip_abi", "abi", "abi_class",
    ]
    parts = []
    for key in order:
        if key in kv:
            parts.append(f"{key}={_format_value(kv[key])}")
    for key in sorted(kv.keys()):
        if key not in order:
            parts.append(f"{key}={_format_value(kv[key])}")
    return "@hook " + " ".join(parts)


def _format_value(value: str) -> str:
    value = str(value)
    if not value:
        return "\"\""
    if any(ch.isspace() for ch in value):
        escaped = value.replace('"', '\\"')
        return f"\"{escaped}\""
    return value


def _parse_hook_kv(tail: str) -> tuple[dict[str, str], bool]:
    matches = list(HOOK_KV_RE.finditer(tail))
    kv: dict[str, str] = {}
    covered = [False] * len(tail)
    for m in matches:
        for i in range(m.start(), m.end()):
            if 0 <= i < len(covered):
                covered[i] = True
        key = m.group(1).lower()
        val = m.group(2)
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        kv[key] = val
    for i, ch in enumerate(tail):
        if ch.isspace():
            continue
        if not covered[i]:
            return kv, False
    return kv, True


def _build_hook_comment(op: str, target: str, module: str | None, normalize: bool, module_from_path: bool) -> str:
    if normalize:
        kv: dict[str, str] = {}
        if module_from_path and module:
            kv["module"] = module
        return _format_hook_comment(kv)
    kv = {"name": target, "kind": op.lower(), "target": target}
    if module_from_path and module:
        kv["module"] = module
    return _format_hook_comment(kv)


def _normalize_hook_line(
    line: str,
    op: str | None,
    target: str | None,
    module: str | None,
    normalize: bool,
    module_from_path: bool,
) -> str:
    hook_match = HOOK_DIRECTIVE_RE.search(line)
    if not hook_match:
        return line
    tail = line[hook_match.end():]
    kv, clean = _parse_hook_kv(tail)
    if not clean:
        return line
    if module_from_path and module and "module" not in kv:
        kv["module"] = module
    if normalize:
        default_kind = op.lower() if op else None
        default_target = target
        default_name = target
        if default_kind and kv.get("kind") == default_kind:
            kv.pop("kind", None)
        if default_target and kv.get("target") == default_target:
            kv.pop("target", None)
        if default_name and kv.get("name") == default_name:
            kv.pop("name", None)
    new_directive = _format_hook_comment(kv)
    return f"{line[:hook_match.start()]}{new_directive}"


def tag_file(
    path: Path,
    root: Path,
    apply: bool,
    report: bool,
    normalize: bool,
    module_from_path: bool,
    changes: list[dict],
) -> int:
    lines = path.read_text(errors='ignore').splitlines()
    changed = False
    tags_added = 0
    out = []
    module = _module_from_path(path, root)

    for idx, line in enumerate(lines):
        m = ORG_RE.match(line)
        if not m:
            if normalize and '@hook' in line:
                new_line = _normalize_hook_line(line, None, None, module, normalize, module_from_path)
                if new_line != line:
                    changed = True
                    if report:
                        changes.append({
                            "file": str(path),
                            "line": idx + 1,
                            "old": line.strip(),
                            "new": new_line.strip(),
                        })
                out.append(new_line)
            else:
                out.append(line)
            continue
        if ':' in line:
            out.append(line)
            continue
        if '@hook' in line:
            op, target = _find_first_instruction(lines, idx)
            new_line = _normalize_hook_line(line, op, target, module, normalize, module_from_path)
            if new_line != line:
                changed = True
                if report:
                    changes.append({
                        "file": str(path),
                        "line": idx + 1,
                        "old": line.strip(),
                        "new": new_line.strip(),
                    })
            out.append(new_line)
            continue
        op, target = _find_first_instruction(lines, idx)
        if op in {'JSL', 'JSR', 'JML', 'JMP'} and target:
            hook_comment = _build_hook_comment(op, target, module, normalize, module_from_path)
            if ';' in line:
                new_line = f"{line} ; {hook_comment}"
            else:
                new_line = f"{line} ; {hook_comment}"
            out.append(new_line)
            changed = True
            tags_added += 1
            if report:
                changes.append({
                    "file": str(path),
                    "line": idx + 1,
                    "old": line.strip(),
                    "new": new_line.strip(),
                })
        else:
            out.append(line)

    if apply and changed:
        path.write_text('\n'.join(out) + '\n')
    return tags_added


def main() -> int:
    parser = argparse.ArgumentParser(description='Tag org blocks with @hook comments')
    parser.add_argument('--root', type=Path, default=Path('.'), help='Root directory')
    parser.add_argument('--apply', action='store_true', help='Apply changes to files')
    parser.add_argument('--dry-run', action='store_true', help='Report changes without writing')
    parser.add_argument('--normalize', action='store_true', help='Normalize @hook tags (drop redundant fields)')
    parser.add_argument('--module-from-path', action='store_true', help='Add module=<top-level dir> if missing')
    parser.add_argument('--json', action='store_true', help='Emit JSON change report to stdout')
    parser.add_argument('--json-out', type=Path, help='Write JSON change report to file')
    args = parser.parse_args()

    total_tags = 0
    changes: list[dict] = []
    root = args.root.resolve()
    for path in root.rglob('*.asm'):
        if _should_skip(path):
            continue
        total_tags += tag_file(
            path,
            root,
            args.apply,
            args.dry_run or args.json or args.json_out,
            args.normalize,
            args.module_from_path,
            changes,
        )

    if args.json or args.json_out:
        import json
        payload = {
            "tagged": total_tags,
            "changes": changes,
        }
        data = json.dumps(payload, indent=2)
        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(data + "\n")
        if args.json:
            print(data)
    elif args.dry_run:
        for change in changes:
            print(f"{change['file']}:{change['line']} -> {change['new']}")
        print(f"Tagged org blocks: {total_tags}")
    else:
        print(f"Tagged org blocks: {total_tags}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
