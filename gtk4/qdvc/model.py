"""Issues and settings: a port of the macOS edition's Model/Issue.swift and
Model/CheckSettings.swift.

Spans are in characters (Unicode code points), which is what Gtk.TextIter
offsets count, where the macOS edition counts UTF-16 units for NSString.
Nothing is stored in either unit, so the editions need not agree on it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from enum import Enum, IntEnum


# --- writing goals ---------------------------------------------------------------

class Dialect(Enum):
    US = "en-US"
    GB = "en-GB"
    GB_OXFORD = "en-GB-oxendict"
    CA = "en-CA"
    AU = "en-AU"

    @property
    def display_name(self) -> str:
        return {
            Dialect.US: "English (US)",
            Dialect.GB: "English (UK)",
            Dialect.GB_OXFORD: "English (UK, Oxford -ize)",
            Dialect.CA: "English (Canada)",
            Dialect.AU: "English (Australia)",
        }[self]

    @property
    def short_name(self) -> str:
        return {Dialect.US: "US", Dialect.GB: "UK", Dialect.GB_OXFORD: "UK (Oxford)",
                Dialect.CA: "Canadian", Dialect.AU: "Australian"}[self]

    @property
    def prompt_name(self) -> str:
        """Wording used inside the language-model prompt."""
        return {
            Dialect.US: "American English",
            Dialect.GB: "British English (-ise spellings)",
            Dialect.GB_OXFORD: "British English with Oxford spelling (-ize endings, but -yse as in analyse)",
            Dialect.CA: "Canadian English (-our and -ize spellings)",
            Dialect.AU: "Australian English (-our and -ise spellings)",
        }[self]

    @property
    def spelling_tags(self) -> list[str]:
        """Enchant dictionary tags to try, best first (the macOS edition's appleSpellLanguage)."""
        return {
            Dialect.US: ["en_US", "en"],
            Dialect.GB: ["en_GB", "en"],
            Dialect.GB_OXFORD: ["en_GB", "en"],
            Dialect.CA: ["en_CA", "en_US", "en"],
            Dialect.AU: ["en_AU", "en_GB", "en"],
        }[self]


class Audience(Enum):
    GENERAL = "general"
    KNOWLEDGEABLE = "knowledgeable"
    EXPERT = "expert"

    @property
    def display_name(self) -> str:
        return self.value.capitalize()


class Formality(Enum):
    INFORMAL = "informal"
    NEUTRAL = "neutral"
    FORMAL = "formal"

    @property
    def display_name(self) -> str:
        return self.value.capitalize()


class WritingDomain(Enum):
    GENERAL = "general"
    ACADEMIC = "academic"
    BUSINESS = "business"
    TECHNICAL = "technical"
    CREATIVE = "creative"
    CASUAL = "casual"
    EMAIL = "email"

    @property
    def display_name(self) -> str:
        return "Email" if self is WritingDomain.EMAIL else self.value.capitalize()


def enum_from(cls, value, default):
    """Tolerant decoding: an unknown stored value falls back to the default."""
    try:
        return cls(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class WritingGoals:
    audience: Audience = Audience.GENERAL
    formality: Formality = Formality.NEUTRAL
    domain: WritingDomain = WritingDomain.GENERAL

    @property
    def prompt_description(self) -> str:
        return f"audience: {self.audience.value}; formality: {self.formality.value}; domain: {self.domain.value}"


@dataclass(frozen=True)
class CheckSettings:
    dialect: Dialect = Dialect.US
    goals: WritingGoals = field(default_factory=WritingGoals)
    #: Per-rule on/off overrides (a tuple of pairs, so the settings stay hashable).
    rule_overrides: tuple[tuple[str, bool], ...] = ()
    long_sentence_word_limit: int = 35
    #: Words the user never wants flagged as misspelled.
    personal_dictionary: tuple[str, ...] = ()

    def is_enabled(self, info) -> bool:
        for rid, on in self.rule_overrides:
            if rid == info.id:
                return on
        return info.default_enabled

    @property
    def overrides(self) -> dict[str, bool]:
        return dict(self.rule_overrides)

    def with_override(self, rule_id: str, enabled: bool | None) -> "CheckSettings":
        d = self.overrides
        if enabled is None:
            d.pop(rule_id, None)
        else:
            d[rule_id] = enabled
        return replace(self, rule_overrides=tuple(sorted(d.items())))

    @property
    def ai_cache_key(self) -> str:
        """Everything that changes what the language model should say about a passage."""
        g = self.goals
        return f"{self.dialect.value}|{g.audience.value}|{g.formality.value}|{g.domain.value}"


# --- issues ------------------------------------------------------------------------

class IssueGroup(Enum):
    """High-level grouping used for colours and filters in the UI."""
    CORRECTNESS = "correctness"
    CLARITY = "clarity"
    ENGAGEMENT = "engagement"
    DELIVERY = "delivery"

    @property
    def display_name(self) -> str:
        return self.value.capitalize()


class IssueSeverity(IntEnum):
    HINT = 0
    SUGGESTION = 1
    WARNING = 2
    ERROR = 3


class IssueCategory(Enum):
    SPELLING = "spelling"
    GRAMMAR = "grammar"
    PUNCTUATION = "punctuation"
    CONSISTENCY = "consistency"
    CLARITY = "clarity"
    CONCISION = "concision"
    WORD_CHOICE = "wordChoice"
    STYLE = "style"
    TONE = "tone"
    TYPOGRAPHY = "typography"

    @property
    def display_name(self) -> str:
        return "Word choice" if self is IssueCategory.WORD_CHOICE else self.value.capitalize()

    @property
    def group(self) -> IssueGroup:
        return _GROUPS[self]

    @property
    def default_severity(self) -> IssueSeverity:
        return _SEVERITIES[self]

    @staticmethod
    def from_loose_name(name: str) -> "IssueCategory | None":
        """Lenient mapping for category names produced by a language model."""
        key = "".join(ch for ch in name.lower() if ch.isalpha())
        return _LOOSE.get(key)


_C = IssueCategory
_GROUPS = {
    _C.SPELLING: IssueGroup.CORRECTNESS, _C.GRAMMAR: IssueGroup.CORRECTNESS,
    _C.PUNCTUATION: IssueGroup.CORRECTNESS, _C.CONSISTENCY: IssueGroup.CORRECTNESS,
    _C.CLARITY: IssueGroup.CLARITY, _C.CONCISION: IssueGroup.CLARITY,
    _C.WORD_CHOICE: IssueGroup.ENGAGEMENT, _C.STYLE: IssueGroup.ENGAGEMENT,
    _C.TONE: IssueGroup.DELIVERY, _C.TYPOGRAPHY: IssueGroup.DELIVERY,
}
_SEVERITIES = {
    _C.SPELLING: IssueSeverity.ERROR, _C.GRAMMAR: IssueSeverity.ERROR,
    _C.PUNCTUATION: IssueSeverity.WARNING, _C.CONSISTENCY: IssueSeverity.WARNING,
    _C.CLARITY: IssueSeverity.SUGGESTION, _C.CONCISION: IssueSeverity.SUGGESTION,
    _C.WORD_CHOICE: IssueSeverity.SUGGESTION,
    _C.STYLE: IssueSeverity.HINT, _C.TONE: IssueSeverity.HINT, _C.TYPOGRAPHY: IssueSeverity.HINT,
}
_LOOSE = {}
for _names, _cat in (
    (("spelling", "typo", "misspelling", "orthography"), _C.SPELLING),
    (("grammar", "agreement", "tense", "capitalization", "capitalisation", "syntax"), _C.GRAMMAR),
    (("punctuation", "comma"), _C.PUNCTUATION),
    (("consistency",), _C.CONSISTENCY),
    (("clarity", "readability", "ambiguity"), _C.CLARITY),
    (("concision", "conciseness", "wordiness", "redundancy", "brevity"), _C.CONCISION),
    (("wordchoice", "vocabulary", "usage", "diction"), _C.WORD_CHOICE),
    (("style", "fluency"), _C.STYLE),
    (("tone", "formality", "register"), _C.TONE),
    (("typography", "formatting", "spacing"), _C.TYPOGRAPHY),
):
    for _n in _names:
        _LOOSE[_n] = _cat


class IssueSource(Enum):
    RULES = "rules"
    SPELL_CHECKER = "spellChecker"
    AI = "ai"

    @property
    def display_name(self) -> str:
        return {IssueSource.RULES: "Rules", IssueSource.SPELL_CHECKER: "Spelling", IssueSource.AI: "AI"}[self]


@dataclass(frozen=True, order=True)
class TextSpan:
    """A range in characters (code points)."""
    location: int
    length: int

    @property
    def upper_bound(self) -> int:
        return self.location + self.length

    def intersects(self, other: "TextSpan") -> bool:
        return self.location < other.upper_bound and other.location < self.upper_bound

    def contains(self, other: "TextSpan") -> bool:
        return other.location >= self.location and other.upper_bound <= self.upper_bound

    def offset(self, delta: int) -> "TextSpan":
        return TextSpan(self.location + delta, self.length)


def substring(text: str, span: TextSpan) -> str | None:
    """The text at a span, or None if the span is out of bounds."""
    if span.location < 0 or span.length < 0 or span.upper_bound > len(text):
        return None
    return text[span.location:span.upper_bound]


@dataclass
class Issue:
    span: TextSpan
    #: The exact text the issue refers to. Used to validate the span after edits.
    original: str
    category: IssueCategory
    message: str
    rule_id: str
    source: IssueSource
    #: Replacement candidates. An empty string means "delete".
    suggestions: list[str] = field(default_factory=list)
    severity: IssueSeverity | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def __post_init__(self):
        if self.severity is None:
            self.severity = self.category.default_severity

    @property
    def fingerprint(self) -> str:
        """Text-based identity used for "Ignore" so the decision survives edits elsewhere."""
        return f"{self.category.value}|{self.original}|{self.suggestions[0] if self.suggestions else ''}"

    def copy(self, **changes) -> "Issue":
        return replace(self, suggestions=list(self.suggestions), **changes)
