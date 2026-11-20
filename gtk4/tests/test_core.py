"""Tests of the pure core: ports of the macOS edition's RuleTests, TextTests and
AIPipelineTests (keep them in step), plus the regex translation, the
importers and the offline guarantees."""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qdvc import uregex  # noqa: E402
from qdvc.ai import (AIReviewer, AIReviewOptions, CancelToken, Cancelled, IssueAnchorer, LLMResponseParser,  # noqa: E402
                     LLMSuggestion, PromptBuilder, PromptFormat, ReviewCache, TextChunk, TextChunker, JSON_GRAMMAR)
from qdvc.model import (CheckSettings, Dialect, Formality, Issue, IssueCategory, IssueSource,  # noqa: E402
                        TextSpan, WritingGoals, substring)
from qdvc.rules import RULE_INFOS, ArticleRule, RuleEngine  # noqa: E402
from qdvc.text import ExclusionZones, IssueAdjuster, IssueMerger, SentenceSplitter, TextStatistics  # noqa: E402
from qdvc.textutil import match_case  # noqa: E402


def settings(dialect=Dialect.US, formality=Formality.NEUTRAL, **kw) -> CheckSettings:
    return CheckSettings(dialect=dialect, goals=WritingGoals(formality=formality), **kw)


class RuleTests(unittest.TestCase):
    def issues(self, text, dialect=Dialect.US, formality=Formality.NEUTRAL, rule=None):
        found = RuleEngine(settings(dialect, formality)).check(text)
        return [i for i in found if rule is None or i.rule_id == rule]

    def first(self, *a, **kw):
        found = self.issues(*a, **kw)
        return found[0] if found else None

    def test_repeated_word(self):
        found = self.issues("I went to the the shop.", rule="repeated-word")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].original, "the the")
        self.assertEqual(found[0].suggestions, ["the"])

    def test_repeated_word_allows_had_had(self):
        self.assertEqual(self.issues("She had had enough.", rule="repeated-word"), [])

    def test_articles(self):
        self.assertEqual(self.first("It took a hour.", rule="a-an").suggestions, ["an"])
        self.assertEqual(self.first("She is an university student.", rule="a-an").suggestions, ["a"])
        self.assertEqual(self.first("He has a MBA.", rule="a-an").suggestions, ["an"])
        self.assertEqual(self.issues("It was an unimportant detail.", rule="a-an"), [])
        self.assertEqual(self.issues("It was a unique event.", rule="a-an"), [])
        self.assertEqual(self.issues("Plan A is good.", rule="a-an"), [])
        self.assertEqual(self.issues("We need an herb garden.", rule="a-an"), [])  # dialect-dependent

    def test_article_numbers(self):
        self.assertTrue(ArticleRule.expects_an("8"))
        self.assertTrue(ArticleRule.expects_an("11th"))
        self.assertFalse(ArticleRule.expects_an("1,000"))

    def test_common_errors(self):
        self.assertEqual(self.first("I could of done it.", rule="common-errors").suggestions, ["could have"])
        self.assertEqual(self.issues("It could of course be true.", rule="common-errors"), [])
        self.assertEqual(self.first("This is better then that.", rule="common-errors").suggestions, ["better than"])
        self.assertEqual(self.first("They should have went home.", rule="common-errors").suggestions,
                         ["have gone"])

    def test_dialect_spelling(self):
        self.assertEqual(self.first("The colour is nice.", Dialect.US, rule="dialect-spelling").suggestions,
                         ["color"])
        self.assertEqual(self.first("The color is nice.", Dialect.GB, rule="dialect-spelling").suggestions,
                         ["colour"])
        self.assertEqual(self.first("We must organize it.", Dialect.GB, rule="dialect-spelling").suggestions,
                         ["organise"])
        self.assertEqual(self.issues("We must organize it.", Dialect.GB_OXFORD, rule="dialect-spelling"), [])
        self.assertEqual(self.first("Colours", Dialect.US, rule="dialect-spelling").suggestions, ["Colors"])
        self.assertEqual(self.issues("The humorous honorary member.", Dialect.GB, rule="dialect-spelling"), [])

    def test_sentence_capitalization(self):
        self.assertEqual(self.first("This is fine. this is not.", rule="sentence-capitalization").suggestions,
                         ["This"])
        self.assertEqual(self.issues("Use e.g. apples.", rule="sentence-capitalization"), [])
        self.assertEqual(self.issues("I bought one. iPhone sales rose.", rule="sentence-capitalization"), [])

    def test_lowercase_i(self):
        self.assertEqual(len(self.issues("Yesterday i went home.", rule="lowercase-i")), 1)
        self.assertEqual(self.issues("That is, i.e. this one.", rule="lowercase-i"), [])

    def test_spacing(self):
        self.assertEqual(len(self.issues("Two  spaces.", rule="multiple-spaces")), 1)
        self.assertEqual(len(self.issues("Hello , world.", rule="space-before-punctuation")), 1)
        self.assertEqual(self.first("Hello,world.", rule="missing-space").suggestions, [", "])
        self.assertEqual(self.issues("Pi is 3.14 and 1,000 is big.", rule="missing-space"), [])

    def test_unbalanced(self):
        self.assertEqual(len(self.issues("This (is open.", rule="unbalanced-pairs")), 1)
        self.assertEqual(self.issues("1) First item", rule="unbalanced-pairs"), [])
        self.assertEqual(self.issues("A (closed) one.", rule="unbalanced-pairs"), [])

    def test_wordiness_deletion_includes_space(self):
        found = self.first("We are in the process of updating.", rule="wordiness")
        self.assertEqual(found.suggestions, [""])
        self.assertEqual(found.original, "in the process of ")

    def test_formality(self):
        self.assertEqual(self.issues("We don't know.", formality=Formality.NEUTRAL, rule="formality"), [])
        self.assertEqual(self.first("We don't know.", formality=Formality.FORMAL, rule="formality").suggestions,
                         ["do not"])
        self.assertEqual(self.first("I'm gonna go.", formality=Formality.NEUTRAL, rule="formality").suggestions,
                         ["going to"])

    def test_urls_are_excluded(self):
        self.assertEqual(self.issues("See https://example.com/the/the/page for more.", rule="repeated-word"), [])

    def test_case_style(self):
        self.assertEqual(match_case("because", "Due to the fact that"), "Because")
        self.assertEqual(match_case("pin", "PIN"), "PIN")
        self.assertEqual(match_case("near", "in close proximity to"), "near")

    # Beyond the Swift tests.

    def test_passive_long_sentence_and_proper_nouns(self):
        self.assertEqual(len(self.issues("The report was written by Sam.", rule="passive-voice")), 1)
        self.assertEqual(self.issues("I was tired.", rule="passive-voice"), [])
        long_sentence = " ".join(["word"] * 40) + "."
        self.assertEqual(len(self.issues(long_sentence, rule="long-sentence")), 1)
        self.assertEqual(self.first("See you on monday.", rule="proper-nouns").suggestions, ["Monday"])

    def test_rules_off_by_default_and_overrides(self):
        off = {i.id for i in RULE_INFOS if not i.default_enabled}
        self.assertEqual(off, {"fillers", "inclusive-language", "smart-typography"})
        s = settings().with_override("fillers", True)
        found = [i for i in RuleEngine(s).check("It is basically fine.") if i.rule_id == "fillers"]
        self.assertEqual(found[0].original, "basically ")
        self.assertEqual(len(RULE_INFOS), 22)

    def test_offsets_are_characters(self):
        # Characters outside the BMP (an emoji) count as one, as Gtk.TextIter offsets do.
        text = "😀 the the end"
        found = self.first(text, rule="repeated-word")
        self.assertEqual(found.span, TextSpan(2, 7))
        self.assertEqual(substring(text, found.span), "the the")


