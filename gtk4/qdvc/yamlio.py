"""The suite's own YAML subset: a port of the macOS edition's YAML.swift.

It reads the block style the apps write, plus what people type by hand:
mappings and sequences nested by indentation (spaces, not tabs); plain,
'single-quoted' and "double-quoted" scalars (\\n, \\t, \\", \\\\, \\uXXXX
escapes) and # comments; literal (|) and folded (>) block scalars with the
-, + chomping indicators and an optional indentation indicator; one-line
flow sequences of scalars ([a, b, "c, d"]) and the empty flow collections
[] and {}.

Not supported (an error, never a silent misreading): anchors and aliases,
tags, multiple documents, flow mappings with content, nested flow
collections and complex keys. Scalars are not typed: everything is a string
until a caller asks for an int or a bool.

The emitter decides plain, quoted, flow and block styles exactly as the
Swift `YAMLEmitter` does, so both editions write the same bytes
(tests/test_core.py, ParityTests). PyYAML is deliberately not used: its
emitter makes different choices, and the Flatpak needs nothing beyond the
GNOME runtime.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_WS = " \t"
_INT = re.compile(r"[+-]?[0-9]+\Z")


# ---------------------------------------------------------------------------
# Nodes

class Node:
    """A parsed YAML value: Null, Scalar, Sequence or Mapping."""

    def get(self, key: str) -> "Node | None":
        return None

    def __getitem__(self, key: str) -> "Node | None":
        return self.get(key)

    @property
    def string(self) -> str | None:
        return None

    @property
    def int(self) -> int | None:
        """As Swift's Int(): an optional sign and ASCII digits."""
        s = self.string
        if s is None or not _INT.match(s.strip(_WS)):
            return None
        return int(s.strip(_WS))

    @property
    def bool(self) -> bool | None:
        s = self.string
        if s is None:
            return None
        s = s.lower()
        if s in ("true", "yes", "on"):
            return True
        if s in ("false", "no", "off"):
            return False
        return None

    @property
    def items(self) -> list["Node"]:
        return []

    @property
    def strings(self) -> list[str]:
        return [i.string for i in self.items if i.string is not None]

    @property
    def pairs(self) -> list["Pair"]:
        return []

    @property
    def is_null(self) -> bool:
        return False


class Null(Node):
    @property
    def items(self) -> list[Node]:
        return []

    @property
    def is_null(self) -> bool:
        return True

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Null)

    def __hash__(self) -> int:
        return 0

    def __repr__(self) -> str:
        return "Null()"


NULL = Null()


@dataclass(eq=True)
class Scalar(Node):
    value: str

    @property
    def string(self) -> str | None:
        return self.value

    @property
    def items(self) -> list[Node]:
        return [self]


@dataclass(eq=True)
class Sequence(Node):
    values: list[Node] = field(default_factory=list)

    @property
    def items(self) -> list[Node]:
        return self.values


@dataclass(eq=True)
class Pair:
    key: str
    value: Node


@dataclass(eq=True)
class Mapping(Node):
    entries: list[Pair] = field(default_factory=list)

    def get(self, key: str) -> Node | None:
        for p in self.entries:
            if p.key == key:
                return p.value
        return None

    @property
    def pairs(self) -> list[Pair]:
        return self.entries


# Convenience builders, as in Swift.
def s(text: str) -> Scalar:
    return Scalar(text)


def num(n: int) -> Scalar:
    return Scalar(str(n))


def flag(b: bool) -> Scalar:
    return Scalar("true" if b else "false")


def str_list(strings: list[str]) -> Sequence:
    return Sequence([Scalar(x) for x in strings])


def mapping(pairs: list[tuple[str, Node]]) -> Mapping:
    return Mapping([Pair(k, v) for k, v in pairs])


class YAMLError(Exception):
    def __init__(self, line: int, message: str):
        super().__init__(f"line {line}: {message}")
        self.line = line
        self.message = message


def parse(text: str) -> Node:
    """Parses a document. An empty document is NULL."""
    return _Parser(text).parse_document()


def emit(node: Node, block_keys: frozenset[str] | set[str] = frozenset()) -> str:
    """Writes a node as a block-style document ending in a newline."""
    lines: list[str] = []
    e = _Emitter(set(block_keys))
    if isinstance(node, Mapping):
        e.emit_mapping(node.entries, 0, lines)
    elif isinstance(node, Sequence):
        e.emit_sequence(node.values, 0, lines)
    elif isinstance(node, Scalar):
        lines.append(_Emitter.scalar(node.value))
    return "" if not lines else "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Parser

