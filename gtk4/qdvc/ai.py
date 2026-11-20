"""The AI review pipeline: a port of the macOS edition's ArticulateCore/AI
(TextChunker, PromptBuilder, PromptFormat, JSONGrammar, LLMResponseParser,
IssueAnchorer, AIReviewer and ReviewCache).

The pipeline is synchronous: `AIReviewer.review` is a generator meant to run
on a worker thread, yielding a `ReviewProgress` as each chunk finishes. The
model is anything with the `TextGenerating` shape (the llama.cpp engine in
qdvc.llm, or a mock in the tests).
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator, Protocol

from . import dialect as lexicon
from .model import CheckSettings, Issue, IssueCategory, IssueSource, TextSpan
from .text import ExclusionZones, SentenceSplitter
from .textutil import is_whitespace


class Cancelled(Exception):
    """The review was stopped (the user pressed Stop, or the text was replaced)."""


class CancelToken:
    def __init__(self):
        self._event = threading.Event()
        self._callbacks: list = []
        self._lock = threading.Lock()

    def cancel(self) -> None:
        with self._lock:
            self._event.set()
            callbacks = list(self._callbacks)
        for fn in callbacks:
            fn()

    def on_cancel(self, fn) -> None:
        """Calls fn when cancelled (at once if already cancelled): how the native engine's flag is set."""
        with self._lock:
            if not self._event.is_set():
                self._callbacks.append(fn)
                return
        fn()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        if self._event.is_set():
            raise Cancelled()


class TextGenerating(Protocol):
    def generate(self, prefix: str, body: str, grammar: str | None, max_tokens: int,
                 cancel: CancelToken | None = None) -> str:
        """prefix: the stable part of the prompt (may be served from a KV cache); body: the
        per-request part; grammar: an optional GBNF grammar constraining the output."""


# --- chunking ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TextChunk:
    span: TextSpan
    text: str


class TextChunker:
    """Splits a document into paragraph-based chunks for the language model.

    Chunk boundaries depend only on local content, so editing one paragraph only invalidates
    the cached result for that paragraph: re-checking a long document after a small edit is fast.
    """

    #: Paragraphs shorter than this (headings, greetings) are merged with the following paragraph.
    SHORT_PARAGRAPH_LENGTH = 80

    @classmethod
    def chunks(cls, text: str, max_length: int, zones: list[TextSpan] | None = None) -> list[TextChunk]:
        zones = zones or []
        paragraphs = [p for p in cls.paragraph_spans(text) if not any(z.contains(p) for z in zones)]

        groups: list[TextSpan] = []
        pending: TextSpan | None = None
        for p in paragraphs:
            if pending is not None:
                merged = TextSpan(pending.location, p.upper_bound - pending.location)
                if p.length < cls.SHORT_PARAGRAPH_LENGTH and merged.length < max_length:
                    pending = merged
                else:
                    groups.append(merged)
                    pending = None
            elif p.length < cls.SHORT_PARAGRAPH_LENGTH:
                pending = p
            else:
                groups.append(p)
        if pending is not None:
            groups.append(pending)

        result: list[TextChunk] = []
        for g in groups:
            if g.length <= max_length:
                result.append(TextChunk(g, text[g.location:g.upper_bound]))
            else:
                cls._split_by_sentences(g, text, max_length, result)
        return result

    @staticmethod
    def paragraph_spans(text: str) -> list[TextSpan]:
        """Paragraphs are separated by blank lines; leading and trailing whitespace is trimmed."""
        spans: list[TextSpan] = []
        n = len(text)
        start = i = 0
        while i < n:
            if text[i] == "\n":
                # Look ahead for a blank line (only whitespace until the next newline).
                j = i + 1
                while j < n and text[j] != "\n" and is_whitespace(text[j]):
                    j += 1
                if j < n and text[j] == "\n":
                    t = _trimmed(TextSpan(start, i - start), text)
                    if t:
                        spans.append(t)
                    # Skip all consecutive blank lines.
                    k = j
                    while k < n and is_whitespace(text[k]):
                        k += 1
                    start = i = k
                    continue
            i += 1
        t = _trimmed(TextSpan(start, n - start), text)
        if t:
            spans.append(t)
        return [s for s in spans if any(c.isalpha() for c in text[s.location:s.upper_bound])]

    @staticmethod
    def _split_by_sentences(group: TextSpan, text: str, max_length: int, result: list[TextChunk]) -> None:
        group_text = text[group.location:group.upper_bound]
        sentences = [s.offset(group.location) for s in SentenceSplitter.sentences(group_text)]
        start: int | None = None
        end = group.location
        for s in sentences:
            if start is not None and s.upper_bound - start > max_length:
                result.append(TextChunk(TextSpan(start, end - start), text[start:end]))
                start = None
            if start is None:
                start = s.location
            end = s.upper_bound
        if start is not None and end > start:
            result.append(TextChunk(TextSpan(start, end - start), text[start:end]))


