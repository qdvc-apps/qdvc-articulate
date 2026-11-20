"""Smoke tests of the GTK 4 front-end.

* With a stub ``gi`` (tests/stubs), every qdvc.gtk4 module must import: this
  runs anywhere, with or without GTK.
* With GTK 4, libadwaita and a display (xvfb-run is enough), the window is
  built, the shared sample is opened, issues are found and underlined, a
  suggestion is applied from the inspector's state, the document is saved,
  and the tabs come back from the session.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(os.path.dirname(ROOT), "sample-texts", "sample.md")
MODULES = sorted(f"qdvc.gtk4.{n[:-3]}" for n in os.listdir(os.path.join(ROOT, "qdvc", "gtk4"))
                 if n.startswith("gtk4_") and n.endswith(".py"))

DRIVER = r'''
import os, sys, time
sys.path.insert(0, ROOT)
os.environ["GSK_RENDERER"] = "cairo"
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import GLib
from qdvc.gtk4 import gtk4_app
app = gtk4_app.App()
errors = []

def spin(n=40):
    ctx = GLib.MainContext.default()
    for _ in range(n):
        while ctx.pending():
            ctx.iteration(False)
        time.sleep(0.01)

def drive():
    w = app.window
    try:
        w.open_path(DOC); spin(80)
        page = w._page()
        assert page.document.path == DOC, "opened"
        rules = {i.rule_id for i in page.state.issues}
        assert "repeated-word" in rules and "common-errors" in rules, rules
        assert w.issue_list.list.get_first_child() is not None, "the inspector lists issues"
        w.lookup_action("next-issue").activate(None); spin(10)
        assert page.state.focused_issue is not None
        issue = next(i for i in page.state.issues if i.rule_id == "repeated-word")
        page.state.apply(issue, issue.suggestions[0]); spin(60)
        assert "the the new" not in page.state.text and page.modified
        w.lookup_action("save").activate(None); spin(10)
        assert not page.modified and "We recieved the new books" in open(DOC).read()
        w.lookup_action("new-tab").activate(None); spin(10)
        w._page().buffer.set_text("An untitled draft with teh typo."); spin(60)
        w.lookup_action("find").activate(None); spin(5)
        for name in ("general", "rules", "model", "dictionary", "privacy"):
            w.show_preferences(name); spin(5)
        w.save_session()
        tabs, active = w.store.load()
        assert len(tabs) == 2 and tabs[1].text.startswith("An untitled draft"), tabs
    except Exception as e:
        import traceback; traceback.print_exc(); errors.append(e)
    app.quit()
    return False

app.connect("activate", lambda *_: GLib.timeout_add(300, drive))
app.run([sys.argv[0]])
sys.exit(1 if errors else 0)
'''


def have_display() -> bool:
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return False
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        return True
    except (ImportError, ValueError):
        return False


class StubImportTests(unittest.TestCase):
    def test_every_gtk4_module_imports_with_a_stub_gi(self):
        code = "import importlib\n" + "".join(f"importlib.import_module({m!r})\n" for m in MODULES)
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([os.path.join(ROOT, "tests", "stubs"), ROOT]))
        r = subprocess.run([sys.executable, "-c", code], env=env, cwd=ROOT, capture_output=True, text=True,
                           timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_entry_point_compiles(self):
        import py_compile
        py_compile.compile(os.path.join(ROOT, "qdvc_articulate.py"), doraise=True)


@unittest.skipUnless(have_display(), "needs GTK 4, libadwaita and a display (try xvfb-run)")
class WindowTests(unittest.TestCase):
    def test_open_check_apply_save_and_restore(self):
        tmp = tempfile.mkdtemp(prefix="articulate-smoke-")
        self.addCleanup(shutil.rmtree, tmp, True)
        doc = os.path.join(tmp, "sample.md")
        shutil.copy(SAMPLE, doc)
        env = dict(os.environ, XDG_CONFIG_HOME=os.path.join(tmp, "config"),
                   XDG_STATE_HOME=os.path.join(tmp, "state"), GTK_A11Y="none")
        code = f"ROOT = {ROOT!r}\nDOC = {doc!r}\n" + DRIVER
        r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
