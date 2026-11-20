"""The deterministic rule engine: a port of Rules/Rule.swift,
BuiltInRules.swift and PhraseListRule.swift.

Rule IDs, names, summaries, messages and patterns are those of the macOS
edition, so the two editions flag the same things (tests/test_core.py holds
the ported RuleTests).
"""

from __future__ import annotations

from dataclasses import dataclass

from . import dialect as lexicon
from . import phrases as P
from . import uregex
from .model import CheckSettings, Formality, Issue, IssueCategory, IssueSeverity, IssueSource, TextSpan
from .text import WORD_PATTERN, ExclusionZones, SentenceSplitter
from .textutil import capitalize_first, is_whitespace, match_case

C, S = IssueCategory, IssueSeverity


@dataclass(frozen=True)
class RuleInfo:
    id: str
    name: str
    summary: str
    category: IssueCategory
    default_enabled: bool = True


class RuleContext:
    def __init__(self, text: str, settings: CheckSettings):
        self.text = text
        self.settings = settings

    def char(self, index: int) -> str | None:
        return self.text[index] if 0 <= index < len(self.text) else None


class Rule:
    info: RuleInfo

    def check(self, ctx: RuleContext) -> list[Issue]:
        raise NotImplementedError

    def make_issue(self, start: int, end: int, ctx: RuleContext, suggestions: list[str], message: str,
                   category: IssueCategory | None = None, severity: IssueSeverity | None = None) -> Issue:
        return Issue(span=TextSpan(start, end - start), original=ctx.text[start:end], suggestions=list(suggestions),
                     category=category or self.info.category, severity=severity, message=message,
                     rule_id=self.info.id, source=IssueSource.RULES)


# --- phrase lists -------------------------------------------------------------------------

class PhraseListRule(Rule):
    def __init__(self, info: RuleInfo, entries: list[P.PhraseEntry]):
        self.info = info
        self.compiled = [(uregex.compile(e.pattern, e.case_insensitive), e) for e in entries]

    def check(self, ctx: RuleContext) -> list[Issue]:
        issues = []
        for rx, entry in self.compiled:
            for m in rx.finditer(ctx.text):
                issue = self._issue(m, entry, ctx)
                if issue is not None:
                    issues.append(issue)
        return issues

    def _issue(self, m, entry: P.PhraseEntry, ctx: RuleContext) -> Issue | None:
        start, end = m.start(), m.end()
        original = ctx.text[start:end]
        replacements = [match_case(self.expand(t, m), original) for t in entry.replacements]

        # Deleting a phrase should also delete one adjacent run of spaces.
        if "" in replacements:
            stop = end
            while ctx.char(stop) in (" ", "\t"):
                stop += 1
            if stop > end:
                trailing = ctx.text[end:stop]
                end = stop
                replacements = [r + trailing if r else "" for r in replacements]
            else:
                begin = start
                while ctx.char(begin - 1) in (" ", "\t"):
                    begin -= 1
                if begin < start:
                    leading = ctx.text[begin:start]
                    start = begin
                    replacements = [leading + r if r else "" for r in replacements]

        full = ctx.text[start:end]
        filtered = [r for r in replacements if r != full]
        if entry.replacements and not filtered:
            return None
        return Issue(span=TextSpan(start, end - start), original=full, suggestions=filtered,
                     category=entry.category or self.info.category, severity=entry.severity, message=entry.message,
                     rule_id=self.info.id, source=IssueSource.RULES)

    @staticmethod
    def expand(template: str, m) -> str:
        if "$" not in template:
            return template
        result = template
        for group in range(min(m.re.groups, 3), 0, -1):
            result = result.replace(f"${group}", m.group(group) or "")
        return result


# --- repeated words ---------------------------------------------------------------------------

class RepeatedWordRule(Rule):
    info = RuleInfo("repeated-word", "Repeated words", "Accidental duplicates such as “the the”.", C.GRAMMAR)
    PATTERN = uregex.compile(r"\b(\p{L}+)(?:[ \t]+|[ \t]*\n[ \t]*)(\1)\b", case_insensitive=True)
    ALLOWED = frozenset({
        "had", "that", "bye", "ha", "no", "so", "very", "really", "knock", "tut", "chop", "bang", "hush", "aye",
        "pom", "dum", "la", "na", "boo", "yeah", "well", "now", "there", "pretty", "far", "is",
    })

    def check(self, ctx):
        out = []
        for m in self.PATTERN.finditer(ctx.text):
            first = m.group(1)
            if first.lower() in self.ALLOWED:
                continue
            out.append(self.make_issue(m.start(), m.end(), ctx, [first], f"Repeated word “{first}”."))
        return out