def _trimmed(span: TextSpan, text: str) -> TextSpan | None:
    if span.length <= 0:
        return None
    s, e = span.location, span.upper_bound
    while s < e and is_whitespace(text[s]):
        s += 1
    while e > s and is_whitespace(text[e - 1]):
        e -= 1
    return TextSpan(s, e - s) if e > s else None


# --- prompts -------------------------------------------------------------------------------

@dataclass(frozen=True)
class RenderedPrompt:
    """A prompt split into a stable prefix (the instructions: identical for every chunk, so its KV
    cache can be reused) and a per-chunk body."""
    prefix: str
    body: str


class PromptFormat(Enum):
    """Chat formats for common instruction-tuned GGUF families. Prompts are rendered here rather than
    with llama.cpp's template list, which doesn't cover newer families like Gemma 4. BOS is added by
    the tokenizer, so it never appears here."""
    AUTOMATIC = "automatic"
    GEMMA4 = "gemma4"
    GEMMA = "gemma"
    CHATML = "chatml"
    LLAMA3 = "llama3"
    MISTRAL = "mistral"
    PHI3 = "phi3"
    PLAIN = "plain"

    @property
    def display_name(self) -> str:
        return {
            PromptFormat.AUTOMATIC: "Automatic",
            PromptFormat.GEMMA4: "Gemma 4",
            PromptFormat.GEMMA: "Gemma 2 / 3 / 3n",
            PromptFormat.CHATML: "ChatML (Qwen, SmolLM, many others)",
            PromptFormat.LLAMA3: "Llama 3",
            PromptFormat.MISTRAL: "Mistral [INST]",
            PromptFormat.PHI3: "Phi-3 / Phi-3.5",
            PromptFormat.PLAIN: "Plain completion",
        }[self]

    @staticmethod
    def detect(chat_template: str | None, architecture: str | None) -> "PromptFormat":
        """Picks a format from the GGUF's embedded chat template and architecture name."""
        t = chat_template
        if t:
            if "<|turn>" in t:
                return PromptFormat.GEMMA4
            if "<start_of_turn>" in t:
                return PromptFormat.GEMMA
            if "<|start_header_id|>" in t:
                return PromptFormat.LLAMA3
            if "<|im_start|>" in t:
                return PromptFormat.CHATML
            if "<|user|>" in t and "<|end|>" in t:
                return PromptFormat.PHI3
            if "[INST]" in t:
                return PromptFormat.MISTRAL
        arch = (architecture or "").lower()
        for prefix, fmt in (("gemma4", PromptFormat.GEMMA4), ("gemma", PromptFormat.GEMMA),
                            ("llama", PromptFormat.LLAMA3), ("qwen", PromptFormat.CHATML),
                            ("smollm", PromptFormat.CHATML), ("phi3", PromptFormat.PHI3),
                            ("mistral", PromptFormat.MISTRAL)):
            if arch.startswith(prefix):
                return fmt
        return PromptFormat.CHATML

    def resolved(self, chat_template: str | None, architecture: str | None) -> "PromptFormat":
        return PromptFormat.detect(chat_template, architecture) if self is PromptFormat.AUTOMATIC else self

    def render(self, system: str, user_lead: str, user_text: str) -> RenderedPrompt:
        """system: instructions (stable across chunks); user_lead: text that starts the user turn
        (stable, e.g. "TEXT:\\n"); user_text: the passage to check."""
        f = PromptFormat
        if self is f.GEMMA4:
            return RenderedPrompt(f"<|turn>system\n{system}<turn|>\n<|turn>user\n{user_lead}",
                                  f"{user_text}<turn|>\n<|turn>model\n")
        if self is f.GEMMA:
            # Gemma 2/3 have no system role: instructions go at the top of the first user turn.
            return RenderedPrompt(f"<start_of_turn>user\n{system}\n\n{user_lead}",
                                  f"{user_text}<end_of_turn>\n<start_of_turn>model\n")
        if self is f.LLAMA3:
            return RenderedPrompt(
                f"<|start_header_id|>system<|end_header_id|>\n\n{system}<|eot_id|>"
                f"<|start_header_id|>user<|end_header_id|>\n\n{user_lead}",
                f"{user_text}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n")
        if self is f.MISTRAL:
            return RenderedPrompt(f"[INST] {system}\n\n{user_lead}", f"{user_text} [/INST]")
        if self is f.PHI3:
            return RenderedPrompt(f"<|system|>\n{system}<|end|>\n<|user|>\n{user_lead}",
                                  f"{user_text}<|end|>\n<|assistant|>\n")
        if self is f.PLAIN:
            return RenderedPrompt(f"{system}\n\n{user_lead}", f"{user_text}\n\nOUTPUT:\n")
        # ChatML, and Automatic when it was never resolved.
        return RenderedPrompt(f"<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{user_lead}",
                              f"{user_text}<|im_end|>\n<|im_start|>assistant\n")


