"""Regular expressions with the Unicode property classes the macOS edition's
ICU patterns use (\\p{L}, \\p{Lu}, \\p{Ll}, \\p{N}).

Python's `re` has no \\p{...}, and the third-party `regex` module is not in
the GNOME runtime, so `compile()` rewrites each property into an explicit
character class built from `unicodedata` at import (the Basic Multilingual
Plane: about ten milliseconds). Inside a bracket expression the ranges are
inserted bare; outside, wrapped in brackets. Everything else in a pattern is
passed through, so the patterns stay word for word those of the Swift
sources.
"""

from __future__ import annotations

import re
import unicodedata

_CATEGORIES = {
    "L": ("Lu", "Ll", "Lt", "Lm", "Lo"),
    "Lu": ("Lu",),
    "Ll": ("Ll",),
    "N": ("Nd", "Nl", "No"),
}


def _ranges(categories: tuple[str, ...]) -> str:
    out: list[str] = []
    start = prev = None
    for cp in range(0x10000):
        if 0xD800 <= cp <= 0xDFFF:
            continue
        if unicodedata.category(chr(cp)) in categories:
            if start is None:
                start = prev = cp
            elif cp == prev + 1:
                prev = cp
            else:
                out.append(_range(start, prev))
                start = prev = cp
    if start is not None:
        out.append(_range(start, prev))
    return "".join(out)


def _range(a: int, b: int) -> str:
    def esc(cp: int) -> str:
        return f"\\u{cp:04x}"
    if a == b:
        return esc(a)
    if b == a + 1:
        return esc(a) + esc(b)
    return f"{esc(a)}-{esc(b)}"


CLASSES = {name: _ranges(cats) for name, cats in _CATEGORIES.items()}

_PROP = re.compile(r"\\p\{(L|Lu|Ll|N)\}")


def translate(pattern: str) -> str:
    """Rewrites \\p{…} into explicit classes, minding bracket expressions."""
    out: list[str] = []
    i, n, in_class = 0, len(pattern), False
    while i < n:
        c = pattern[i]
        if c == "\\" and i + 1 < n:
            m = _PROP.match(pattern, i)
            if m:
                body = CLASSES[m.group(1)]
                out.append(body if in_class else f"[{body}]")
                i = m.end()
                continue
            out.append(pattern[i:i + 2])
            i += 2
            continue
        if c == "[" and not in_class:
            in_class = True
            out.append(c)
            # A ']' or '^]' straight after '[' is literal.
            if i + 1 < n and pattern[i + 1] == "^":
                out.append("^")
                i += 1
            if i + 1 < n and pattern[i + 1] == "]":
                out.append("\\]")
                i += 1
        elif c == "]" and in_class:
            in_class = False
            out.append(c)
        else:
            out.append(c)
        i += 1
    return "".join(out)


def compile(pattern: str, case_insensitive: bool = False) -> re.Pattern:  # noqa: A001 - mirrors re.compile
    flags = re.IGNORECASE if case_insensitive else 0
    return re.compile(translate(pattern), flags)


def escape(text: str) -> str:
    """As NSRegularExpression.escapedPattern(for:): escapes metacharacters."""
    return re.escape(text)