# --- a / an ------------------------------------------------------------------------------------

class ArticleRule(Rule):
    info = RuleInfo("a-an", "“a” vs “an”", "Uses the sound of the next word, including acronyms and numbers.",
                    C.GRAMMAR)
    PATTERN = uregex.compile(r"\b(an?|An?)[ \t]+([\p{L}\p{N}][\p{L}\p{N}'’\-.]*)")
    SILENT_H = ("hour", "honest", "honor", "honour", "heir")
    CONSONANT_SOUND_PREFIXES = (
        "unanim", "unary", "unesco", "use", "usu", "usag", "uti", "ute", "uto", "ura", "uri", "ure", "uro",
        "euro", "eu", "ewe", "ouija", "uk", "ubiq", "uvula", "u-",
    )
    WORD_LIKE_ACRONYMS = frozenset({"nasa", "nato", "nafta", "unesco", "unicef", "opec", "laser", "radar", "scuba",
                                    "lan", "wan", "pin", "gif", "asap"})
    AMBIGUOUS = frozenset({"faq", "sql", "herb", "herbs", "herbal"})

    @classmethod
    def expects_an(cls, raw: str) -> bool | None:
        """True = "an", False = "a", None = unsure (don't flag)."""
        word = raw
        while word and not (word[-1].isalpha() or word[-1].isnumeric()):
            word = word[:-1]
        if not word:
            return None
        first = word[0]
        lower = word.lower()
        if lower in cls.AMBIGUOUS or lower.startswith("herb"):
            return None
        if first.isnumeric():
            digits = ""
            for ch in word:
                if ch.isnumeric() or ch == ",":
                    digits += ch
                else:
                    break
            digits = digits.replace(",", "")
            return digits.startswith("8") or digits in ("11", "18")
        letters = [c for c in word if c.isalpha()]
        is_acronym = 2 <= len(letters) <= 5 and all(c.isupper() for c in letters) \
            and "".join(letters).lower() not in cls.WORD_LIKE_ACRONYMS
        is_single = len(letters) == 1 and (len(word) == 1 or word[1:2] == "-")
        if is_acronym or is_single:
            # Letter names that start with a vowel sound: A E F H I L M N O R S X.
            return first.lower() in "aefhilmnorsx"
        if lower.startswith(cls.SILENT_H):
            return True
        if lower in ("one", "once") or lower.startswith("one-"):
            return False
        if lower.startswith(cls.CONSONANT_SOUND_PREFIXES):
            return False
        if lower.startswith("uni"):
            # "unicorn", "unit", "universal" (you-) vs "unimportant", "uninformed", "unidentified" (un-).
            return len(lower) > 3 and lower[3] in "mnd"
        return first.lower() in "aeiou"

    def check(self, ctx):
        out = []
        for m in self.PATTERN.finditer(ctx.text):
            article, nxt = m.group(1), m.group(2)
            wants_an = self.expects_an(nxt)
            if wants_an is None:
                continue
            # A capitalised "A" mid-sentence is usually a label ("Plan A is …"): only accept it at a sentence start.
            if article[0].isupper() and not self._sentence_start(m.start(1), ctx):
                continue
            if wants_an == (len(article) == 2):
                continue
            replacement = match_case("an" if wants_an else "a", article)
            message = (f"Use “an” before a vowel sound (“{nxt}”)." if wants_an
                       else f"Use “a” before a consonant sound (“{nxt}”).")
            out.append(self.make_issue(m.start(1), m.end(1), ctx, [replacement], message))
        return out

    @staticmethod
    def _sentence_start(index: int, ctx: RuleContext) -> bool:
        i = index - 1
        while ctx.char(i) in (" ", "\t"):
            i -= 1
        c = ctx.char(i)
        return c is None or c in ".!?\n\"“(:-*#"


# --- capitalisation ----------------------------------------------------------------------------

