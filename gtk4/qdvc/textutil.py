"""Small text helpers: a port of Text/TextUtilities.swift (CaseStyle and the
character classes) plus `excerpt` from the macOS edition's IssueStyle.swift."""

from __future__ import annotations

_WHITESPACE = {" ", "\t", "\n", "\r", "\u00a0", "\u2028", "\u2029"}


def is_whitespace(ch: str) -> bool:
    """As UnitClass.isWhitespace: space, tab, line breaks, no-break space, line/paragraph separators."""
    return ch in _WHITESPACE


def is_letter(ch: str) -> bool:
    return ch.isalpha()


def capitalize_first(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def match_case(replacement: str, original: str) -> str:
    """Makes `replacement` follow the capitalisation of `original` (UPPER, Title or as-is)."""
    if not replacement:
        return replacement
    letters = [c for c in original if c.isalpha()]
    if len(letters) >= 2 and all(c.isupper() for c in letters):
        return replacement.upper()
    first = next((c for c in original if c.isalpha()), None)
    if first is not None and first.isupper() and replacement[0].islower():
        return capitalize_first(replacement)
    return replacement


def excerpt(s: str, max_length: int = 90) -> str:
    """Single-line, length-limited version for display in lists."""
    flat = s.replace("\n", " ")
    if len(flat) <= max_length:
        return flat
    return flat[:max_length - 1] + "…"
