"""Preferences: a port of the macOS edition's SettingsStore (and its
LlamaSettings), kept at $XDG_CONFIG_HOME/qdvc-articulate/config.yml. In the
Flatpak, XDG_CONFIG_HOME is the app's own
~/.var/app/qdvc.articulate.gtk4app/config, never shared or synced.

Written with the suite's YAML (yamlio). Decoding is tolerant, as in the
macOS edition, so adding a setting later never wipes saved preferences.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

from . import yamlio as Y
from .ai import PromptFormat
from .documents import write_text_file
from .model import Audience, CheckSettings, Dialect, Formality, WritingDomain, WritingGoals, enum_from

MAX_RECENT = 12
CONTEXT_LENGTHS = [2048, 4096, 8192, 16384, 32768]
OUTPUT_TOKENS = [512, 768, 1024, 1536, 2048]
CHUNK_LENGTHS = [600, 900, 1200, 1800, 2400]


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / "qdvc-articulate"


def state_dir() -> Path:
    """Drafts of unsaved documents and the open tabs (not preferences)."""
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return Path(base) / "qdvc-articulate"


@dataclass(frozen=True)
class LlamaSettings:
    context_length: int = 8192
    threads: int = 0
    max_output_tokens: int = 1024
    chunk_length: int = 1200
    temperature: float = 0.0
    prompt_format: PromptFormat = PromptFormat.AUTOMATIC
    reuse_prompt_cache: bool = True
    load_at_launch: bool = True


def _int(node, default: int, lo: int, hi: int) -> int:
    v = node.int if node is not None else None
    return v if v is not None and lo <= v <= hi else default


def _bool(node, default: bool) -> bool:
    v = node.bool if node is not None else None
    return default if v is None else v


def _float(node, default: float, lo: float, hi: float) -> float:
    try:
        v = float(node.string) if node is not None and node.string is not None else None
    except ValueError:
        v = None
    return v if v is not None and lo <= v <= hi else default


def _str(node, default: str | None = None) -> str | None:
    return node.string if node is not None and node.string is not None else default


class Preferences:
    """All preferences, with change notification: listeners get the name of what changed
    ("check", "llama", "editor", "model", "recent", "window", "checking")."""

    def __init__(self, path: Path | None = None):
        self.path = path or (config_dir() / "config.yml")
        self.check = CheckSettings()
        self.llama = LlamaSettings()
        self.editor_font_size = 12
        self.monospace = False
        self.spelling = True
        self.auto_ai = False
        self.model_path: str | None = None
        self.recent_files: list[str] = []
        self.window = {"width": 1100, "height": 760, "maximized": False, "inspector": True}
        self._listeners: list = []
        self.load()

    # --- notification --------------------------------------------------------------------

    def connect(self, fn) -> None:
        self._listeners.append(fn)

    def _changed(self, what: str) -> None:
        self.save()
        for fn in list(self._listeners):
            fn(what)

    # --- loading and saving ------------------------------------------------------------------

    def load(self) -> None:
        try:
            doc = Y.parse(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, Y.YAMLError):
            return
        g = doc.get("goals")
        goals = WritingGoals(
            audience=enum_from(Audience, _str(g.get("audience") if g else None), Audience.GENERAL),
            formality=enum_from(Formality, _str(g.get("formality") if g else None), Formality.NEUTRAL),
            domain=enum_from(WritingDomain, _str(g.get("domain") if g else None), WritingDomain.GENERAL))
        overrides = []
        node = doc.get("rule_overrides")
        for p in (node.pairs if node is not None else []):
            if p.value.bool is not None:
                overrides.append((p.key, p.value.bool))
        dictionary = doc.get("personal_dictionary")
        self.check = CheckSettings(
            dialect=enum_from(Dialect, _str(doc.get("dialect")), Dialect.US),
            goals=goals,
            rule_overrides=tuple(sorted(overrides)),
            long_sentence_word_limit=_int(doc.get("long_sentence_word_limit"), 35, 10, 100),
            personal_dictionary=tuple(dictionary.strings if dictionary is not None else ()))
        l = doc.get("llama")  # noqa: E741
        d = LlamaSettings()
        if l is not None:
            self.llama = LlamaSettings(
                context_length=_int(l.get("context_length"), d.context_length, 512, 262144),
                threads=_int(l.get("threads"), d.threads, 0, 256),
                max_output_tokens=_int(l.get("max_output_tokens"), d.max_output_tokens, 64, 8192),
                chunk_length=_int(l.get("chunk_length"), d.chunk_length, 200, 10000),
                temperature=_float(l.get("temperature"), d.temperature, 0.0, 2.0),
                prompt_format=enum_from(PromptFormat, _str(l.get("prompt_format")), d.prompt_format),
                reuse_prompt_cache=_bool(l.get("reuse_prompt_cache"), d.reuse_prompt_cache),
                load_at_launch=_bool(l.get("load_at_launch"), d.load_at_launch))
        self.editor_font_size = _int(doc.get("editor_font_size"), 12, 8, 32)
        self.monospace = _bool(doc.get("monospace"), False)
        self.spelling = _bool(doc.get("spelling"), True)
        self.auto_ai = _bool(doc.get("auto_ai"), False)
        self.model_path = _str(doc.get("model_path")) or None
        recent = doc.get("recent_files")
        self.recent_files = [p for p in (recent.strings if recent is not None else []) if p][:MAX_RECENT]
        w = doc.get("window")
        if w is not None:
            self.window = {"width": _int(w.get("width"), 1100, 360, 10000),
                           "height": _int(w.get("height"), 760, 300, 10000),
                           "maximized": _bool(w.get("maximized"), False),
                           "inspector": _bool(w.get("inspector"), True)}

    def to_yaml(self) -> str:
        c, l = self.check, self.llama  # noqa: E741
        pairs: list[tuple[str, Y.Node]] = [
            ("dialect", Y.s(c.dialect.value)),
            ("goals", Y.mapping([("audience", Y.s(c.goals.audience.value)),
                                 ("formality", Y.s(c.goals.formality.value)),
                                 ("domain", Y.s(c.goals.domain.value))])),
            ("long_sentence_word_limit", Y.num(c.long_sentence_word_limit)),
            ("rule_overrides", Y.mapping([(k, Y.flag(v)) for k, v in c.rule_overrides])),
            ("personal_dictionary", Y.str_list(list(c.personal_dictionary))),
            ("spelling", Y.flag(self.spelling)),
            ("auto_ai", Y.flag(self.auto_ai)),
            ("editor_font_size", Y.num(self.editor_font_size)),
            ("monospace", Y.flag(self.monospace)),
        ]
        if self.model_path:
            pairs.append(("model_path", Y.s(self.model_path)))
        pairs += [
            ("llama", Y.mapping([
                ("context_length", Y.num(l.context_length)), ("threads", Y.num(l.threads)),
                ("max_output_tokens", Y.num(l.max_output_tokens)), ("chunk_length", Y.num(l.chunk_length)),
                ("temperature", Y.s(f"{l.temperature:.2f}")), ("prompt_format", Y.s(l.prompt_format.value)),
                ("reuse_prompt_cache", Y.flag(l.reuse_prompt_cache)), ("load_at_launch", Y.flag(l.load_at_launch))])),
            ("recent_files", Y.str_list(self.recent_files)),
            ("window", Y.mapping([("width", Y.num(self.window["width"])), ("height", Y.num(self.window["height"])),
                                  ("maximized", Y.flag(self.window["maximized"])),
                                  ("inspector", Y.flag(self.window["inspector"]))])),
        ]
        return Y.emit(Y.mapping(pairs))

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            write_text_file(self.path, self.to_yaml())
        except OSError:
            pass

    # --- changing --------------------------------------------------------------------------

    def set_check(self, check: CheckSettings) -> None:
        if check != self.check:
            self.check = check
            self._changed("check")

    def set_dialect(self, dialect: Dialect) -> None:
        self.set_check(replace(self.check, dialect=dialect))

    def set_goals(self, **kw) -> None:
        self.set_check(replace(self.check, goals=replace(self.check.goals, **kw)))

    def set_llama(self, **kw) -> None:
        llama = replace(self.llama, **kw)
        if llama != self.llama:
            self.llama = llama
            self._changed("llama")

    def set_option(self, name: str, value) -> None:
        """editor_font_size, monospace ("editor"); spelling, auto_ai ("checking")."""
        if getattr(self, name) != value:
            setattr(self, name, value)
            self._changed("editor" if name in ("editor_font_size", "monospace") else "checking")

    def set_model_path(self, path: str | None) -> None:
        if path != self.model_path:
            self.model_path = path
            self._changed("model")

    # Personal dictionary

    def add_to_dictionary(self, word: str) -> None:
        w = word.strip()
        if not w or any(x.lower() == w.lower() for x in self.check.personal_dictionary):
            return
        words = sorted([*self.check.personal_dictionary, w], key=str.casefold)
        self.set_check(replace(self.check, personal_dictionary=tuple(words)))

    def remove_from_dictionary(self, word: str) -> None:
        self.set_check(replace(self.check, personal_dictionary=tuple(
            x for x in self.check.personal_dictionary if x != word)))

    # Rules

    def set_rule(self, info, enabled: bool) -> None:
        self.set_check(self.check.with_override(info.id, None if enabled == info.default_enabled else enabled))

    def reset_rules(self) -> None:
        self.set_check(replace(self.check, rule_overrides=()))

    # Recent files and the window

    def add_recent(self, path: str) -> None:
        rest = [p for p in self.recent_files if p != path]
        recent = ([path] + rest)[:MAX_RECENT]
        if recent != self.recent_files:
            self.recent_files = recent
            self._changed("recent")

    def remove_recent(self, path: str) -> None:
        if path in self.recent_files:
            self.recent_files = [p for p in self.recent_files if p != path]
            self._changed("recent")

    def set_window(self, **kw) -> None:
        w = dict(self.window, **kw)
        if w != self.window:
            self.window = w
            self.save()