class SentenceCapitalizationRule(Rule):
    info = RuleInfo("sentence-capitalization", "Sentence capitalisation",
                    "A new sentence should start with a capital letter.", C.GRAMMAR)
    PATTERN = uregex.compile(r"(?<=[.!?])[ \t]+(\p{Ll}[\p{L}'’]*)")

    def check(self, ctx):
        out = []
        for m in self.PATTERN.finditer(ctx.text):
            p = m.start() - 1
            punct = ctx.char(p)
            if punct is None:
                continue
            # Ellipsis or "?!" sequences may continue a sentence.
            if ctx.char(p - 1) in (".", "?", "!"):
                continue
            if punct == ".":
                word = SentenceSplitter.word_before(ctx.text, p)
                if not word or word in SentenceSplitter.ABBREVIATIONS or len(word) == 1:
                    continue
                # Domain-like or numeric tokens ("example.com", "v1.2").
                if "." in word:
                    continue
            word = m.group(1)
            # Deliberate lower-case brand names: iPhone, macOS, eBay.
            if any(c.isupper() for c in word[1:]):
                continue
            out.append(self.make_issue(m.start(1), m.end(1), ctx, [capitalize_first(word)],
                                       "Start the sentence with a capital letter.", severity=S.WARNING))
        return out


class LowercaseIRule(Rule):
    info = RuleInfo("lowercase-i", "Lower-case “i”", "The pronoun “I” is always capitalised.", C.GRAMMAR)
    PATTERN = uregex.compile(r"(?<![\p{L}\p{N}_.'’\-(\[])i(?![\p{L}\p{N}_.\-)\]])(?!\s*[=<>+*/\[\](){}])")

    def check(self, ctx):
        return [self.make_issue(m.start(), m.end(), ctx, ["I"], "The pronoun “I” is always capitalised.")
                for m in self.PATTERN.finditer(ctx.text)]


class ProperNounRule(Rule):
    info = RuleInfo("proper-nouns", "Days, months and languages", "“monday” → “Monday”, “english” → “English”.",
                    C.GRAMMAR)
    PATTERN = uregex.compile(r"\b(?:" + "|".join(P.ALWAYS_CAPITALIZED) + r")\b")

    def check(self, ctx):
        out = []
        for m in self.PATTERN.finditer(ctx.text):
            cap = capitalize_first(m.group(0))
            out.append(self.make_issue(m.start(), m.end(), ctx, [cap],
                                       f"“{cap}” is a proper noun and takes a capital letter.", severity=S.WARNING))
        return out


# --- dialect ---------------------------------------------------------------------------------------

class DialectSpellingRule(Rule):
    info = RuleInfo("dialect-spelling", "Regional spelling",
                    "Keeps spelling consistent with your chosen variety of English (colour/color, organise/organize).",
                    C.SPELLING)
    WORD = uregex.compile(r"\b\p{L}+\b")

    def check(self, ctx):
        d = ctx.settings.dialect
        out = []
        for m in self.WORD.finditer(ctx.text):
            word = m.group(0)
            if len(word) < 3:
                continue
            preferred = lexicon.preferred_spelling(word, d)
            if preferred is None:
                continue
            out.append(self.make_issue(m.start(), m.end(), ctx, [preferred],
                                       f"{d.short_name} spelling is “{preferred}”.", severity=S.SUGGESTION))
        return out


# --- spacing ---------------------------------------------------------------------------------------

class MultipleSpacesRule(Rule):
    info = RuleInfo("multiple-spaces", "Multiple spaces", "Two or more spaces between words.", C.TYPOGRAPHY)
    PATTERN = uregex.compile(r"(?<=\S) {2,}(?=\S)")

    def check(self, ctx):
        return [self.make_issue(m.start(), m.end(), ctx, [" "], "Use a single space.")
                for m in self.PATTERN.finditer(ctx.text)]


class SpaceBeforePunctuationRule(Rule):
    info = RuleInfo("space-before-punctuation", "Space before punctuation", "“word ,” → “word,”.", C.PUNCTUATION)
    PATTERN = uregex.compile(r"""(?<=[\p{L}\p{N})\]"'”’])[ \t]+(?=[,;:!?](?:\s|$)|\.(?:\s|$))""")

    def check(self, ctx):
        return [self.make_issue(m.start(), m.end(), ctx, [""], "Remove the space before the punctuation mark.")
                for m in self.PATTERN.finditer(ctx.text)]