def _indent(line: str) -> int:
    n = 0
    for ch in line:
        if ch == " ":
            n += 1
        else:
            break
    return n


def _is_blank(line: str) -> bool:
    return all(c in _WS for c in line)


def _is_ignorable(line: str) -> bool:
    t = line.strip(_WS)
    return t == "" or t.startswith("#") or t == "---" or t == "..."


def _is_sequence_entry(c: str) -> bool:
    return c == "-" or c.startswith("- ")


class _Parser:
    def __init__(self, text: str):
        if text.startswith("\ufeff"):
            text = text[1:]
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        self.lines = text.split("\n")
        self.i = 0

    def error(self, message: str, line: int | None = None) -> YAMLError:
        return YAMLError((self.i if line is None else line) + 1, message)

    def skip_ignorable(self) -> bool:
        while self.i < len(self.lines) and _is_ignorable(self.lines[self.i]):
            self.i += 1
        return self.i < len(self.lines)

    @staticmethod
    def content(line: str) -> str:
        return line[_indent(line):]

    def check_tabs(self, line: str) -> None:
        lead = ""
        for ch in line:
            if ch in _WS:
                lead += ch
            else:
                break
        if "\t" in lead:
            raise self.error("tabs cannot be used for indentation")

    def parse_document(self) -> Node:
        if not self.skip_ignorable():
            return NULL
        node = self.parse_node(0)
        if self.skip_ignorable():
            raise self.error("unexpected content (check the indentation)")
        return node

    def parse_node(self, min_indent: int) -> Node:
        if not self.skip_ignorable():
            return NULL
        line = self.lines[self.i]
        self.check_tabs(line)
        n = _indent(line)
        if n < min_indent:
            return NULL
        c = self.content(line)
        if _is_sequence_entry(c):
            return self.parse_sequence(n)
        if _split_key(c) is not None:
            return self.parse_mapping(n)
        self.i += 1
        return self.parse_value_text(c, max(min_indent - 1, 0), self.i - 1)

    def parse_mapping(self, n: int) -> Node:
        pairs: list[Pair] = []
        while self.skip_ignorable():
            line = self.lines[self.i]
            self.check_tabs(line)
            ind = _indent(line)
            if ind < n:
                break
            if ind > n:
                raise self.error("unexpected indentation")
            c = self.content(line)
            if _is_sequence_entry(c):
                raise self.error('a list item cannot appear here (expected "key: value")')
            kv = _split_key(c)
            if kv is None:
                raise self.error('expected "key: value"')
            key, rest = kv
            line_index = self.i
            self.i += 1
            pairs.append(Pair(key, self.parse_value(rest, n, line_index)))
        return Mapping(pairs)

    def parse_sequence(self, n: int) -> Node:
        items: list[Node] = []
        while self.skip_ignorable():
            line = self.lines[self.i]
            self.check_tabs(line)
            ind = _indent(line)
            if ind < n:
                break
            if ind > n:
                raise self.error("unexpected indentation")
            c = self.content(line)
            if not _is_sequence_entry(c):
                break
            after = c[1:]
            gap = len(after) - len(after.lstrip(" "))
            rest = after[gap:]
            if rest == "" or rest.startswith("#"):
                self.i += 1
                items.append(self.parse_node(n + 1))
            else:
                # Replace "- " with spaces and parse what follows as a node
                # indented at the item's content column.
                self.lines[self.i] = " " * (n + 1 + gap) + rest
                items.append(self.parse_node(n + 1))
        return Sequence(items)

    def parse_value(self, rest: str, n: int, line_index: int) -> Node:
        r = _strip_comment(rest).strip(_WS)
        if r == "":
            if not self.skip_ignorable():
                return NULL
            nxt = self.lines[self.i]
            ind = _indent(nxt)
            if ind > n:
                return self.parse_node(n + 1)
            if ind == n and _is_sequence_entry(self.content(nxt)):
                return self.parse_sequence(n)
            return NULL
        return self.parse_value_text(r, n, line_index)

    def parse_value_text(self, raw: str, n: int, line_index: int) -> Node:
        r = _strip_comment(raw).strip(_WS)
        if r[:1] in ("|", ">"):
            return Scalar(self.parse_block_scalar(r, n, line_index))
        if r.startswith("["):
            return self.parse_flow_sequence(r, line_index)
        if r.startswith("{"):
            if r.replace(" ", "") == "{}":
                return Mapping([])
            raise self.error("flow mappings ({…}) are not supported", line_index)
        if r[:1] in ("&", "*", "!"):
            raise self.error("anchors, aliases and tags are not supported", line_index)
        if r[:1] in ('"', "'"):
            text = r
            while _quoted_end(text) is None and self.i < len(self.lines):
                nxt = self.lines[self.i].strip(_WS)
                self.i += 1
                text += "\\n" if nxt == "" else " " + nxt
            end = _quoted_end(text)
            if end is None:
                raise self.error("unterminated quoted string", line_index)
            after = _strip_comment(text[end:]).strip(_WS)
            if after:
                raise self.error("unexpected text after a quoted string", line_index)
            return Scalar(_unquote(text[:end], line_index + 1))
        if r in ("~", "null", "Null", "NULL"):
            return NULL
        return Scalar(r)

    def parse_block_scalar(self, header: str, n: int, line_index: int) -> str:
        folded = header[0] == ">"
        chomp = " "
        indicator: int | None = None
        for ch in header[1:]:
            if ch in "-+":
                chomp = ch
            elif ch.isdigit() and ch.isascii() and int(ch) > 0:
                indicator = int(ch)
            elif ch == " ":
                break
            else:
                raise self.error(f'bad block scalar header "{header}"', line_index)
        if indicator is not None:
            content_indent = n + indicator
        else:
            j = self.i
            while j < len(self.lines) and _is_blank(self.lines[j]):
                j += 1
            if j >= len(self.lines):
                return ""
            content_indent = _indent(self.lines[j])
            if content_indent <= n:
                content_indent = n + 1
        body: list[str] = []
        while self.i < len(self.lines):
            line = self.lines[self.i]
            if _is_blank(line):
                body.append(line[content_indent:] if len(line) > content_indent else "")
                self.i += 1
                continue
            if _indent(line) < content_indent:
                break
            body.append(line[content_indent:])
            self.i += 1
        trailing = 0
        while body and body[-1] == "":
            body.pop()
            trailing += 1
        if folded:
            text = ""
            previous = "start"
            for line in body:
                if line == "":
                    text += "\n"
                    previous = "blank"
                elif line.startswith(" "):
                    if previous in ("text", "more"):
                        text += "\n"
                    text += line
                    previous = "more"
                else:
                    if previous == "text":
                        text += " "
                    elif previous == "more":
                        text += "\n"
                    text += line
                    previous = "text"
        else:
            text = "\n".join(body)
        if not body:
            return "\n" * trailing if chomp == "+" else ""
        if chomp == "-":
            return text
        if chomp == "+":
            return text + "\n" + "\n" * trailing
        return text + "\n"

    def parse_flow_sequence(self, start: str, line_index: int) -> Node:
        text = start
        while _flow_end(text) is None and self.i < len(self.lines):
            text += " " + self.lines[self.i].strip(_WS)
            self.i += 1
        end = _flow_end(text)
        if end is None:
            raise self.error("unterminated [ … ] list", line_index)
        after = _strip_comment(text[end + 1:]).strip(_WS)
        if after:
            raise self.error("unexpected text after a [ … ] list", line_index)
        inner = text[1:end]
        items: list[Node] = []
        current = ""
        quote: str | None = None
        escaped = False

        def flush() -> None:
            nonlocal current
            t = current.strip(_WS)
            current = ""
            if t == "":
                return
            if t[:1] in ("[", "{"):
                raise self.error("nested [ … ] lists are not supported", line_index)
            if t[:1] in ('"', "'"):
                items.append(Scalar(_unquote(t, line_index + 1)))
            elif t in ("~", "null"):
                items.append(NULL)
            else:
                items.append(Scalar(t))

        pending_single = False
        for ch in inner:
            if pending_single:
                pending_single = False
                if ch == "'":
                    current += ch
                    quote = "'"
                    continue
            if quote is not None:
                current += ch
                if quote == '"' and ch == "\\" and not escaped:
                    escaped = True
                    continue
                if ch == quote and not escaped:
                    if quote == "'":
                        pending_single = True
                    quote = None
                escaped = False
            elif ch in ('"', "'") and current.strip(_WS) == "":
                quote = ch
                current += ch
            elif ch == ",":
                flush()
            else:
                current += ch
        flush()
        return Sequence(items)