class PromptBuilder:
    """The copy-editing instructions given to the local language model. Small (2–8B) models do best
    with short, explicit rules and one worked example. Word for word the macOS edition's."""

    USER_LEAD = "TEXT:\n"

    def __init__(self, settings: CheckSettings):
        self.settings = settings

    @property
    def system_prompt(self) -> str:
        s = self.settings
        lines = [
            f"You are a meticulous, conservative copy editor for {s.dialect.prompt_name}.",
            "Find genuine errors and clear improvements in the TEXT the user sends: spelling, grammar, "
            "punctuation, word choice, clarity and concision.",
            f"Writing goals: {s.goals.prompt_description}. Only suggest tone changes that serve these goals.",
            "",
            "Rules:",
            '- Report only real problems. If the text is fine, return {"issues":[]}.',
            '- "original" must be copied EXACTLY from the TEXT (same letters, case and punctuation) and be as '
            "short as possible, usually 1 to 6 words.",
            '- "replacement" is the corrected text that replaces "original". Keep the author\'s meaning and voice.',
            f"- Use {s.dialect.prompt_name} spelling. Never change a correct spelling into another variety of "
            "English.",
            "- Do not rewrite whole sentences unless needed for clarity. Do not report matters of taste as errors.",
            "- Ignore code, URLs, e-mail addresses and Markdown syntax.",
            '- "explanation" is one short sentence of at most 20 words.',
            '- "category" is one of: spelling, grammar, punctuation, wordChoice, clarity, concision, style, tone.',
            "",
            "Respond with JSON only, in this exact form:",
            '{"issues":[{"original":"...","replacement":"...","category":"grammar","explanation":"..."}]}',
            "",
            "Example",
            "TEXT: Their going to the libary tomorow, and they has alot of book to return.",
            'OUTPUT: {"issues":[{"original":"Their going","replacement":"They\'re going","category":"grammar",'
            '"explanation":"Use \\"they\'re\\" (they are)."},{"original":"libary","replacement":"library",'
            '"category":"spelling","explanation":"Misspelling."},{"original":"tomorow","replacement":"tomorrow",'
            '"category":"spelling","explanation":"Misspelling."},{"original":"they has","replacement":"they have",'
            '"category":"grammar","explanation":"Subject and verb must agree."},{"original":"alot of book",'
            '"replacement":"a lot of books","category":"grammar","explanation":"\\"A lot\\" is two words, and the '
            'noun should be plural."}]}',
        ]
        return "\n".join(lines)

    def render(self, chunk: str, fmt: PromptFormat) -> RenderedPrompt:
        return fmt.render(self.system_prompt, self.USER_LEAD, chunk)


