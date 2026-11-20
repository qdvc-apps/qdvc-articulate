"""Spelling from Enchant (libenchant-2, with Hunspell dictionaries): the
counterpart of the macOS edition's SystemSpellChecker (AppleSpell).

Enchant is part of the GNOME runtime and its dictionaries come with the
runtime's locale extension, so nothing is bundled. Unlike AppleSpell it runs
inside the app's own process: no text leaves the app at all. Enchant has no
GObject bindings, so it is reached through ctypes. There is no grammar
checker to go with it on Linux; the rules and the AI review cover grammar.

Words are found here rather than by Enchant: words with digits or
underscores, single letters, words in capitals (acronyms) and words with
inner capitals (iPhone, macOS) are not checked, nor is anything in an
exclusion zone (code, URLs, e-mail addresses).
"""

from __future__ import annotations

import ctypes
import ctypes.util
import threading

from . import uregex
from .model import Dialect, Issue, IssueCategory, IssueSeverity, IssueSource, TextSpan
from .text import ExclusionZones

WORD = uregex.compile(r"[\p{L}\p{N}_]+(?:['’][\p{L}]+)*")
_DESCRIBE = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
                             ctypes.c_void_p)


def _load():
    for name in ("libenchant-2.so.2", ctypes.util.find_library("enchant-2")):
        if not name:
            continue
        try:
            lib = ctypes.CDLL(name)
        except OSError:
            continue
        c = ctypes
        lib.enchant_broker_init.restype = c.c_void_p
        lib.enchant_broker_free.argtypes = [c.c_void_p]
        lib.enchant_broker_request_dict.restype = c.c_void_p
        lib.enchant_broker_request_dict.argtypes = [c.c_void_p, c.c_char_p]
        lib.enchant_broker_dict_exists.restype = c.c_int
        lib.enchant_broker_dict_exists.argtypes = [c.c_void_p, c.c_char_p]
        lib.enchant_broker_free_dict.argtypes = [c.c_void_p, c.c_void_p]
        lib.enchant_broker_list_dicts.argtypes = [c.c_void_p, _DESCRIBE, c.c_void_p]
        lib.enchant_dict_check.restype = c.c_int
        lib.enchant_dict_check.argtypes = [c.c_void_p, c.c_char_p, c.c_ssize_t]
        lib.enchant_dict_suggest.restype = c.POINTER(c.c_char_p)
        lib.enchant_dict_suggest.argtypes = [c.c_void_p, c.c_char_p, c.c_ssize_t, c.POINTER(c.c_size_t)]
        lib.enchant_dict_free_string_list.argtypes = [c.c_void_p, c.POINTER(c.c_char_p)]
        return lib
    return None


class SpellChecker:
    """One Enchant broker, with a dictionary per variety of English, and a cache of verdicts."""

    MAX_SUGGESTIONS = 5

    def __init__(self):
        self._lib = _load()
        self._broker = self._lib.enchant_broker_init() if self._lib else None
        self._dicts: dict[str, int | None] = {}
        self._tags: dict[Dialect, str | None] = {}
        self._verdicts: dict[tuple[str, str], list[str] | None] = {}
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return bool(self._broker)

    def dictionaries(self) -> list[str]:
        """The language tags Enchant has dictionaries for (for Preferences)."""
        if not self._broker:
            return []
        tags: list[str] = []

        def describe(tag, _provider, _desc, _file, _data):
            tags.append(tag.decode("utf-8", "replace"))
        with self._lock:
            self._lib.enchant_broker_list_dicts(self._broker, _DESCRIBE(describe), None)
        return sorted(set(tags))

    def tag_for(self, dialect: Dialect) -> str | None:
        """The dictionary used for a variety of English, or None when there is none."""
        if dialect not in self._tags:
            with self._lock:
                self._tags[dialect] = next((t for t in dialect.spelling_tags if self._dict_locked(t)), None)
        return self._tags[dialect]

    def _dict_locked(self, tag: str):
        if tag not in self._dicts:
            d = None
            if self._broker and self._lib.enchant_broker_dict_exists(self._broker, tag.encode()):
                d = self._lib.enchant_broker_request_dict(self._broker, tag.encode()) or None
            self._dicts[tag] = d
        return self._dicts[tag]

    def suggestions(self, word: str, tag: str) -> list[str] | None:
        """None when the word is correct, else the suggestions (possibly none)."""
        key = (tag, word)
        if key in self._verdicts:
            return self._verdicts[key]
        with self._lock:
            d = self._dict_locked(tag)
            if not d:
                return None
            data = word.replace("’", "'").encode("utf-8")
            rc = self._lib.enchant_dict_check(d, data, len(data))
            verdict: list[str] | None = None
            if rc > 0:
                n = ctypes.c_size_t(0)
                arr = self._lib.enchant_dict_suggest(d, data, len(data), ctypes.byref(n))
                verdict = []
                if arr:
                    verdict = [arr[i].decode("utf-8", "replace") for i in range(min(n.value, self.MAX_SUGGESTIONS))]
                    self._lib.enchant_dict_free_string_list(d, arr)
            if len(self._verdicts) > 20000:
                self._verdicts.clear()
            self._verdicts[key] = verdict
            return verdict

    def check(self, text: str, dialect: Dialect) -> list[Issue]:
        tag = self.tag_for(dialect) if text else None
        if tag is None:
            return []
        zones = ExclusionZones.compute(text)
        issues: list[Issue] = []
        for m in WORD.finditer(text):
            word = m.group(0)
            if not should_check(word):
                continue
            span = TextSpan(m.start(), len(word))
            if ExclusionZones.is_excluded(span, zones):
                continue
            guesses = self.suggestions(word, tag)
            if guesses is None:
                continue
            if "’" in word:
                guesses = [g.replace("'", "’") for g in guesses]
            message = f"Possible spelling mistake. Did you mean “{guesses[0]}”?" if guesses \
                else "Possible spelling mistake."
            issues.append(Issue(span=span, original=word, suggestions=guesses, category=IssueCategory.SPELLING,
                                severity=IssueSeverity.ERROR, message=message, rule_id="enchant.spelling",
                                source=IssueSource.SPELL_CHECKER))
        return issues

    def close(self) -> None:
        with self._lock:
            if self._broker:
                for d in self._dicts.values():
                    if d:
                        self._lib.enchant_broker_free_dict(self._broker, d)
                self._lib.enchant_broker_free(self._broker)
            self._broker = None
            self._dicts.clear()


def should_check(word: str) -> bool:
    if len(word) < 2 or any(c.isdigit() or c == "_" for c in word):
        return False
    letters = [c for c in word if c.isalpha()]
    if all(c.isupper() for c in letters):
        return False  # acronyms, shouting
    if any(c.isupper() for c in word[1:]):
        return False  # iPhone, macOS, McDonald
    return True