def _split_key(c: str) -> tuple[str, str] | None:
    """Splits "key: rest" (or "key:"), with a plain or quoted key."""
    if c[:1] in ('"', "'"):
        end = _quoted_end(c)
        if end is None:
            return None
        try:
            key = _unquote(c[:end], 0)
        except YAMLError:
            return None
        after = c[end:]
        if not after.startswith(":"):
            return None
        rest = after[1:]
        if not (rest == "" or rest.startswith(" ")):
            return None
        return key, rest
    if c and c[0] in "[{|>#&*!%@`\"'":
        return None
    if _is_sequence_entry(c):
        return None
    for idx, ch in enumerate(c):
        if ch == ":":
            if idx + 1 == len(c) or c[idx + 1] == " ":
                key = c[:idx].strip(_WS)
                if not key:
                    return None
                return key, c[idx + 1:]
        if ch == "#" and idx > 0 and c[idx - 1] == " ":
            return None
    return None


def _strip_comment(s: str) -> str:
    """Removes a trailing "# comment" outside quotes."""
    quote: str | None = None
    escaped = False
    previous = " "
    idx = 0
    while idx < len(s):
        ch = s[idx]
        if quote is not None:
            if quote == '"' and ch == "\\" and not escaped:
                escaped = True
                previous = ch
                idx += 1
                continue
            if ch == quote and not escaped:
                quote = None
            escaped = False
        elif ch in ('"', "'") and previous in (" ", "[", ","):
            quote = ch
        elif ch == "#" and previous in (" ", "\t"):
            return s[:idx]
        previous = ch
        idx += 1
    return s