class MissingSpaceRule(Rule):
    info = RuleInfo("missing-space", "Missing space after punctuation", "“word,word” → “word, word”.",
                    C.PUNCTUATION)
    COMMA = uregex.compile(r"(?<=\p{L}{2})([,;])(?=\p{L}{2})")
    SENTENCE = uregex.compile(r"(?<=\p{Ll}{2})([.!?])(?=\p{Lu}\p{Ll})")

    def check(self, ctx):
        out = []
        for rx in (self.COMMA, self.SENTENCE):
            for m in rx.finditer(ctx.text):
                mark = m.group(0)
                out.append(self.make_issue(m.start(), m.end(), ctx, [mark + " "], f"Add a space after “{mark}”."))
        return out


# --- brackets and quotes -----------------------------------------------------------------------------

class UnbalancedPairsRule(Rule):
    info = RuleInfo("unbalanced-pairs", "Unmatched brackets and quotes",
                    "An opening “(” without a closing “)”, an odd number of quotation marks.", C.PUNCTUATION)
    OPENERS = {"(": ")", "[": "]", "{": "}"}
    CLOSERS = frozenset(")]}")

    def check(self, ctx):
        out: list[Issue] = []
        start = 0
        n = len(ctx.text)
        for i in range(n + 1):
            if i == n or ctx.text[i] == "\n":
                self._paragraph(start, i, ctx, out)
                start = i + 1
        return out

    def _paragraph(self, start: int, end: int, ctx: RuleContext, out: list[Issue]) -> None:
        if end <= start:
            return
        t = ctx.text
        stack: list[tuple[str, int]] = []
        straight: list[int] = []
        curly_open: list[int] = []
        curly_unmatched: list[int] = []
        # List markers such as "1)" or "a)" at the start of a line are not brackets.
        first = start
        while first < end and is_whitespace(t[first]):
            first += 1
        for i in range(start, end):
            u = t[i]
            if u in self.OPENERS:
                stack.append((u, i))
            elif u in self.CLOSERS:
                if stack and self.OPENERS[stack[-1][0]] == u:
                    stack.pop()
                elif not (u == ")" and i - first <= 3):
                    out.append(self.make_issue(i, i + 1, ctx, [],
                                               "This closing bracket has no matching opening bracket."))
            elif u == '"':
                straight.append(i)
            elif u == "“":
                curly_open.append(i)
            elif u == "”":
                if curly_open:
                    curly_open.pop()
                else:
                    curly_unmatched.append(i)
        for _, pos in stack:
            out.append(self.make_issue(pos, pos + 1, ctx, [], "This bracket is never closed."))
        if len(straight) % 2 == 1:
            out.append(self.make_issue(straight[-1], straight[-1] + 1, ctx, [], "Unmatched quotation mark."))
        for pos in curly_open + curly_unmatched:
            out.append(self.make_issue(pos, pos + 1, ctx, [], "Unmatched quotation mark."))


# --- style -------------------------------------------------------------------------------------------

class PassiveVoiceRule(Rule):
    info = RuleInfo("passive-voice", "Passive voice", "“The report was written by …”. Not wrong, but often weaker.",
                    C.STYLE)
    _ADVERBS = ("not|never|also|often|always|usually|already|then|just|still|completely|fully|widely|largely|"
                "generally|frequently|rarely|being")
    PATTERN = uregex.compile(r"\b(?:am|is|are|was|were|be|been|being)\s+(?:(?:" + _ADVERBS + r")\s+)?(\p{L}+ed|"
                             + "|".join(P.IRREGULAR_PARTICIPLES) + r")\b", case_insensitive=True)

    def check(self, ctx):
        out = []
        for m in self.PATTERN.finditer(ctx.text):
            if m.group(1).lower() in P.NOT_PASSIVE_PARTICIPLES:
                continue
            out.append(self.make_issue(m.start(), m.end(), ctx, [],
                                       "Passive voice. Consider an active construction if the actor matters.",
                                       severity=S.HINT))
        return out


class LongSentenceRule(Rule):
    info = RuleInfo("long-sentence", "Long sentences", "Sentences above your word limit (Preferences › General).",
                    C.CLARITY)

    def check(self, ctx):
        limit = max(10, ctx.settings.long_sentence_word_limit)
        out = []
        for s in SentenceSplitter.sentences(ctx.text):
            words = sum(1 for _ in WORD_PATTERN.finditer(ctx.text, s.location, s.upper_bound))
            if words > limit:
                out.append(self.make_issue(s.location, s.upper_bound, ctx, [],
                                           f"This sentence has {words} words. Consider splitting it.",
                                           severity=S.HINT))
        return out