class TextTests(unittest.TestCase):
    def test_sentence_splitting(self):
        text = "Dr. Smith arrived. He said hello! Did it work? Yes, e.g. this one."
        self.assertEqual([substring(text, s) for s in SentenceSplitter.sentences(text)],
                         ["Dr. Smith arrived.", "He said hello!", "Did it work?", "Yes, e.g. this one."])

    def test_statistics(self):
        stats = TextStatistics.compute("The cat sat on the mat. " * 10)
        self.assertEqual(stats.words, 60)
        self.assertEqual(stats.sentences, 10)
        self.assertIsNotNone(stats.flesch_reading_ease)
        self.assertGreater(stats.flesch_reading_ease, 90)

    def test_adjuster_shifts_and_drops(self):
        def mk(loc, orig):
            return Issue(span=TextSpan(loc, 3), original=orig, category=IssueCategory.SPELLING, message="",
                         rule_id="x", source=IssueSource.RULES)
        adjusted = IssueAdjuster.adjust([mk(0, "teh"), mk(10, "abc"), mk(20, "xyz")], TextSpan(11, 2), 5)
        self.assertEqual([i.original for i in adjusted], ["teh", "xyz"])
        self.assertEqual(adjusted[-1].span.location, 23)

    def test_transform_region(self):
        self.assertEqual(IssueAdjuster.transform_region(TextSpan(10, 10), TextSpan(12, 2), 6), TextSpan(10, 14))
        self.assertEqual(IssueAdjuster.transform_region(TextSpan(10, 10), TextSpan(0, 2), 0), TextSpan(8, 10))

    def test_merger_deduplicates_and_validates(self):
        text = "teh cat"
        spell = Issue(span=TextSpan(0, 3), original="teh", suggestions=["the"], category=IssueCategory.SPELLING,
                      message="", rule_id="s", source=IssueSource.SPELL_CHECKER)
        ai = Issue(span=TextSpan(0, 3), original="teh", suggestions=["the", "tea"], category=IssueCategory.SPELLING,
                   message="", rule_id="a", source=IssueSource.AI)
        stale = Issue(span=TextSpan(4, 3), original="dog", category=IssueCategory.SPELLING, message="",
                      rule_id="s", source=IssueSource.SPELL_CHECKER)
        merged = IssueMerger.merge([[spell], [ai, stale]], text, set(), CheckSettings(), [])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].suggestions, ["the", "tea"])
        self.assertEqual(spell.suggestions, ["the"], "the inputs are not changed")

    def test_personal_dictionary(self):
        s = CheckSettings(personal_dictionary=("QDVC",))
        issue = Issue(span=TextSpan(0, 4), original="qdvc", category=IssueCategory.SPELLING, message="",
                      rule_id="s", source=IssueSource.SPELL_CHECKER)
        self.assertEqual(IssueMerger.merge([[issue]], "qdvc", set(), s, []), [])

    def test_exclusion_zones(self):
        self.assertEqual(len(ExclusionZones.compute("Run `the the` or visit www.example.com now.")), 2)
        fenced = "Text\n```\nthe the\n```\nMore."
        self.assertEqual(len(ExclusionZones.compute(fenced)), 1)