def _quoted_end(s: str) -> int | None:
    """The index just past the closing quote of a quoted scalar at the start."""
    if not s or s[0] not in ('"', "'"):
        return None
    q = s[0]
    idx = 1
    while idx < len(s):
        ch = s[idx]
        if q == '"' and ch == "\\":
            idx += 2
            continue
        if ch == q:
            nxt = idx + 1
            if q == "'" and nxt < len(s) and s[nxt] == "'":
                idx = nxt + 1
                continue
            return nxt
        idx += 1
    return None


def _flow_end(s: str) -> int | None:
    """The index of the "]" that closes a flow sequence at the start of s."""
    quote: str | None = None
    escaped = False
    at_item_start = True
    idx = 1
    while idx < len(s):
        ch = s[idx]
        if quote is not None:
            if quote == '"' and ch == "\\" and not escaped:
                escaped = True
                idx += 1
                continue
            if ch == quote and not escaped:
                nxt = idx + 1
                if quote == "'" and nxt < len(s) and s[nxt] == "'":
                    idx = nxt + 1
                    continue
                quote = None
            escaped = False
        elif ch in ('"', "'") and at_item_start:
            quote = ch
        elif ch == "]":
            return idx
        if quote is None:
            if ch == ",":
                at_item_start = True
            elif ch != " ":
                at_item_start = False
        else:
            at_item_start = False
        idx += 1
    return None


_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", '"': '"', "\\": "\\", "/": "/", " ": " "}


def _unquote(s: str, line: int) -> str:
    if len(s) < 2 or s[0] not in ('"', "'") or s[-1] != s[0]:
        raise YAMLError(line, "bad quoted string")
    q = s[0]
    inner = s[1:-1]
    if q == "'":
        return inner.replace("''", "'")
    out = []
    it = iter(inner)
    for ch in it:
        if ch != "\\":
            out.append(ch)
            continue
        e = next(it, None)
        if e is None:
            raise YAMLError(line, "bad escape at end of string")
        if e in _ESCAPES:
            out.append(_ESCAPES[e])
        elif e in ("u", "U", "x"):
            count = 2 if e == "x" else (4 if e == "u" else 8)
            hexs = "".join(h for h in (next(it, "") for _ in range(count)))
            try:
                out.append(chr(int(hexs, 16)))
            except (ValueError, OverflowError):
                raise YAMLError(line, f"bad \\{e} escape") from None
        else:
            raise YAMLError(line, f"unknown escape \\{e}")
    return "".join(out)


# ---------------------------------------------------------------------------
# Emitter

def _is_control(ch: str) -> bool:
    o = ord(ch)
    return o < 0x20 or o == 0x7F or ch == "\ufeff"