class FormalityRule(Rule):
    info = RuleInfo("formality", "Formality",
                    "Flags slang unless your goal is informal, and contractions when your goal is formal.", C.TONE)
    CONTRACTIONS = [(uregex.compile(P.literal_pattern(w), True), r) for w, r in P.CONTRACTIONS]
    SLANG = [(uregex.compile(P.literal_pattern(w), True), r) for w, r in P.SLANG]

    def check(self, ctx):
        formality = ctx.settings.goals.formality
        out = []
        if formality is not Formality.INFORMAL:
            out += self._run(self.SLANG, ctx, "Informal word. Consider a more standard alternative.")
        if formality is Formality.FORMAL:
            out += self._run(self.CONTRACTIONS, ctx, "Contractions can feel informal in formal writing.")
        return out

    def _run(self, compiled, ctx, message):
        out = []
        for rx, replacements in compiled:
            for m in rx.finditer(ctx.text):
                original = m.group(0)
                out.append(self.make_issue(m.start(), m.end(), ctx, [match_case(r, original) for r in replacements],
                                           message, severity=S.HINT))
        return out


# --- the engine ---------------------------------------------------------------------------------------

def _phrase_rule(rid, name, summary, category, entries, default_enabled=True):
    return PhraseListRule(RuleInfo(rid, name, summary, category, default_enabled), entries)


RULES: list[Rule] = [
    RepeatedWordRule(),
    ArticleRule(),
    _phrase_rule("common-errors", "Common mistakes",
                 "“could of”, “more then”, “should have went”, mixed-up idioms and similar.", C.GRAMMAR,
                 P.COMMON_ERRORS),
    SentenceCapitalizationRule(),
    LowercaseIRule(),
    ProperNounRule(),
    DialectSpellingRule(),
    MultipleSpacesRule(),
    SpaceBeforePunctuationRule(),
    MissingSpaceRule(),
    _phrase_rule("double-punctuation", "Repeated punctuation", "“..”, “,,”, “!!” and similar.", C.PUNCTUATION,
                 P.DOUBLE_PUNCTUATION),
    UnbalancedPairsRule(),
    _phrase_rule("wordiness", "Wordy phrases", "“in order to” → “to”, “due to the fact that” → “because”.",
                 C.CONCISION, P.WORDINESS),
    _phrase_rule("redundancy", "Redundant phrases", "“end result”, “revert back”, “PIN number”.", C.CONCISION,
                 P.REDUNDANCY),
    _phrase_rule("intensifiers", "Weak intensifiers", "“very good” → “excellent”.", C.WORD_CHOICE, P.INTENSIFIERS),
    _phrase_rule("cliches", "Clichés", "“at the end of the day”, “think outside the box”.", C.STYLE, P.CLICHES),
    PassiveVoiceRule(),
    LongSentenceRule(),
    FormalityRule(),
    _phrase_rule("fillers", "Filler words", "“basically”, “actually”, “literally”.", C.CONCISION, P.FILLERS,
                 default_enabled=False),
    _phrase_rule("inclusive-language", "Inclusive language", "“chairman” → “chair”, “manpower” → “workforce”.",
                 C.TONE, P.INCLUSIVE, default_enabled=False),
    _phrase_rule("smart-typography", "Typographic dashes and ellipses", "“--” → “—”, “...” → “…”.", C.TYPOGRAPHY,
                 P.SMART_TYPOGRAPHY, default_enabled=False),
]

RULE_INFOS: list[RuleInfo] = [r.info for r in RULES]


class RuleEngine:
    """Runs all enabled deterministic rules. Pure and thread-safe: call it off the main thread."""

    def __init__(self, settings: CheckSettings):
        self.settings = settings

    def check(self, text: str) -> list[Issue]:
        if not text:
            return []
        ctx = RuleContext(text, self.settings)
        zones = ExclusionZones.compute(text)
        issues: list[Issue] = []
        for rule in RULES:
            if self.settings.is_enabled(rule.info):
                issues.extend(rule.check(ctx))
        issues = [i for i in issues if not ExclusionZones.is_excluded(i.span, zones)]
        issues.sort(key=lambda i: i.span.location)
        return issues
