"""Tests of the toolkit-independent layer the window drives: preferences, the
model manager, per-document checking (EditorState), drafts and the restored
session, and the isolation report."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qdvc import isolation  # noqa: E402
from qdvc.ai import PromptFormat  # noqa: E402
from qdvc.editor import EditorState, Environment  # noqa: E402
from qdvc.engine import ModelManager, ModelState  # noqa: E402
from qdvc.llm import ModelInfo  # noqa: E402
from qdvc.model import Dialect, Formality, IssueGroup  # noqa: E402
from qdvc.preferences import Preferences  # noqa: E402
from qdvc.rules import RULE_INFOS  # noqa: E402
from qdvc.session import Document, SessionStore  # noqa: E402

REPLY = '{"issues":[{"original":"recieve","replacement":"receive","category":"spelling","explanation":"Typo."}]}'


class FakeEngine:
    def __init__(self):
        self.calls = 0

    def load(self, path, config):
        return ModelInfo("m.gguf", "fake", "qwen3", "<|im_start|>", 10, 1, 4096, config.context_length)

    def unload(self):
        pass

    def configure(self, temperature, reuse):
        pass

    def generate(self, prefix, body, grammar, max_tokens, cancel=None):
        self.calls += 1
        return REPLY


class View:
    def __init__(self, state):
        self.state = state
        self.revealed = None

    def replace_range(self, start, end, text):
        self.state.will_edit(start, end - start, len(text))
        self.state.text_changed(self.state.text[:start] + text + self.state.text[end:])

    def reveal(self, start, end):
        self.revealed = (start, end)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="articulate-"))
        self.prefs = Preferences(self.tmp / "config.yml")
        self.prefs.set_option("spelling", False)


class PreferencesTests(Base):
    def test_round_trip(self):
        p = self.prefs
        p.set_dialect(Dialect.GB)
        p.set_goals(formality=Formality.FORMAL)
        p.set_rule(next(i for i in RULE_INFOS if i.id == "fillers"), True)
        p.set_rule(next(i for i in RULE_INFOS if i.id == "passive-voice"), False)
        p.add_to_dictionary("QDVC")
        p.add_to_dictionary("qdvc")
        p.set_llama(temperature=0.35, prompt_format=PromptFormat.GEMMA4)
        p.set_model_path("/run/user/1000/doc/abc/model.gguf")
        p.add_recent("/tmp/a.md")
        again = Preferences(self.tmp / "config.yml")
        self.assertEqual(again.check, p.check)
        self.assertEqual(again.check.personal_dictionary, ("QDVC",))
        self.assertEqual(again.check.overrides, {"fillers": True, "passive-voice": False})
        self.assertEqual(again.llama, p.llama)
        self.assertEqual(again.model_path, p.model_path)
        self.assertEqual(again.recent_files, ["/tmp/a.md"])

    def test_tolerant_of_bad_values(self):
        (self.tmp / "bad.yml").write_text("dialect: klingon\nllama:\n  context_length: lots\neditor_font_size: 99\n")
        p = Preferences(self.tmp / "bad.yml")
        self.assertEqual(p.check.dialect, Dialect.US)
        self.assertEqual(p.llama.context_length, 8192)
        self.assertEqual(p.editor_font_size, 12)

    def test_listeners(self):
        seen = []
        self.prefs.connect(seen.append)
        self.prefs.set_dialect(Dialect.AU)
        self.prefs.set_dialect(Dialect.AU)
        self.prefs.set_option("monospace", True)
        self.assertEqual(seen, ["check", "editor"])


class EditorTests(Base):
    def make(self, engine=None):
        models = ModelManager(self.prefs, lambda work, done: done(work()), engine or FakeEngine(), available=True)
        state = EditorState(self.prefs, models, None, Environment())
        state.view = View(state)
        return models, state

    def test_quick_check_and_apply(self):
        _, state = self.make()
        state.load("I went to the the shop.")
        self.assertEqual([i.rule_id for i in state.issues], ["repeated-word"])
        self.assertEqual(state.stats.words, 6)
        state.apply(state.issues[0], state.issues[0].suggestions[0])
        self.assertEqual(state.text, "I went to the shop.")
        self.assertEqual(state.issues, [])

    def test_navigation_ignore_and_hidden_groups(self):
        _, state = self.make()
        state.load("I could of gone. It was a very good day.")
        groups = {i.category.group for i in state.issues}
        self.assertIn(IssueGroup.CORRECTNESS, groups)
        state.select_next()
        first = state.focused_issue
        self.assertEqual(state.view.revealed, (first.span.location, first.span.upper_bound))
        state.ignore_focused()
        self.assertNotIn(first.fingerprint, [i.fingerprint for i in state.issues])
        state.clear_ignored()
        self.assertIn(first.fingerprint, [i.fingerprint for i in state.issues])
        state.set_group_hidden(IssueGroup.CORRECTNESS, True)
        self.assertTrue(all(i.category.group is not IssueGroup.CORRECTNESS for i in state.visible_issues))

    def test_edits_shift_issues(self):
        _, state = self.make()
        state.load("Hello. the the end.")
        state.will_edit(0, 0, 4)
        state.text = "Oh, Hello. the the end."
        state.refresh()
        self.assertEqual(state.issues[0].span.location, 11)

    def test_ai_review(self):
        engine = FakeEngine()
        models, state = self.make(engine)
        state.run_ai_check()
        self.assertEqual(state.ai_state.kind, "failed")
        self.assertIn("No AI model", state.ai_state.message)
        self.prefs.set_model_path(str(self.tmp / "config.yml"))  # any existing file: the engine is fake
        models.load()
        self.assertIs(models.status.state, ModelState.READY)
        self.assertEqual(models.resolved_format, PromptFormat.CHATML)
        state.load("This paragraph says I recieve letters, and it is long enough to be checked on its own here.")
        state.run_ai_check()
        self.assertEqual(state.ai_state.kind, "finished")
        self.assertEqual(state.ai_state.found, 1)
        self.assertIn("ai.spelling", [i.rule_id for i in state.issues])
        state.run_ai_check()
        self.assertEqual(engine.calls, 1, "the second review comes from the cache")

    def test_dictionary_filters_spelling(self):
        _, state = self.make()
        state.load("This paragraph says I recieve letters, and it is long enough to be checked on its own here.")
        state.models.prefs.set_model_path(str(self.tmp / "config.yml"))
        state.models.load()
        state.run_ai_check()
        issue = next(i for i in state.issues if i.original == "recieve")
        state.add_to_dictionary(issue)
        state.settings_changed()
        self.assertNotIn("recieve", [i.original for i in state.issues])


class SessionTests(unittest.TestCase):
    def test_drafts_and_restore(self):
        tmp = Path(tempfile.mkdtemp(prefix="articulate-session-"))
        f = tmp / "notes.md"
        f.write_text("saved\r\n")
        store = SessionStore(tmp / "state")
        saved, text = Document.open(str(f))
        self.assertEqual((text, saved.line_ending), ("saved\n", "\r\n"))
        untitled = Document()
        empty = Document()
        store.save([(saved, "saved\nand more\n", 7), (untitled, "draft text\n", 0), (empty, "", 0)], active=1)
        tabs, active = store.load()
        self.assertEqual([t.text for t in tabs], ["saved\nand more\n", "draft text\n"])
        self.assertEqual(active, 1)
        self.assertTrue(tabs[0].document.is_modified(tabs[0].text))
        self.assertEqual(tabs[0].document.line_ending, "\r\n")
        self.assertEqual(tabs[0].cursor, 7)
        tabs[0].document.save(tabs[0].text)
        self.assertEqual(f.read_bytes(), b"saved\r\nand more\r\n")
        store.save([(tabs[0].document, tabs[0].text, 0)], 0)
        self.assertEqual(list((tmp / "state" / "drafts").glob("*.txt")), [])
        tabs, _ = store.load()
        self.assertFalse(tabs[0].document.is_modified(tabs[0].text))

    def test_missing_file_keeps_the_draft(self):
        tmp = Path(tempfile.mkdtemp(prefix="articulate-session-"))
        f = tmp / "gone.md"
        f.write_text("x")
        store = SessionStore(tmp / "state")
        doc, _ = Document.open(str(f))
        store.save([(doc, "changed", 0)], 0)
        os.unlink(f)
        tabs, _ = store.load()
        self.assertIsNone(tabs[0].document.path)
        self.assertEqual(tabs[0].text, "changed")


class IsolationTests(unittest.TestCase):
    def test_report(self):
        tmp = Path(tempfile.mkdtemp(prefix="articulate-iso-"))
        info = tmp / "flatpak-info"
        info.write_text("[Application]\nname=qdvc.articulate.gtk4app\n\n[Context]\nshared=ipc;\n"
                        "sockets=wayland;fallback-x11;\n")
        net = tmp / "net"
        (net / "lo").mkdir(parents=True)
        r = isolation.report(str(info), str(net))
        self.assertTrue(r.is_isolated)
        self.assertEqual(r.app_id, "qdvc.articulate.gtk4app")
        info.write_text("[Context]\nshared=network;ipc;\n")
        self.assertFalse(isolation.report(str(info), str(net)).is_isolated)
        self.assertFalse(isolation.report(str(tmp / "absent"), str(net)).is_isolated)


if __name__ == "__main__":
    unittest.main()