class AIPipelineTests(unittest.TestCase):
    def test_parses_clean_json(self):
        raw = '{"issues":[{"original":"teh","replacement":"the","category":"spelling","explanation":"Typo."}]}'
        self.assertEqual([s.replacement for s in LLMResponseParser.parse(raw)], ["the"])

    def test_parses_truncated_json(self):
        raw = ('{"issues":[{"original":"teh","replacement":"the","category":"spelling","explanation":"Typo."},'
               '{"original":"recieve","replac')
        self.assertEqual([s.original for s in LLMResponseParser.parse(raw)], ["teh"])

    def test_parses_fenced_json(self):
        self.assertEqual(LLMResponseParser.parse('Sure! Here you go:\n```json\n{"issues":[]}\n```'), [])
        raw = 'Here:\n```json\n{"issues":[{"original":"a","replacement":"b"}]}\n```'
        self.assertEqual(LLMResponseParser.parse(raw)[0].category, "grammar")

    def test_anchoring(self):
        chunk = TextChunk(TextSpan(100, 29), "I recieve the the mail daily.")
        found = IssueAnchorer.anchor([
            LLMSuggestion("recieve", "receive", "spelling", "Typo."),
            LLMSuggestion("Missing words", "x", "grammar", "Not in text."),
        ], chunk, CheckSettings())
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].span, TextSpan(102, 7))
        self.assertEqual(found[0].category, IssueCategory.SPELLING)

    def test_anchoring_normalises_quotes(self):
        chunk = TextChunk(TextSpan(0, 14), "It’s own thing")
        found = IssueAnchorer.anchor([LLMSuggestion("It's own", "Its own", "grammar", "")], chunk, CheckSettings())
        self.assertEqual(found[0].original, "It’s own")

    def test_dialect_guard_rejects_wrong_variety(self):
        chunk = TextChunk(TextSpan(0, 15), "A lovely colour")
        found = IssueAnchorer.anchor([LLMSuggestion("colour", "color", "spelling", "")], chunk,
                                     settings(Dialect.GB))
        self.assertEqual(found, [])

    def test_chunker_merges_short_paragraphs(self):
        text = "Heading\n\n" + "This is a sentence that goes on. " * 5 + "\n\nShort tail."
        chunks = TextChunker.chunks(text, 1200)
        self.assertEqual(len(chunks), 2)
        self.assertTrue(chunks[0].text.startswith("Heading"))

    def test_chunker_splits_long_paragraphs(self):
        text = "This is a reasonably long sentence used for testing the chunker. " * 40
        chunks = TextChunker.chunks(text, 500)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(c.span.length <= 500 for c in chunks))
        self.assertTrue(all(substring(text, c.span) == c.text for c in chunks))

    def test_prompt_format_detection(self):
        self.assertEqual(PromptFormat.detect("{{ '<|turn>user' }}", "gemma4"), PromptFormat.GEMMA4)
        self.assertEqual(PromptFormat.detect("<start_of_turn>", None), PromptFormat.GEMMA)
        self.assertEqual(PromptFormat.detect(None, "qwen3"), PromptFormat.CHATML)

    def test_prompt_is_split_into_a_stable_prefix(self):
        b = PromptBuilder(settings(Dialect.GB))
        one, two = b.render("First.", PromptFormat.GEMMA4), b.render("Second.", PromptFormat.GEMMA4)
        self.assertEqual(one.prefix, two.prefix)
        self.assertTrue(one.prefix.endswith("TEXT:\n"))
        self.assertIn("British English (-ise spellings)", one.prefix)
        self.assertEqual(one.body, "First.<turn|>\n<|turn>model\n")
        self.assertIn('"explanation":"Use \\"they\'re\\" (they are)."', b.system_prompt)

    def test_grammar_text(self):
        self.assertTrue(JSON_GRAMMAR.startswith('root        ::= "{" ws "\\"issues\\""'))
        self.assertTrue(JSON_GRAMMAR.endswith("ws          ::= [ \\t\\n]{0,8}"))

    def test_reviewer_uses_cache(self):
        calls = []

        class Mock:
            def generate(self, prefix, body, grammar, max_tokens, cancel=None):
                calls.append(body)
                return '{"issues":[{"original":"teh","replacement":"the","category":"spelling","explanation":"Typo."}]}'

        reviewer = AIReviewer(Mock(), ReviewCache())
        text = "This paragraph has teh typo and is long enough to stand on its own as a chunk of text."
        options = AIReviewOptions(PromptFormat.CHATML, "mock")
        found = [i for p in reviewer.review(text, CheckSettings(), options) for i in p.issues]
        self.assertEqual([i.original for i in found], ["teh"])
        progress = list(reviewer.review(text, CheckSettings(), options))
        self.assertTrue(progress[0].from_cache)
        self.assertEqual(len(calls), 1)

    def test_reviewer_cancels(self):
        class Mock:
            def generate(self, *a, **kw):
                return '{"issues":[]}'
        token = CancelToken()
        token.cancel()
        with self.assertRaises(Cancelled):
            list(AIReviewer(Mock(), ReviewCache()).review("Some text that is here.", CheckSettings(),
                                                          AIReviewOptions(PromptFormat.CHATML, "m"), token))