#: GBNF grammar that forces the model's output to be exactly the JSON shape parsed here. With
#: constrained decoding the model cannot produce chatter, Markdown fences, "thinking" blocks or
#: malformed JSON.
JSON_GRAMMAR = r'''root        ::= "{" ws "\"issues\"" ws ":" ws "[" ws issue-list? ws "]" ws "}"
issue-list  ::= issue ( ws "," ws issue )*
issue       ::= "{" ws "\"original\"" ws ":" ws string ws "," ws "\"replacement\"" ws ":" ws string ws "," ws "\"category\"" ws ":" ws category ws "," ws "\"explanation\"" ws ":" ws string ws "}"
category    ::= "\"spelling\"" | "\"grammar\"" | "\"punctuation\"" | "\"wordChoice\"" | "\"clarity\"" | "\"concision\"" | "\"style\"" | "\"tone\""
string      ::= "\"" char* "\""
char        ::= [^"\\\x00-\x1F] | "\\" ( ["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] )
ws          ::= [ \t\n]{0,8}'''


# --- parsing the model's output ---------------------------------------------------------------

@dataclass(frozen=True)
class LLMSuggestion:
    """One raw suggestion as returned by the language model (before it is located in the text)."""
    original: str
    replacement: str
    category: str
    explanation: str


class _DecodeError(Exception):
    pass


def _suggestion(obj) -> LLMSuggestion:
    """As the Swift decoder: "original" is required; the rest fall back to defaults."""
    if not isinstance(obj, dict) or not isinstance(obj.get("original"), str):
        raise _DecodeError()

    def opt(key, default):
        v = obj.get(key)
        return v if isinstance(v, str) else default
    return LLMSuggestion(obj["original"], opt("replacement", ""), opt("category", "grammar"), opt("explanation", ""))


def _decode_envelope(s: str) -> list[LLMSuggestion] | None:
    try:
        obj = json.loads(s)
        if not isinstance(obj, dict) or not isinstance(obj.get("issues"), list):
            return None
        return [_suggestion(x) for x in obj["issues"]]
    except (ValueError, _DecodeError, RecursionError):
        return None


def _decode_array(s: str) -> list[LLMSuggestion] | None:
    try:
        obj = json.loads(s)
        if not isinstance(obj, list):
            return None
        return [_suggestion(x) for x in obj]
    except (ValueError, _DecodeError, RecursionError):
        return None


class LLMResponseParser:
    @staticmethod
    def parse(raw: str) -> list[LLMSuggestion]:
        """Tolerates leading chatter, Markdown fences and output cut off by the token limit
        (keeps every complete issue object)."""
        starts = [i for i in (raw.find("{"), raw.find("[")) if i >= 0]
        if not starts:
            return []
        text = raw[min(starts):]
        if text.startswith("["):
            arr = _decode_array(text)
            if arr is not None:
                return arr
        full = _decode_envelope(text)
        if full is not None:
            return full
        # Repair truncated output: cut after the last complete object and close the array and object.
        search_end = len(text)
        for _ in range(64):
            close = text.rfind("}", 0, search_end)
            if close < 0:
                break
            head = text[:close + 1]
            for candidate in (_decode_envelope(head + "]}"), _decode_envelope(head)):
                if candidate is not None:
                    return candidate
            if head.startswith("["):
                arr = _decode_array(head + "]")
                if arr is not None:
                    return arr
            search_end = close
        return []


# --- anchoring --------------------------------------------------------------------------------------

_NORMALIZE = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u02bc": "'",      # ‘ ’ ʼ → '
    "\u201c": '"', "\u201d": '"',                      # “ ” → "
    "\u00a0": " ", "\u2009": " ", "\u202f": " ",       # non-breaking and thin spaces
    "\u2013": "-", "\u2014": "-",                      # – — → -
})


def normalize(s: str) -> str:
    """Length-preserving normalisation (one character for one character), so offsets found in the
    normalised text are valid in the original."""
    return s.translate(_NORMALIZE)


def _fold(s: str) -> str:
    """Length-preserving lower-casing (characters whose lower case is longer are kept as they are)."""
    return "".join(lc if len(lc := c.lower()) == 1 else c for c in s)


