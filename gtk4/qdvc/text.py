"""Text analysis: ports of Text/ExclusionZones.swift, SentenceSplitter.swift,
TextStatistics.swift and IssueProcessing.swift (IssueAdjuster, IssueMerger)."""

from __future__ import annotations

from dataclasses import dataclass

from . import uregex
from .model import CheckSettings, Issue, IssueCategory, TextSpan, substring
from .textutil import is_letter, is_whitespace


def _span(m, group: int = 0) -> TextSpan:
    return TextSpan(m.start(group), m.end(group) - m.start(group))


# --- exclusion zones -------------------------------------------------------------

class ExclusionZones:
    """Regions that should never be "corrected": code, URLs, e-mail addresses and Markdown link targets."""

    PATTERNS = [
        # Fenced Markdown code blocks.
        uregex.compile(r"(?ms)^[ \t]*```.*?^[ \t]*```[ \t]*$"),
        # Inline code.
        uregex.compile(r"`[^`\n]+`"),
        # URLs.
        uregex.compile(r"""\b(?:https?://|ftp://|www\.)[^\s<>"'()\[\]]+""", case_insensitive=True),
        # E-mail addresses.
        uregex.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
        # Markdown link / image targets: ](...)
        uregex.compile(r"\]\([^)\s]*\)"),
        # HTML-ish tags.
        uregex.compile(r"</?[A-Za-z][^<>\n]{0,200}>"),
    ]

    @classmethod
    def compute(cls, text: str) -> list[TextSpan]:
        zones = [_span(m) for p in cls.PATTERNS for m in p.finditer(text)]
        return sorted(zones, key=lambda s: s.location)

    @staticmethod
    def is_excluded(span: TextSpan, zones: list[TextSpan]) -> bool:
        return any(z.intersects(span) for z in zones)


# --- sentences -----------------------------------------------------------------------

class SentenceSplitter:
    """Lightweight, portable sentence segmentation."""

    #: Sentence-ending punctuation followed by whitespace and a likely sentence start, or a line break.
    BOUNDARY = uregex.compile(r"""[.!?…]+["'”’)\]]*(?=\s+["'“‘(\[]?[\p{Lu}\p{N}])|\n+""")

    ABBREVIATIONS = frozenset({
        "e.g", "i.e", "etc", "vs", "cf", "approx", "incl", "excl", "a.m", "p.m", "mr", "mrs", "ms", "dr",
        "prof", "st", "no", "nos", "vol", "fig", "figs", "al", "ca", "est", "dept", "jr", "sr", "inc", "ltd",
        "co", "corp", "min", "max", "sec", "hr", "hrs", "mins", "pp", "p", "ed", "eds", "viz", "resp", "ibid",
        "op", "cit", "misc", "govt", "univ", "gen", "col", "lt", "sgt", "capt", "rev", "hon", "u.s", "u.k",
        "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "mt", "ft",
    })

    @classmethod
    def sentences(cls, text: str) -> list[TextSpan]:
        """Trimmed sentence spans in document order."""
        spans: list[TextSpan] = []
        start = 0
        for m in cls.BOUNDARY.finditer(text):
            if text[m.start()] != "\n" and cls.ends_with_abbreviation(text, m.start()):
                continue
            end = m.end()
            cls._append(TextSpan(start, end - start), text, spans)
            start = end
        cls._append(TextSpan(start, len(text) - start), text, spans)
        return spans

    @staticmethod
    def word_before(text: str, index: int) -> str:
        """The word immediately before `index` (letters and inner dots), lowercased, without outer dots."""
        i = index - 1
        while i >= 0 and (is_letter(text[i]) or text[i] == "."):
            i -= 1
        start = i + 1
        if start >= index:
            return ""
        return text[start:index].lower().strip(".")

    @classmethod
    def ends_with_abbreviation(cls, text: str, index: int) -> bool:
        if text[index] != ".":  # only "." can follow an abbreviation
            return False
        word = cls.word_before(text, index)
        if not word:
            return False
        if word in cls.ABBREVIATIONS:
            return True
        # Single capital letter = an initial ("J. Smith").
        return len(word) == 1 and index > 0 and text[index - 1].isupper()

    @staticmethod
    def _append(span: TextSpan, text: str, spans: list[TextSpan]) -> None:
        s, e = span.location, span.upper_bound
        while s < e and is_whitespace(text[s]):
            s += 1
        while e > s and is_whitespace(text[e - 1]):
            e -= 1
        if e > s:
            spans.append(TextSpan(s, e - s))


# --- statistics ---------------------------------------------------------------------

WORD_PATTERN = uregex.compile(r"[\p{L}\p{N}]+(?:['’][\p{L}]+)*")