class RegexTranslationTests(unittest.TestCase):
    def test_properties_inside_and_outside_classes(self):
        self.assertTrue(uregex.compile(r"\p{Lu}\p{Ll}+").fullmatch("Élan"))
        self.assertTrue(uregex.compile(r"[\p{L}\p{N}]+").fullmatch("abc123ß"))
        self.assertIsNone(uregex.compile(r"\p{L}").search("123 _"))
        self.assertTrue(uregex.compile(r"[^\p{L}]").fullmatch("1"))
        self.assertTrue(uregex.compile(r"[\]\p{N}]+").fullmatch("]1"))

    def test_every_rule_pattern_compiles(self):
        from qdvc import rules
        for rule in rules.RULES:
            for name in dir(rule):
                if isinstance(getattr(rule, name, None), re.Pattern):
                    self.assertIsInstance(getattr(rule, name), re.Pattern)


class OfflineTests(unittest.TestCase):
    """The app must never touch the network (docs/MAINTENANCE.md §1.1)."""

    FORBIDDEN = [r"\bimport socket\b", r"\bfrom socket\b", r"\burllib\b", r"\bhttp\.client\b", r"\bhttp\.server\b",
                 r"\brequests\b", r"\baiohttp\b", r"\bwebbrowser\b", r"\bftplib\b", r"\bsmtplib\b", r"\bxmlrpc\b",
                 r"\bWebKit\b", r"Gio\.Socket", r"Gio\.Resolver", r"Gio\.NetworkMonitor", r"Soup\b",
                 r"UriLauncher", r"show_uri", r"launch_default_for_uri", r"http://", r"https://"]

    def test_no_networking_in_the_sources(self):
        files = list((ROOT / "qdvc").rglob("*.py")) + [ROOT / "qdvc_articulate.py"]
        self.assertTrue(files)
        for f in files:
            # An XML namespace URI is an identifier, never fetched; such lines say so.
            text = "\n".join(line for line in f.read_text(encoding="utf-8").splitlines()
                             if "# XML namespace" not in line)
            for pat in self.FORBIDDEN:
                self.assertIsNone(re.search(pat, text), f"{f.relative_to(ROOT)} matches {pat}")

    def test_no_networking_in_the_native_shim(self):
        text = (ROOT / "native" / "articulate_llama.c").read_text(encoding="utf-8")
        for pat in (r"\bsocket\s*\(", r"\bconnect\s*\(", r"curl", r"http"):
            self.assertIsNone(re.search(pat, text, re.IGNORECASE), pat)

    def test_flatpak_has_no_network_and_no_filesystem(self):
        manifest = (ROOT / "flatpak" / "qdvc.articulate.gtk4app.yml").read_text(encoding="utf-8")
        finish = manifest.split("finish-args:")[1].split("modules:")[0]
        args = [line.strip()[2:] for line in finish.splitlines() if line.strip().startswith("- ")]
        self.assertTrue(args)
        for a in args:
            self.assertNotIn("network", a)
            self.assertFalse(a.startswith("--filesystem"), a)
        self.assertIn("-DLLAMA_CURL=OFF", manifest)


if __name__ == "__main__":
    unittest.main()
