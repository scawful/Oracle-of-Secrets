"""Mini expression parser/evaluator for Oracle tooling.

Keep in sync with z3dk/scripts/expr.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable


class ExprError(ValueError):
    """Expression parsing or evaluation error."""


@dataclass(frozen=True)
class Token:
    kind: str
    value: str | int | None = None


_MULTI_OPS = ("==", "!=", "<=", ">=", "&&", "||", "<<", ">>")
_SINGLE_OPS = set("+-*/%&|^!<>")
_PUNCT = {"(": "LPAREN", ")": "RPAREN", ",": "COMMA"}


def _is_ident_start(ch: str) -> bool:
    return ch.isalpha() or ch == "_"


def _is_ident_char(ch: str) -> bool:
    return ch.isalnum() or ch in "_."


def tokenize(expr: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    length = len(expr)
    while i < length:
        ch = expr[i]
        if ch.isspace():
            i += 1
            continue
        if ch in _PUNCT:
            tokens.append(Token(_PUNCT[ch], ch))
            i += 1
            continue
        if ch == "$":
            i += 1
            start = i
            while i < length and expr[i].isalnum():
                i += 1
            if start == i:
                raise ExprError("Invalid hex literal")
            try:
                value = int(expr[start:i], 16)
            except ValueError as exc:
                raise ExprError("Invalid hex literal") from exc
            tokens.append(Token("NUMBER", value))
            continue
        if ch == "0" and i + 1 < length and expr[i + 1] in ("x", "X"):
            i += 2
            start = i
            while i < length and expr[i].isalnum():
                i += 1
            if start == i:
                raise ExprError("Invalid hex literal")
            try:
                value = int(expr[start:i], 16)
            except ValueError as exc:
                raise ExprError("Invalid hex literal") from exc
            tokens.append(Token("NUMBER", value))
            continue
        if ch.isdigit():
            start = i
            while i < length and expr[i].isdigit():
                i += 1
            tokens.append(Token("NUMBER", int(expr[start:i], 10)))
            continue
        if _is_ident_start(ch):
            start = i
            i += 1
            while i < length and _is_ident_char(expr[i]):
                i += 1
            tokens.append(Token("IDENT", expr[start:i]))
            continue

        if i + 1 < length and expr[i:i + 2] in _MULTI_OPS:
            tokens.append(Token("OP", expr[i:i + 2]))
            i += 2
            continue
        if ch in _SINGLE_OPS:
            tokens.append(Token("OP", ch))
            i += 1
            continue

        raise ExprError(f"Unexpected character: {ch}")

    tokens.append(Token("EOF"))
    return tokens


@dataclass
class Node:
    kind: str
    value: str | int | None = None
    left: "Node | None" = None
    right: "Node | None" = None
    args: list["Node"] | None = None


_PRECEDENCE = {
    "||": 1,
    "&&": 2,
    "|": 3,
    "^": 4,
    "&": 5,
    "==": 6,
    "!=": 6,
    "<": 7,
    "<=": 7,
    ">": 7,
    ">=": 7,
    "<<": 8,
    ">>": 8,
    "+": 9,
    "-": 9,
    "*": 10,
    "/": 10,
    "%": 10,
}

_UNARY_OPS = {"+", "-", "!"}
_PREFIX_PRECEDENCE = 11


class Parser:
    def __init__(self, tokens: Iterable[Token]) -> None:
        self._tokens = list(tokens)
        self._pos = 0

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, kind: str, value: str | None = None) -> Token:
        tok = self._advance()
        if tok.kind != kind or (value is not None and tok.value != value):
            raise ExprError(f"Expected {kind} {value or ''}".strip())
        return tok

    def parse(self) -> Node:
        node = self._parse_expr(0)
        if self._peek().kind != "EOF":
            raise ExprError("Unexpected token after expression")
        return node

    def _parse_expr(self, min_prec: int) -> Node:
        left = self._parse_prefix()
        while True:
            tok = self._peek()
            if tok.kind != "OP":
                break
            prec = _PRECEDENCE.get(tok.value)
            if prec is None or prec < min_prec:
                break
            op = tok.value
            self._advance()
            right = self._parse_expr(prec + 1)
            left = Node("bin", op, left=left, right=right)
        return left

    def _parse_prefix(self) -> Node:
        tok = self._advance()
        if tok.kind == "NUMBER":
            return Node("number", tok.value)
        if tok.kind == "IDENT":
            if self._peek().kind == "LPAREN":
                self._advance()
                args: list[Node] = []
                if self._peek().kind != "RPAREN":
                    while True:
                        args.append(self._parse_expr(0))
                        if self._peek().kind == "COMMA":
                            self._advance()
                            continue
                        break
                self._expect("RPAREN")
                return Node("call", tok.value, args=args)
            return Node("ident", tok.value)
        if tok.kind == "OP" and tok.value in _UNARY_OPS:
            operand = self._parse_expr(_PREFIX_PRECEDENCE)
            return Node("unary", tok.value, left=operand)
        if tok.kind == "LPAREN":
            node = self._parse_expr(0)
            self._expect("RPAREN")
            return node
        raise ExprError(f"Unexpected token: {tok.kind} {tok.value}")


@dataclass
class EvalContext:
    resolve_value: Callable[[str], int]
    read_mem8: Callable[[int], int]
    read_mem16: Callable[[int], int]


class ExprEvaluator:
    def __init__(self, context: EvalContext) -> None:
        self._ctx = context

    def evaluate(self, expr: str) -> int:
        parser = Parser(tokenize(expr))
        node = parser.parse()
        return self._eval(node)

    def _eval(self, node: Node) -> int:
        kind = node.kind
        if kind == "number":
            return int(node.value or 0)
        if kind == "ident":
            name = str(node.value or "")
            lowered = name.lower()
            if lowered == "true":
                return 1
            if lowered == "false":
                return 0
            return int(self._ctx.resolve_value(name))
        if kind == "unary":
            operand = self._eval(node.left) if node.left else 0
            if node.value == "!":
                return 0 if operand else 1
            if node.value == "-":
                return -operand
            if node.value == "+":
                return operand
        if kind == "bin":
            left = self._eval(node.left)
            right = self._eval(node.right)
            op = node.value
            if op == "+":
                return left + right
            if op == "-":
                return left - right
            if op == "*":
                return left * right
            if op == "/":
                if right == 0:
                    raise ExprError("Division by zero")
                return left // right
            if op == "%":
                if right == 0:
                    raise ExprError("Modulo by zero")
                return left % right
            if op == "<<":
                return left << right
            if op == ">>":
                return left >> right
            if op == "&":
                return left & right
            if op == "^":
                return left ^ right
            if op == "|":
                return left | right
            if op == "==":
                return 1 if left == right else 0
            if op == "!=":
                return 1 if left != right else 0
            if op == "<":
                return 1 if left < right else 0
            if op == "<=":
                return 1 if left <= right else 0
            if op == ">":
                return 1 if left > right else 0
            if op == ">=":
                return 1 if left >= right else 0
            if op == "&&":
                return 1 if (left and right) else 0
            if op == "||":
                return 1 if (left or right) else 0
        if kind == "call":
            fname = str(node.value or "")
            args = [self._eval(arg) for arg in (node.args or [])]
            return self._call(fname, args)
        raise ExprError(f"Unhandled node: {node}")

    def _call(self, name: str, args: list[int]) -> int:
        lname = name.lower()
        if lname == "bit":
            if len(args) != 2:
                raise ExprError("bit(x, n) expects 2 args")
            return 1 if (args[0] >> args[1]) & 1 else 0
        if lname == "mask":
            if len(args) != 2:
                raise ExprError("mask(x, m) expects 2 args")
            return args[0] & args[1]
        if lname == "between":
            if len(args) != 3:
                raise ExprError("between(x, lo, hi) expects 3 args")
            return 1 if args[1] <= args[0] <= args[2] else 0
        if lname == "bank":
            if len(args) != 1:
                raise ExprError("bank(x) expects 1 arg")
            return (args[0] >> 16) & 0xFF
        if lname == "byte":
            if len(args) != 1:
                raise ExprError("byte(x) expects 1 arg")
            return args[0] & 0xFF
        if lname == "word":
            if len(args) != 1:
                raise ExprError("word(x) expects 1 arg")
            return args[0] & 0xFFFF
        if lname == "mem":
            if len(args) != 1:
                raise ExprError("mem(addr) expects 1 arg")
            return int(self._ctx.read_mem8(args[0]))
        if lname == "memw":
            if len(args) != 1:
                raise ExprError("memw(addr) expects 1 arg")
            return int(self._ctx.read_mem16(args[0]))
        raise ExprError(f"Unknown function: {name}")