class _Emitter:
    def __init__(self, block_keys: set[str]):
        self.block_keys = block_keys

    def emit_mapping(self, pairs: list[Pair], indent: int, lines: list[str]) -> None:
        pad = " " * indent
        for pair in pairs:
            key = self.key_text(pair.key)
            block = pair.key in self.block_keys
            v = pair.value
            if isinstance(v, Null):
                lines.append(f"{pad}{key}:")
            elif isinstance(v, Scalar):
                t = v.value
                if "\n" in t or "\r" in t or (block and t):
                    lines.append(f"{pad}{key}: {self.block_header(t)}")
                    lines.extend(self.block_lines(t, indent + 2))
                else:
                    lines.append(f"{pad}{key}: {self.scalar(t)}")
            elif isinstance(v, Sequence):
                flow = None if block else self.flow_text(v.values)
                if not v.values:
                    lines.append(f"{pad}{key}: []")
                elif flow is not None:
                    lines.append(f"{pad}{key}: {flow}")
                else:
                    lines.append(f"{pad}{key}:")
                    self.emit_sequence(v.values, indent + 2, lines)
            elif isinstance(v, Mapping):
                if not v.entries:
                    lines.append(f"{pad}{key}: {{}}")
                else:
                    lines.append(f"{pad}{key}:")
                    self.emit_mapping(v.entries, indent + 2, lines)

    def emit_sequence(self, items: list[Node], indent: int, lines: list[str]) -> None:
        pad = " " * indent
        for item in items:
            if isinstance(item, Null):
                lines.append(f"{pad}- ~")
            elif isinstance(item, Scalar):
                lines.append(f"{pad}- {self.scalar(item.value, force_single_line=True)}")
            elif isinstance(item, Sequence):
                if not item.values:
                    lines.append(f"{pad}- []")
                else:
                    sub: list[str] = []
                    self.emit_sequence(item.values, indent + 2, sub)
                    sub[0] = pad + "- " + sub[0][indent + 2:]
                    lines.extend(sub)
            elif isinstance(item, Mapping):
                if not item.entries:
                    lines.append(f"{pad}- {{}}")
                else:
                    sub = []
                    self.emit_mapping(item.entries, indent + 2, sub)
                    sub[0] = pad + "- " + sub[0][indent + 2:]
                    lines.extend(sub)

    @classmethod
    def flow_text(cls, items: list[Node]) -> str | None:
        parts = []
        for item in items:
            if not isinstance(item, Scalar) or "\n" in item.value:
                return None
            parts.append(cls.scalar(item.value, flow=True, force_single_line=True))
        text = "[" + ", ".join(parts) + "]"
        return text if len(text) <= 60 and len(items) <= 6 else None

    @classmethod
    def key_text(cls, key: str) -> str:
        plain = bool(key) and all(c.isalpha() or c.isnumeric() or c in "_-." for c in key) \
            and not key.startswith("-")
        return key if plain else cls.double_quoted(key)

    @staticmethod
    def needs_quotes(t: str, flow: bool) -> bool:
        if t == "":
            return True
        if t[0] == " " or t[-1] == " ":
            return True
        if t[0] in "-?:,[]{}#&*!|>'\"%@`~":
            return True
        if ": " in t or " #" in t or t.endswith(":"):
            return True
        if flow and any(c in t for c in ",[]{}"):
            return True
        if t in ("null", "Null", "NULL", "~"):
            return True
        if any(_is_control(c) for c in t):
            return True
        return False

    @classmethod
    def scalar(cls, t: str, flow: bool = False, force_single_line: bool = False) -> str:
        if cls.needs_quotes(t, flow) or (force_single_line and "\n" in t):
            return cls.double_quoted(t)
        return t

    @staticmethod
    def double_quoted(t: str) -> str:
        out = ['"']
        for ch in t:
            if ch == '"':
                out.append('\\"')
            elif ch == "\\":
                out.append("\\\\")
            elif ch == "\n":
                out.append("\\n")
            elif ch == "\t":
                out.append("\\t")
            elif ch == "\r":
                out.append("\\r")
            elif _is_control(ch):
                out.append("\\u%04X" % ord(ch))
            else:
                out.append(ch)
        out.append('"')
        return "".join(out)

    @staticmethod
    def split(t: str) -> tuple[list[str], int]:
        t = t.replace("\r\n", "\n").replace("\r", "\n")
        trailing = 0
        while t.endswith("\n"):
            t = t[:-1]
            trailing += 1
        return t.split("\n"), trailing

    @classmethod
    def block_header(cls, t: str) -> str:
        body, trailing = cls.split(t)
        header = "|"
        first = body[0] if body else None
        if first is not None and (first.startswith(" ") or all(c in _WS for c in first)):
            header += "2"
        if trailing == 0:
            header += "-"
        elif trailing > 1:
            header += "+"
        return header

    @classmethod
    def block_lines(cls, t: str, indent: int) -> list[str]:
        body, trailing = cls.split(t)
        pad = " " * indent
        lines = ["" if b == "" else pad + b for b in body]
        if trailing > 1:
            lines.extend([""] * (trailing - 1))
        return lines