@dataclass
class TextStatistics:
    characters: int = 0
    characters_excluding_spaces: int = 0
    words: int = 0
    sentences: int = 0
    paragraphs: int = 0
    syllables: int = 0
    unique_words: int = 0
    longest_sentence_words: int = 0
    average_words_per_sentence: float = 0.0
    average_syllables_per_word: float = 0.0
    #: Flesch Reading Ease (higher = easier). None for very short texts.
    flesch_reading_ease: float | None = None
    #: Flesch–Kincaid grade level. None for very short texts.
    flesch_kincaid_grade: float | None = None
    #: At 238 words per minute (average adult silent reading).
    reading_time_seconds: int = 0
    #: At 150 words per minute.
    speaking_time_seconds: int = 0

    @property
    def lexical_diversity(self) -> float:
        return 0.0 if self.words == 0 else self.unique_words / self.words

    @property
    def readability_label(self) -> str:
        score = self.flesch_reading_ease
        if score is None:
            return "Not enough text"
        for limit, name in ((90, "Very easy"), (80, "Easy"), (70, "Fairly easy"), (60, "Plain English"),
                            (50, "Fairly difficult"), (30, "Difficult")):
            if score >= limit:
                return name
        return "Very difficult"

    @classmethod
    def compute(cls, text: str) -> "TextStatistics":
        st = cls()
        st.characters = len(text)
        st.characters_excluding_spaces = sum(1 for c in text if not c.isspace())
        words = [m.group(0).lower() for m in WORD_PATTERN.finditer(text)]
        st.words = len(words)
        st.unique_words = len(set(words))
        st.syllables = sum(syllable_count(w) for w in words)

        sentence_spans = [s for s in SentenceSplitter.sentences(text)
                          # Ignore "sentences" that contain no words (e.g. a line of dashes).
                          if WORD_PATTERN.search(text, s.location, s.upper_bound)]
        st.sentences = len(sentence_spans)
        for s in sentence_spans:
            n = sum(1 for _ in WORD_PATTERN.finditer(text, s.location, s.upper_bound))
            st.longest_sentence_words = max(st.longest_sentence_words, n)

        st.paragraphs = sum(1 for line in text.replace("\r\n", "\n").split("\n")
                            if any(c.isalpha() or c.isnumeric() for c in line))
        if st.sentences:
            st.average_words_per_sentence = st.words / st.sentences
        if st.words:
            st.average_syllables_per_word = st.syllables / st.words
        if st.words >= 30 and st.sentences:
            wps, spw = st.average_words_per_sentence, st.average_syllables_per_word
            st.flesch_reading_ease = 206.835 - 1.015 * wps - 84.6 * spw
            st.flesch_kincaid_grade = 0.39 * wps + 11.8 * spw - 15.59
        st.reading_time_seconds = round(st.words / 238.0 * 60.0)
        st.speaking_time_seconds = round(st.words / 150.0 * 60.0)
        return st


def syllable_count(word: str) -> int:
    """Heuristic English syllable count (good enough for readability formulas)."""
    letters = "".join(c for c in word.lower() if c.isalpha())
    if not letters:
        return 1
    if len(letters) <= 3:
        return 1
    count, previous = 0, False
    for ch in letters:
        vowel = ch in "aeiouy"
        if vowel and not previous:
            count += 1
        previous = vowel
    if letters.endswith("e") and not letters.endswith("le") and count > 1:
        count -= 1
    if (letters.endswith("es") or letters.endswith("ed")) and count > 1 \
            and not letters.endswith(("ted", "ded", "ses", "zes", "ces", "ges")):
        count -= 1
    return max(1, count)


def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{max(seconds, 0)} s"
    return f"{round(seconds / 60)} min"


# --- keeping issues in step with edits, and merging the sources -----------------------

class IssueAdjuster:
    @staticmethod
    def adjust(issues: list[Issue], edit: TextSpan, replacement_length: int) -> list[Issue]:
        """Shifts issues after an edit. Issues that overlap or touch the edited range are dropped
        (the next check will re-evaluate that text), so underlines never sit on stale text."""
        delta = replacement_length - edit.length
        out: list[Issue] = []
        for issue in issues:
            if issue.span.upper_bound < edit.location:
                out.append(issue)
            elif issue.span.location > edit.upper_bound:
                out.append(issue.copy(span=issue.span.offset(delta)))
        return out

    @staticmethod
    def transform_region(span: TextSpan, edit: TextSpan, replacement_length: int) -> TextSpan:
        """Transforms a span through an edit, growing or shrinking it if the edit happened inside it.
        Used for "this region was re-checked" bookkeeping, where dropping would be wrong."""
        delta = replacement_length - edit.length
        if span.upper_bound <= edit.location:
            return span
        if span.location >= edit.upper_bound:
            return span.offset(delta)
        start = min(span.location, edit.location)
        end = max(span.upper_bound + delta, edit.location + replacement_length)
        return TextSpan(start, max(0, end - start))


class IssueMerger:
    @staticmethod
    def merge(sources: list[list[Issue]], text: str, ignored: set[str], settings: CheckSettings,
              zones: list[TextSpan]) -> list[Issue]:
        """Validates, filters, de-duplicates and sorts issues from all sources.

        - Issues whose text no longer matches `original` are dropped (stale).
        - Ignored fingerprints, personal-dictionary words and excluded zones are removed.
        - Issues on the same span in the same group are merged (suggestions are combined).
        """
        dictionary = {w.lower() for w in settings.personal_dictionary}
        index_by_key: dict[str, int] = {}
        result: list[Issue] = []
        for source in sources:
            for issue in source:
                if issue.span.length <= 0 or substring(text, issue.span) != issue.original:
                    continue
                if issue.fingerprint in ignored:
                    continue
                if issue.category is IssueCategory.SPELLING and issue.original.lower() in dictionary:
                    continue
                if ExclusionZones.is_excluded(issue.span, zones):
                    continue
                key = f"{issue.span.location}:{issue.span.length}:{issue.category.group.value}"
                if key in index_by_key:
                    existing = result[index_by_key[key]]
                    for s in issue.suggestions:
                        if s not in existing.suggestions:
                            existing.suggestions.append(s)
                    if issue.severity > existing.severity:
                        existing.severity = issue.severity
                    continue
                index_by_key[key] = len(result)
                result.append(issue.copy())
        return sorted(result, key=lambda i: (i.span.location, i.span.length))