class IssueAnchorer:
    """Language models are poor at character offsets, so they quote the text instead. The anchorer
    finds each quote in the chunk and turns it into a positioned Issue."""

    @classmethod
    def anchor(cls, suggestions: list[LLMSuggestion], chunk: TextChunk, settings: CheckSettings) -> list[Issue]:
        text = chunk.text
        variants = (text, _fold(text), _fold(normalize(text)))
        cursor = 0
        used: set[TextSpan] = set()
        issues: list[Issue] = []
        for s in suggestions:
            original = s.original
            if not original.strip() or s.replacement == original:
                continue
            if lexicon.introduces_dispreferred_spelling(s.replacement, settings.dialect) \
                    and not lexicon.introduces_dispreferred_spelling(original, settings.dialect):
                continue
            local = cls.locate(original, variants, cursor, used)
            if local is None:
                continue
            used.add(local)
            cursor = local.location
            category = IssueCategory.from_loose_name(s.category) or IssueCategory.GRAMMAR
            explanation = s.explanation.strip()
            issues.append(Issue(span=local.offset(chunk.span.location), original=text[local.location:local.upper_bound],
                                suggestions=[s.replacement], category=category,
                                message=explanation or "Suggested by the AI model.",
                                rule_id=f"ai.{category.value}", source=IssueSource.AI))
        return issues

    @staticmethod
    def locate(needle: str, variants: tuple[str, str, str], cursor: int, used: set[TextSpan]) -> TextSpan | None:
        exact, folded, normalized = variants
        attempts = ((exact, needle), (folded, _fold(needle)), (normalized, _fold(normalize(needle))))
        for source, query in attempts:
            if not query:
                continue
            for start in (cursor, 0):
                location = max(0, min(start, len(source)))
                while location < len(source):
                    found = source.find(query, location)
                    if found < 0:
                        break
                    span = TextSpan(found, len(query))
                    if span not in used:
                        return span
                    location = found + 1
        return None


# --- the reviewer -------------------------------------------------------------------------------------

@dataclass
class AIReviewOptions:
    format: PromptFormat
    model_identifier: str
    max_output_tokens: int = 1024
    max_chunk_length: int = 1200
    use_grammar: bool = True


@dataclass
class ReviewProgress:
    completed: int
    total: int
    #: The region of the snapshot that was just reviewed (in snapshot coordinates).
    chunk_span: TextSpan
    #: Issues found in that region (in snapshot coordinates).
    issues: list[Issue] = field(default_factory=list)
    from_cache: bool = False


class ReviewCache:
    """In-memory cache of model output per chunk. Never written to disk."""

    def __init__(self, limit: int = 4000):
        self._storage: dict[str, list[LLMSuggestion]] = {}
        self._limit = limit
        self._lock = threading.Lock()

    def get(self, key: str) -> list[LLMSuggestion] | None:
        with self._lock:
            return self._storage.get(key)

    def store(self, key: str, value: list[LLMSuggestion]) -> None:
        with self._lock:
            if len(self._storage) >= self._limit:
                self._storage.clear()
            self._storage[key] = value

    def clear(self) -> None:
        with self._lock:
            self._storage.clear()

    def __len__(self) -> int:
        return len(self._storage)


class AIReviewer:
    def __init__(self, generator: TextGenerating, cache: ReviewCache):
        self.generator = generator
        self.cache = cache

    def review(self, text: str, settings: CheckSettings, options: AIReviewOptions,
               cancel: CancelToken | None = None) -> Iterator[ReviewProgress]:
        """Reviews `text` chunk by chunk, yielding results as each chunk completes. Raises Cancelled."""
        cancel = cancel or CancelToken()
        zones = ExclusionZones.compute(text)
        chunks = TextChunker.chunks(text, options.max_chunk_length, zones)
        builder = PromptBuilder(settings)
        key_prefix = f"{options.model_identifier}|{options.format.value}|{settings.ai_cache_key}|"
        for index, chunk in enumerate(chunks):
            cancel.check()
            key = key_prefix + chunk.text
            suggestions = self.cache.get(key)
            from_cache = suggestions is not None
            if suggestions is None:
                prompt = builder.render(chunk.text, options.format)
                raw = self.generator.generate(prompt.prefix, prompt.body,
                                              JSON_GRAMMAR if options.use_grammar else None,
                                              options.max_output_tokens, cancel)
                cancel.check()
                suggestions = LLMResponseParser.parse(raw)
                self.cache.store(key, suggestions)
            issues = [i for i in IssueAnchorer.anchor(suggestions, chunk, settings)
                      if not ExclusionZones.is_excluded(i.span, zones)]
            yield ReviewProgress(index + 1, len(chunks), chunk.span, issues, from_cache)
